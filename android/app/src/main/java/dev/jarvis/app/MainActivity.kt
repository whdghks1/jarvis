package dev.jarvis.app

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.CalendarContract
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.util.Locale

data class UiMessage(val role: String, val text: String)

class MainActivity : ComponentActivity() {
    private var textToSpeech: TextToSpeech? = null
    private var ttsReady = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val tokenStore = SecureTokenStore(this)
        val prefs = getSharedPreferences("jarvis_settings", MODE_PRIVATE)
        textToSpeech = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) {
                textToSpeech?.language = Locale.KOREAN
                ttsReady = true
            }
        }
        setContent {
            JarvisTheme {
                JarvisApp(
                    tokenStore = tokenStore,
                    initialServerUrl = prefs.getString("server_url", BuildConfig.DEFAULT_SERVER_URL)
                        ?: BuildConfig.DEFAULT_SERVER_URL,
                    saveServerUrl = { prefs.edit().putString("server_url", it).apply() },
                    initialConversationId = prefs.getInt("conversation_id", -1).takeIf { it > 0 },
                    saveConversationId = { id ->
                        if (id == null) prefs.edit().remove("conversation_id").apply()
                        else prefs.edit().putInt("conversation_id", id).apply()
                    },
                    initialTtsEnabled = prefs.getBoolean("tts_enabled", true),
                    saveTtsEnabled = { prefs.edit().putBoolean("tts_enabled", it).apply() },
                    speak = { text ->
                        if (ttsReady) textToSpeech?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "jarvis_reply")
                    },
                    executeAction = ::executeAction,
                )
            }
        }
    }

    override fun onDestroy() {
        textToSpeech?.stop()
        textToSpeech?.shutdown()
        super.onDestroy()
    }

    private fun executeAction(action: DeviceAction) {
        val intent = when (action.type) {
            "phone.dial" -> Intent(Intent.ACTION_DIAL, Uri.parse("tel:${action.payload.getString("phone_number")}"))
            "navigation.open" -> {
                val query = Uri.encode(action.payload.getString("destination"))
                Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=$query"))
            }
            "calendar.create" -> Intent(Intent.ACTION_INSERT).setData(CalendarContract.Events.CONTENT_URI).apply {
                putExtra(CalendarContract.Events.TITLE, action.payload.getString("title"))
                action.payload.optLong("start_millis").takeIf { it > 0 }?.let {
                    putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, it)
                }
                action.payload.optLong("end_millis").takeIf { it > 0 }?.let {
                    putExtra(CalendarContract.EXTRA_EVENT_END_TIME, it)
                }
            }
            else -> error("Unsupported action")
        }
        requireNotNull(intent.resolveActivity(packageManager)) { "실행할 앱을 찾을 수 없습니다." }
        startActivity(intent)
    }
}

@Composable
private fun JarvisApp(
    tokenStore: SecureTokenStore,
    initialServerUrl: String,
    saveServerUrl: (String) -> Unit,
    initialConversationId: Int?,
    saveConversationId: (Int?) -> Unit,
    initialTtsEnabled: Boolean,
    saveTtsEnabled: (Boolean) -> Unit,
    speak: (String) -> Unit,
    executeAction: (DeviceAction) -> Unit,
) {
    var serverUrl by remember { mutableStateOf(initialServerUrl) }
    var token by remember { mutableStateOf(tokenStore.load()) }
    if (token == null) {
        PairingScreen(serverUrl, onServerUrl = { serverUrl = it }) { name, code ->
            val api = JarvisApi(serverUrl)
            val newToken = api.pair(name, code)
            tokenStore.save(newToken)
            saveServerUrl(serverUrl)
            token = newToken
        }
    } else {
        ChatScreen(
            api = remember(token, serverUrl) { JarvisApi(serverUrl, token) },
            initialConversationId = initialConversationId,
            saveConversationId = saveConversationId,
            initialTtsEnabled = initialTtsEnabled,
            saveTtsEnabled = saveTtsEnabled,
            speak = speak,
            executeAction = executeAction,
            onUnpair = { tokenStore.clear(); token = null },
        )
    }
}

@Composable
private fun PairingScreen(
    initialUrl: String,
    onServerUrl: (String) -> Unit,
    pair: suspend (String, String) -> Unit,
) {
    var url by remember { mutableStateOf(initialUrl) }
    var name by remember { mutableStateOf("My Android") }
    var code by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    Box(Modifier.fillMaxSize().background(Color(0xFF050B12)).padding(24.dp), contentAlignment = Alignment.Center) {
        Column(Modifier.widthIn(max = 460.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Text("JARVIS", style = MaterialTheme.typography.headlineLarge, color = Color(0xFF5DD9FF), fontWeight = FontWeight.Bold)
            Text("개인 기기 연결", color = Color.White)
            OutlinedTextField(url, { url = it }, label = { Text("서버 주소") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(name, { name = it }, label = { Text("기기 이름") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(code, { code = it }, label = { Text("서버 터미널의 등록 코드") }, modifier = Modifier.fillMaxWidth())
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(
                enabled = !loading && url.isNotBlank() && code.length >= 6,
                modifier = Modifier.fillMaxWidth(),
                onClick = {
                    loading = true
                    scope.launch {
                        runCatching { withContext(Dispatchers.IO) { pair(name, code) } }
                            .onSuccess { onServerUrl(url) }
                            .onFailure { error = it.message }
                        loading = false
                    }
                },
            ) { Text(if (loading) "연결 중…" else "안전하게 연결") }
        }
    }
}

@Composable
private fun ChatScreen(
    api: JarvisApi,
    initialConversationId: Int?,
    saveConversationId: (Int?) -> Unit,
    initialTtsEnabled: Boolean,
    saveTtsEnabled: (Boolean) -> Unit,
    speak: (String) -> Unit,
    executeAction: (DeviceAction) -> Unit,
    onUnpair: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var input by remember { mutableStateOf("") }
    var conversationId by remember { mutableStateOf(initialConversationId) }
    var messages by remember { mutableStateOf(listOf<UiMessage>()) }
    var pending by remember { mutableStateOf(listOf<DeviceAction>()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var ttsEnabled by remember { mutableStateOf(initialTtsEnabled) }

    fun refreshActions() = scope.launch {
        runCatching { withContext(Dispatchers.IO) { api.pendingActions() } }
            .onSuccess { pending = it }.onFailure { error = it.message }
    }

    val speechLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            input = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull().orEmpty()
        }
    }
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            speechLauncher.launch(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.KOREAN.toLanguageTag())
            })
        }
    }

    Scaffold(
        containerColor = Color(0xFF050B12),
        topBar = {
            Surface(color = Color(0xFF0B1724)) {
                Row(Modifier.fillMaxWidth().padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("JARVIS", color = Color(0xFF5DD9FF), fontWeight = FontWeight.Bold)
                    Spacer(Modifier.weight(1f))
                    TextButton(onClick = {
                        ttsEnabled = !ttsEnabled
                        saveTtsEnabled(ttsEnabled)
                    }) { Text(if (ttsEnabled) "음성 켜짐" else "음성 꺼짐") }
                    TextButton(onClick = {
                        conversationId = null
                        saveConversationId(null)
                        messages = emptyList()
                    }) { Text("새 대화") }
                    TextButton(onClick = onUnpair) { Text("연결 해제") }
                }
            }
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).imePadding()) {
            if (pending.isNotEmpty()) {
                PendingActionCard(pending.first(), onApprove = { action ->
                    scope.launch {
                        val failure = runCatching {
                            withContext(Dispatchers.IO) { api.approve(action.id) }
                            executeAction(action)
                            withContext(Dispatchers.IO) { api.result(action.id, true, "Android intent opened") }
                        }.exceptionOrNull()
                        if (failure != null) {
                            withContext(Dispatchers.IO) {
                                runCatching { api.result(action.id, false, failure.message ?: "Android action failed") }
                            }
                            error = failure.message
                        }
                        refreshActions()
                    }
                }, onCancel = { action ->
                    scope.launch { withContext(Dispatchers.IO) { api.cancel(action.id) }; refreshActions() }
                })
            }
            LazyColumn(
                Modifier.weight(1f).fillMaxWidth().padding(horizontal = 14.dp),
                contentPadding = PaddingValues(vertical = 18.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                if (messages.isEmpty()) item { Text("무엇을 도와드릴까요?", color = Color.White, style = MaterialTheme.typography.headlineSmall) }
                items(messages) { message -> MessageBubble(message) }
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(horizontal = 16.dp)) }
            Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.Bottom) {
                OutlinedTextField(
                    input, { input = it }, placeholder = { Text("JARVIS에게 말하기") },
                    modifier = Modifier.weight(1f), maxLines = 5,
                )
                IconButton(onClick = { permissionLauncher.launch(Manifest.permission.RECORD_AUDIO) }) { Text("🎙") }
                Button(enabled = !loading && input.isNotBlank(), onClick = {
                    val text = input.trim(); input = ""; loading = true
                    messages = messages + UiMessage("user", text)
                    scope.launch {
                        val assistantIndex = messages.size
                        messages = messages + UiMessage("assistant", "")
                        runCatching {
                            withContext(Dispatchers.IO) {
                                api.chatStream(
                                    text,
                                    conversationId,
                                    onConversation = { id ->
                                        scope.launch {
                                            conversationId = id
                                            saveConversationId(id)
                                        }
                                    },
                                    onDelta = { delta ->
                                        scope.launch {
                                            val current = messages.getOrNull(assistantIndex)?.text.orEmpty()
                                            messages = messages.toMutableList().also {
                                                if (assistantIndex < it.size) it[assistantIndex] = UiMessage("assistant", current + delta)
                                            }
                                        }
                                    },
                                )
                            }
                        }
                            .onSuccess { reply ->
                                conversationId = reply.conversationId
                                saveConversationId(reply.conversationId)
                                messages = messages.toMutableList().also {
                                    if (assistantIndex < it.size) it[assistantIndex] = UiMessage("assistant", reply.text)
                                }
                                if (ttsEnabled) speak(reply.text)
                                refreshActions()
                            }.onFailure { error = it.message }
                        loading = false
                    }
                }) { Text(if (loading) "…" else "전송") }
            }
        }
    }
    LaunchedEffect(Unit) {
        initialConversationId?.let { id ->
            runCatching { withContext(Dispatchers.IO) { api.messages(id) } }
                .onSuccess { stored -> messages = stored.map { UiMessage(it.role, it.content) } }
                .onFailure {
                    conversationId = null
                    saveConversationId(null)
                }
        }
        refreshActions()
    }
}

@Composable
private fun MessageBubble(message: UiMessage) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (message.role == "user") Arrangement.End else Arrangement.Start) {
        Surface(
            color = if (message.role == "user") Color(0xFF153D55) else Color(0xFF0B1724),
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier.widthIn(max = 320.dp),
        ) { Text(message.text, color = Color.White, modifier = Modifier.padding(14.dp)) }
    }
}

@Composable
private fun PendingActionCard(
    action: DeviceAction,
    onApprove: (DeviceAction) -> Unit,
    onCancel: (DeviceAction) -> Unit,
) {
    Card(Modifier.fillMaxWidth().padding(12.dp), colors = CardDefaults.cardColors(containerColor = Color(0xFF123047))) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("실행 승인이 필요합니다", color = Color(0xFF5DD9FF), fontWeight = FontWeight.Bold)
            Text(action.title, color = Color.White)
            action.description?.let { Text(it, color = Color(0xFFB7C8D5)) }
            Row(Modifier.align(Alignment.End)) {
                TextButton(onClick = { onCancel(action) }) { Text("취소") }
                Button(onClick = { onApprove(action) }) { Text("확인 후 실행") }
            }
        }
    }
}

@Composable
private fun JarvisTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Color(0xFF5DD9FF),
            background = Color(0xFF050B12),
            surface = Color(0xFF0B1724),
        ),
        content = content,
    )
}
