package ai.aria.os.llm

/**
 * Represents a single message in a conversation with Claude.
 *
 * Roles:
 * - "user"      — human turn (or tool results)
 * - "assistant" — Claude's response (may contain tool_use blocks)
 */
data class Message(
    val role: String,
    val content: String = "",
    val toolCalls: List<ToolCall>? = null,      // assistant's tool_use blocks
    val toolResults: List<ToolResult>? = null    // user's tool_result blocks
) {
    data class ToolResult(
        val toolUseId: String,
        val content: String
    )
}

/**
 * A tool call requested by Claude.
 */
data class ToolCall(
    val id: String,
    val name: String,
    val input: Map<String, Any>
)

/**
 * The full response from a Claude API call.
 */
data class ChatResponse(
    val text: String?,
    val toolCalls: List<ToolCall>?
)
