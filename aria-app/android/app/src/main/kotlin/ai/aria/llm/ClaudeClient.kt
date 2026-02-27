package ai.aria.os.llm

import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * ClaudeClient — OkHttp-based HTTPS client for Anthropic's Messages API.
 *
 * Handles:
 * - Serializing conversation history + tools to Anthropic's API format
 * - Parsing text and tool_use blocks from the response
 * - Proper agentic tool-result message format
 */
class ClaudeClient(private var apiKey: String) {

    companion object {
        const val TAG = "ClaudeClient"
        const val BASE_URL = "https://api.anthropic.com/v1/messages"
        const val MODEL = "claude-3-5-haiku-20241022"
        const val ANTHROPIC_VERSION = "2023-06-01"
        const val MAX_TOKENS = 1024
    }

    private val gson = Gson()

    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    fun updateApiKey(key: String) {
        apiKey = key
    }

    /**
     * Send a chat request to Claude and return the response.
     *
     * @param messages Conversation history
     * @param tools Tool schemas to pass to Claude
     * @param systemPrompt System prompt for Claude
     * @return ChatResponse with text and/or tool calls
     */
    @Throws(ClaudeException::class)
    suspend fun chat(
        messages: List<Message>,
        tools: List<Map<String, Any>> = emptyList(),
        systemPrompt: String = ""
    ): ChatResponse {
        val requestBody = buildRequestBody(messages, tools, systemPrompt)
        Log.d(TAG, "Sending request to Claude API")
        Log.v(TAG, "Request: $requestBody")

        val request = Request.Builder()
            .url(BASE_URL)
            .addHeader("x-api-key", apiKey)
            .addHeader("anthropic-version", ANTHROPIC_VERSION)
            .addHeader("content-type", "application/json")
            .post(requestBody.toRequestBody("application/json".toMediaType()))
            .build()

        val response = try {
            client.newCall(request).execute()
        } catch (e: IOException) {
            throw ClaudeException("Network error: ${e.message}", e)
        }

        val responseBody = response.body?.string() ?: throw ClaudeException("Empty response body")

        if (!response.isSuccessful) {
            Log.e(TAG, "Claude API error ${response.code}: $responseBody")
            val errorMsg = try {
                val json = JsonParser.parseString(responseBody).asJsonObject
                json.getAsJsonObject("error")?.get("message")?.asString ?: "Unknown error"
            } catch (e: Exception) {
                responseBody
            }
            throw ClaudeException("API error ${response.code}: $errorMsg")
        }

        Log.v(TAG, "Response: $responseBody")
        return parseResponse(responseBody)
    }

    /**
     * Build the JSON request body for the Anthropic Messages API.
     * Handles the complex content block format for tool use and tool results.
     */
    private fun buildRequestBody(
        messages: List<Message>,
        tools: List<Map<String, Any>>,
        systemPrompt: String
    ): String {
        val root = JsonObject()
        root.addProperty("model", MODEL)
        root.addProperty("max_tokens", MAX_TOKENS)

        if (systemPrompt.isNotBlank()) {
            root.addProperty("system", systemPrompt)
        }

        // Build messages array
        val messagesArray = JsonArray()
        for (msg in messages) {
            val msgObj = buildMessageObject(msg)
            if (msgObj != null) messagesArray.add(msgObj)
        }
        root.add("messages", messagesArray)

        // Build tools array
        if (tools.isNotEmpty()) {
            val toolsArray = JsonArray()
            for (tool in tools) {
                val toolObj = gson.toJsonTree(tool).asJsonObject
                toolsArray.add(toolObj)
            }
            root.add("tools", toolsArray)
        }

        return root.toString()
    }

    /**
     * Convert a Message to Anthropic's content block format.
     *
     * - Regular user/assistant text → { role, content: "text" }
     * - Assistant tool_use → { role: "assistant", content: [{ type: "tool_use", id, name, input }] }
     * - Tool results → { role: "user", content: [{ type: "tool_result", tool_use_id, content }] }
     */
    private fun buildMessageObject(msg: Message): JsonObject? {
        val obj = JsonObject()

        when {
            // Tool results (from user role)
            msg.toolResults != null && msg.toolResults.isNotEmpty() -> {
                obj.addProperty("role", "user")
                val contentArray = JsonArray()
                for (result in msg.toolResults) {
                    val block = JsonObject()
                    block.addProperty("type", "tool_result")
                    block.addProperty("tool_use_id", result.toolUseId)
                    block.addProperty("content", result.content)
                    contentArray.add(block)
                }
                obj.add("content", contentArray)
            }

            // Assistant with tool calls
            msg.toolCalls != null && msg.toolCalls.isNotEmpty() -> {
                obj.addProperty("role", "assistant")
                val contentArray = JsonArray()

                // Add text block if present
                if (msg.content.isNotBlank()) {
                    val textBlock = JsonObject()
                    textBlock.addProperty("type", "text")
                    textBlock.addProperty("text", msg.content)
                    contentArray.add(textBlock)
                }

                // Add tool_use blocks
                for (toolCall in msg.toolCalls) {
                    val toolBlock = JsonObject()
                    toolBlock.addProperty("type", "tool_use")
                    toolBlock.addProperty("id", toolCall.id)
                    toolBlock.addProperty("name", toolCall.name)
                    toolBlock.add("input", gson.toJsonTree(toolCall.input))
                    contentArray.add(toolBlock)
                }
                obj.add("content", contentArray)
            }

            // Regular text message
            msg.content.isNotBlank() -> {
                obj.addProperty("role", msg.role)
                obj.addProperty("content", msg.content)
            }

            else -> return null // Skip empty messages
        }

        return obj
    }

    /**
     * Parse Claude's response JSON into ChatResponse.
     * Response content[] may contain:
     * - { type: "text", text: "..." }
     * - { type: "tool_use", id: "...", name: "...", input: {...} }
     */
    private fun parseResponse(responseBody: String): ChatResponse {
        val json = JsonParser.parseString(responseBody).asJsonObject
        val contentArray = json.getAsJsonArray("content")

        var text: String? = null
        val toolCalls = mutableListOf<ToolCall>()

        for (element in contentArray) {
            val block = element.asJsonObject
            when (val type = block.get("type")?.asString) {
                "text" -> {
                    text = block.get("text")?.asString
                }
                "tool_use" -> {
                    val id = block.get("id")?.asString ?: continue
                    val name = block.get("name")?.asString ?: continue
                    val inputElement = block.get("input")
                    val input = parseToolInput(inputElement)
                    toolCalls.add(ToolCall(id = id, name = name, input = input))
                }
                else -> Log.w(TAG, "Unknown content block type: $type")
            }
        }

        Log.d(TAG, "Parsed response: text=${text?.take(100)}, toolCalls=${toolCalls.map { it.name }}")
        return ChatResponse(
            text = text,
            toolCalls = if (toolCalls.isNotEmpty()) toolCalls else null
        )
    }

    /**
     * Recursively parse a JSON element into a Map<String, Any>.
     */
    private fun parseToolInput(element: JsonElement?): Map<String, Any> {
        if (element == null || !element.isJsonObject) return emptyMap()
        return parseJsonObject(element.asJsonObject)
    }

    private fun parseJsonObject(obj: JsonObject): Map<String, Any> {
        val map = mutableMapOf<String, Any>()
        for ((key, value) in obj.entrySet()) {
            map[key] = parseJsonElement(value)
        }
        return map
    }

    private fun parseJsonElement(element: JsonElement): Any {
        return when {
            element.isJsonNull -> ""
            element.isJsonPrimitive -> {
                val prim = element.asJsonPrimitive
                when {
                    prim.isBoolean -> prim.asBoolean
                    prim.isNumber -> {
                        val num = prim.asNumber
                        if (num.toDouble() == num.toLong().toDouble()) num.toLong() else num.toDouble()
                    }
                    else -> prim.asString
                }
            }
            element.isJsonObject -> parseJsonObject(element.asJsonObject)
            element.isJsonArray -> element.asJsonArray.map { parseJsonElement(it) }
            else -> element.toString()
        }
    }
}

class ClaudeException(message: String, cause: Throwable? = null) : Exception(message, cause)
