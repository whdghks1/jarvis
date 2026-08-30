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
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.text.DateFormat
import java.util.Date
import java.util.Locale

data class UiMessage(val role: String, val text: String)

class MainActivity : ComponentActivity() {
    private var textToSpeech: TextToSpeech? = null
    private var ttsReady = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = android.graphics.Color.rgb(2, 6, 11)
        window.navigationBarColor = android.graphics.Color.rgb(2, 6, 11)
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
                action.payload.optString("description").takeIf { it.isNotBlank() }?.let {
                    putExtra(CalendarContract.Events.DESCRIPTION, it)
                }
                action.payload.optString("location").takeIf { it.isNotBlank() }?.let {
                    putExtra(CalendarContract.Events.EVENT_LOCATION, it)
                }
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
        PairingScreen(serverUrl) { enteredUrl, name, code ->
            val normalizedUrl = enteredUrl.trim().trimEnd('/')
            val api = JarvisApi(normalizedUrl)
            val newToken = api.pair(name, code)
            tokenStore.save(newToken)
            serverUrl = normalizedUrl
            saveServerUrl(normalizedUrl)
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
    pair: suspend (String, String, String) -> Unit,
) {
    var url by remember { mutableStateOf(initialUrl) }
    var name by remember { mutableStateOf("My Android") }
    var code by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    Box(Modifier.fillMaxSize().background(Color(0xFF02060B))) {
        HudBackground()
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState())
                .padding(horizontal = 22.dp, vertical = 18.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                MiniCore()
                Spacer(Modifier.width(12.dp))
                Column {
                    Text("PERSONAL ASSISTANT", color = HudCyan, style = MaterialTheme.typography.labelSmall)
                    Text("JARVIS", color = HudText, fontWeight = FontWeight.SemiBold)
                }
                Spacer(Modifier.weight(1f))
                Text("●  CORE ONLINE", color = Color(0xFF62F5BC), style = MaterialTheme.typography.labelSmall)
            }

            Spacer(Modifier.height(38.dp))
            JarvisCore()
            Spacer(Modifier.height(18.dp))
            Text("NEURAL INTERFACE READY", color = HudCyan, style = MaterialTheme.typography.labelSmall)
            Text(
                "개인 기기 연결",
                color = HudText,
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Light,
                modifier = Modifier.padding(top = 8.dp),
            )
            Text(
                "보안 채널을 설정하면 이 기기에서 JARVIS를 사용할 수 있습니다.",
                color = HudMuted,
                style = MaterialTheme.typography.bodySmall,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 6.dp, bottom = 18.dp),
            )

            Surface(
                modifier = Modifier.fillMaxWidth().widthIn(max = 460.dp)
                    .border(1.dp, HudLine, RoundedCornerShape(4.dp)),
                color = Color(0xE6071B29),
                shape = RoundedCornerShape(4.dp),
            ) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(11.dp)) {
                    HudField(url, { url = it }, "SERVER ENDPOINT", "http://10.0.2.2:8000")
                    HudField(name, { name = it }, "DEVICE ID", "My Android")
                    HudField(
                        code, { code = it }, "PAIRING CODE", "서버의 등록 코드",
                        secret = true,
                    )
                    error?.let {
                        Text("LINK ERROR // $it", color = Color(0xFFFF8294), style = MaterialTheme.typography.labelSmall)
                    }
                    Button(
                        enabled = !loading && url.isNotBlank() && code.length >= 6,
                        modifier = Modifier.fillMaxWidth().height(50.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFF123C50),
                            contentColor = Color(0xFFDFFAFF),
                            disabledContainerColor = Color(0xFF0A202C),
                        ),
                        shape = RoundedCornerShape(3.dp),
                        onClick = {
                            loading = true
                            error = null
                            scope.launch {
                                runCatching { withContext(Dispatchers.IO) { pair(url, name, code) } }
                                    .onFailure { error = it.message }
                                loading = false
                            }
                        },
                    ) { Text(if (loading) "SECURE LINK INITIALIZING…" else "기기 연결  //  INITIALIZE") }
                }
            }
            Text(
                "ENCRYPTED PERSONAL CHANNEL  ·  AUTH REQUIRED",
                color = Color(0xFF476273),
                style = MaterialTheme.typography.labelSmall,
                modifier = Modifier.padding(top = 24.dp, bottom = 8.dp),
            )
        }
    }
}

private val HudCyan = Color(0xFF53DDFF)
private val HudText = Color(0xFFEFFBFF)
private val HudMuted = Color(0xFF7896A8)
private val HudLine = Color(0x4D53DDFF)

@Composable
private fun HudBackground() {
    Canvas(Modifier.fillMaxSize()) {
        drawRect(Brush.radialGradient(listOf(Color(0x332891B5), Color.Transparent), center = Offset(size.width * .72f, size.height * .24f), radius = size.width * .75f))
        val grid = 44.dp.toPx()
        var x = 0f
        while (x < size.width) { drawLine(Color(0x1053DDFF), Offset(x, 0f), Offset(x, size.height)); x += grid }
        var y = 0f
        while (y < size.height) { drawLine(Color(0x1053DDFF), Offset(0f, y), Offset(size.width, y)); y += grid }
        drawCircle(Color(0x1853DDFF), size.width * .47f, Offset(size.width * 1.04f, size.height * .23f), style = Stroke(1.dp.toPx()))
    }
}

@Composable
private fun MiniCore() {
    Box(
        Modifier.size(38.dp).border(1.dp, Color(0x9953DDFF), CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Box(Modifier.size(8.dp).background(Color(0xFFDFFAFF), CircleShape))
    }
}

@Composable
private fun JarvisCore() {
    val transition = rememberInfiniteTransition(label = "jarvis-core")
    val clockwise by transition.animateFloat(
        0f, 360f, infiniteRepeatable(tween(9000, easing = LinearEasing), RepeatMode.Restart), label = "clockwise",
    )
    val counter by transition.animateFloat(
        360f, 0f, infiniteRepeatable(tween(6000, easing = LinearEasing), RepeatMode.Restart), label = "counter",
    )
    Box(Modifier.size(148.dp), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize().rotate(clockwise)) {
            drawCircle(Color(0x4053DDFF), style = Stroke(1.dp.toPx()))
            for (angle in 0 until 360 step 24) {
                val radians = Math.toRadians(angle.toDouble())
                val center = Offset(size.width / 2, size.height / 2)
                val r1 = size.minDimension * .43f
                val r2 = size.minDimension * .49f
                drawLine(
                    HudCyan,
                    Offset(center.x + kotlin.math.cos(radians).toFloat() * r1, center.y + kotlin.math.sin(radians).toFloat() * r1),
                    Offset(center.x + kotlin.math.cos(radians).toFloat() * r2, center.y + kotlin.math.sin(radians).toFloat() * r2),
                    1.dp.toPx(),
                )
            }
        }
        Box(Modifier.size(108.dp).rotate(counter).border(1.dp, Color(0x9953DDFF), CircleShape))
        Box(
            Modifier.size(66.dp).background(
                Brush.radialGradient(listOf(Color(0x6653DDFF), Color(0xFF061925))), CircleShape,
            ).border(1.dp, Color(0xCCB6F4FF), CircleShape),
            contentAlignment = Alignment.Center,
        ) { Text("J", color = Color(0xFFDFFAFF), style = MaterialTheme.typography.headlineMedium) }
    }
}

@Composable
private fun HudField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    placeholder: String,
    secret: Boolean = false,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        placeholder = { Text(placeholder, color = Color(0xFF526F80)) },
        visualTransformation = if (secret) PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None,
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
        colors = OutlinedTextFieldDefaults.colors(
            focusedTextColor = HudText, unfocusedTextColor = HudText,
            focusedBorderColor = HudCyan, unfocusedBorderColor = HudLine,
            focusedLabelColor = HudCyan, unfocusedLabelColor = HudMuted,
            cursorColor = HudCyan,
        ),
    )
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
    var menuExpanded by remember { mutableStateOf(false) }

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

    Box(Modifier.fillMaxSize().background(Color(0xFF02060B))) {
        HudBackground()
        Scaffold(
            containerColor = Color.Transparent,
            topBar = {
                Surface(color = Color(0xE6071520), shadowElevation = 10.dp) {
                    Row(
                        Modifier.fillMaxWidth().height(70.dp).padding(horizontal = 16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        MiniCore()
                        Spacer(Modifier.width(11.dp))
                        Column {
                            Text("SECURE PERSONAL CHANNEL", color = HudCyan, style = MaterialTheme.typography.labelSmall)
                            Text("JARVIS", color = HudText, fontWeight = FontWeight.SemiBold)
                        }
                        Spacer(Modifier.weight(1f))
                        Text(
                            if (loading) "●  PROCESSING" else "●  ONLINE",
                            color = if (loading) HudCyan else Color(0xFF62F5BC),
                            style = MaterialTheme.typography.labelSmall,
                        )
                        Box {
                            TextButton(onClick = { menuExpanded = true }) {
                                Text("⋮", color = HudText, style = MaterialTheme.typography.headlineSmall)
                            }
                            DropdownMenu(
                                expanded = menuExpanded,
                                onDismissRequest = { menuExpanded = false },
                                modifier = Modifier.background(Color(0xFF081B28)),
                            ) {
                                DropdownMenuItem(
                                    text = { Text(if (ttsEnabled) "음성 응답 끄기" else "음성 응답 켜기") },
                                    onClick = {
                                        ttsEnabled = !ttsEnabled
                                        saveTtsEnabled(ttsEnabled)
                                        menuExpanded = false
                                    },
                                )
                                DropdownMenuItem(
                                    text = { Text("새 대화") },
                                    onClick = {
                                        conversationId = null
                                        saveConversationId(null)
                                        messages = emptyList()
                                        menuExpanded = false
                                    },
                                )
                                DropdownMenuItem(
                                    text = { Text("기기 연결 해제") },
                                    onClick = { menuExpanded = false; onUnpair() },
                                )
                            }
                        }
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
                if (messages.isEmpty()) item { ChatWelcome() }
                items(messages) { message -> MessageBubble(message) }
            }
                error?.let {
                    Text(
                        "SYSTEM ERROR // $it", color = Color(0xFFFF8294),
                        style = MaterialTheme.typography.labelSmall,
                        modifier = Modifier.padding(horizontal = 18.dp, vertical = 4.dp),
                    )
                }
                Surface(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 8.dp)
                        .border(1.dp, HudLine, RoundedCornerShape(4.dp)),
                    color = Color(0xF2071B29),
                    shape = RoundedCornerShape(4.dp),
                ) {
                    Row(Modifier.padding(7.dp), verticalAlignment = Alignment.Bottom) {
                        OutlinedTextField(
                            input, { input = it }, placeholder = { Text("JARVIS에게 메시지 보내기", color = HudMuted) },
                            modifier = Modifier.weight(1f), maxLines = 5,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = HudText, unfocusedTextColor = HudText,
                                focusedBorderColor = Color.Transparent, unfocusedBorderColor = Color.Transparent,
                                cursorColor = HudCyan,
                            ),
                        )
                        FilledIconButton(
                            onClick = { permissionLauncher.launch(Manifest.permission.RECORD_AUDIO) },
                            colors = IconButtonDefaults.filledIconButtonColors(containerColor = Color(0xFF0C3042)),
                        ) { Text("🎙") }
                        Spacer(Modifier.width(6.dp))
                        FilledIconButton(
                            enabled = !loading && input.isNotBlank(),
                            colors = IconButtonDefaults.filledIconButtonColors(
                                containerColor = Color(0xFF176A88), contentColor = HudText,
                            ),
                            onClick = {
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
                            },
                        ) { Text(if (loading) "…" else "↑", style = MaterialTheme.typography.titleLarge) }
                    }
                }
                Text(
                    "PRIVATE LINK  ·  RESPONSES MAY BE INACCURATE",
                    color = Color(0xFF476273), style = MaterialTheme.typography.labelSmall,
                    modifier = Modifier.align(Alignment.CenterHorizontally).padding(bottom = 7.dp),
                )
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
    val user = message.role == "user"
    Column(
        Modifier.fillMaxWidth(),
        horizontalAlignment = if (user) Alignment.End else Alignment.Start,
    ) {
        Text(
            if (user) "YOU" else "JARVIS // AI",
            color = if (user) Color(0xFF6B9AAF) else HudCyan,
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 3.dp),
        )
        Surface(
            color = if (user) Color(0xE60D4258) else Color(0xE6071D2B),
            shape = if (user) RoundedCornerShape(14.dp, 2.dp, 14.dp, 14.dp)
            else RoundedCornerShape(2.dp, 14.dp, 14.dp, 14.dp),
            modifier = Modifier.widthIn(max = 340.dp).border(
                1.dp, if (user) Color(0x6653DDFF) else HudLine,
                if (user) RoundedCornerShape(14.dp, 2.dp, 14.dp, 14.dp)
                else RoundedCornerShape(2.dp, 14.dp, 14.dp, 14.dp),
            ),
        ) { Text(message.text.ifEmpty { "분석 중…" }, color = HudText, modifier = Modifier.padding(15.dp)) }
    }
}

@Composable
private fun ChatWelcome() {
    Column(
        Modifier.fillMaxWidth().padding(top = 34.dp, bottom = 18.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        JarvisCore()
        Text(
            "NEURAL INTERFACE ACTIVE", color = HudCyan,
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.padding(top = 18.dp),
        )
        Text(
            "무엇을 도와드릴까요?", color = HudText,
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Light,
            modifier = Modifier.padding(top = 10.dp),
        )
        Text(
            "모든 시스템이 준비되었습니다.\n명령하거나 대화를 시작하세요.",
            color = HudMuted, textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 8.dp),
        )
        Row(Modifier.padding(top = 20.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            HudReadout("MEMORY", "SYNCED")
            HudReadout("VOICE", "READY")
            HudReadout("CHANNEL", "SECURE")
        }
    }
}

@Composable
private fun HudReadout(label: String, value: String) {
    Column(
        Modifier.width(94.dp).border(width = 1.dp, color = HudLine).padding(8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(label, color = Color(0xFF526F80), style = MaterialTheme.typography.labelSmall)
        Text(value, color = Color(0xFF87D9EC), style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
private fun PendingActionCard(
    action: DeviceAction,
    onApprove: (DeviceAction) -> Unit,
    onCancel: (DeviceAction) -> Unit,
) {
    Card(
        Modifier.fillMaxWidth().padding(12.dp).border(1.dp, Color(0x9953DDFF), RoundedCornerShape(4.dp)),
        colors = CardDefaults.cardColors(containerColor = Color(0xF20A2636)),
        shape = RoundedCornerShape(4.dp),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("ACTION PROTOCOL // APPROVAL REQUIRED", color = HudCyan, style = MaterialTheme.typography.labelSmall)
            Text(action.title, color = Color.White)
            action.description?.let { Text(it, color = Color(0xFFB7C8D5)) }
            Text(actionPreview(action), color = Color(0xFFD6E7F2))
            Row(Modifier.align(Alignment.End)) {
                TextButton(onClick = { onCancel(action) }) { Text("취소") }
                Button(onClick = { onApprove(action) }) { Text("확인 후 실행") }
            }
        }
    }
}

private fun actionPreview(action: DeviceAction): String = when (action.type) {
    "phone.dial" -> "전화번호: ${action.payload.optString("phone_number", "확인 필요")}"
    "navigation.open" -> "목적지: ${action.payload.optString("destination", "확인 필요")}"
    "calendar.create" -> {
        val title = action.payload.optString("title", "제목 없음")
        val start = formatDateTime(action.payload.optLong("start_millis", 0L))
        val end = formatDateTime(action.payload.optLong("end_millis", 0L))
        val location = action.payload.optString("location").takeIf { it.isNotBlank() }
        buildString {
            append("일정: $title\n시작: $start")
            if (end != "지정 안 됨") append("\n종료: $end")
            if (location != null) append("\n장소: $location")
        }
    }
    else -> "지원하지 않는 작업"
}

private fun formatDateTime(epochMillis: Long): String {
    if (epochMillis <= 0L) return "지정 안 됨"
    return DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT)
        .format(Date(epochMillis))
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
