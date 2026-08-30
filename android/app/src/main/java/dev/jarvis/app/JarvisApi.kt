package dev.jarvis.app

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class ChatReply(val text: String, val conversationId: Int)
data class DeviceAction(
    val id: Int,
    val type: String,
    val title: String,
    val description: String?,
    val payload: JSONObject,
)

class JarvisApi(var baseUrl: String, private var token: String? = null) {
    fun setToken(value: String) { token = value }

    private fun request(path: String, method: String = "GET", body: JSONObject? = null): String {
        val connection = URL(baseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 15_000
        connection.readTimeout = 90_000
        connection.setRequestProperty("Content-Type", "application/json")
        token?.let { connection.setRequestProperty("Authorization", "Bearer $it") }
        if (body != null) {
            connection.doOutput = true
            connection.outputStream.use { it.write(body.toString().toByteArray()) }
        }
        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) {
            val detail = runCatching { JSONObject(text).optString("detail") }.getOrNull()
            throw IllegalStateException(detail?.ifBlank { null } ?: "Server error $status")
        }
        return text
    }

    fun pair(name: String, pairingCode: String): String {
        val result = JSONObject(request("/device-registration", "POST", JSONObject()
            .put("name", name).put("pairing_code", pairingCode)))
        return result.getString("access_token").also { setToken(it) }
    }

    fun chat(message: String, conversationId: Int?): ChatReply {
        val body = JSONObject().put("message", message)
        conversationId?.let { body.put("conversation_id", it) }
        val result = JSONObject(request("/chat", "POST", body))
        return ChatReply(result.getString("reply"), result.getInt("conversation_id"))
    }

    fun pendingActions(): List<DeviceAction> {
        val array = JSONArray(request("/actions?status=pending_confirmation"))
        return (0 until array.length()).map { index ->
            val item = array.getJSONObject(index)
            DeviceAction(
                item.getInt("id"), item.getString("action_type"), item.getString("title"),
                item.optString("description").ifBlank { null }, item.getJSONObject("payload")
            )
        }
    }

    fun approve(id: Int) { request("/actions/$id/approve", "POST", JSONObject()) }
    fun cancel(id: Int) { request("/actions/$id/cancel", "POST", JSONObject()) }
    fun result(id: Int, success: Boolean, detail: String) {
        request("/actions/$id/result", "POST", JSONObject().put("success", success).put("detail", detail))
    }
}
