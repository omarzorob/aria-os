package ai.aria.os.tools.base

/**
 * AriaTool — base class for all Aria Android tools.
 *
 * Each tool maps to a Claude tool schema and implements the actual Android API call.
 *
 * Convention:
 * - description: 1-2 sentence description for Claude to understand when to use the tool
 * - inputSchema: JSON Schema object (Claude's "input_schema" format)
 * - execute: coroutine that runs the action and returns a result string
 */
abstract class AriaTool {

    /** Human-readable description for Claude */
    abstract val description: String

    /**
     * JSON Schema for tool inputs.
     * Format: { type: "object", properties: { ... }, required: [...] }
     */
    abstract val inputSchema: Map<String, Any>

    /**
     * Execute the tool with the given input map.
     * @param input Key-value pairs from Claude's tool call
     * @return Plain text or JSON string describing the result
     */
    abstract suspend fun execute(input: Map<String, Any>): String

    /** Helper: safely get a string parameter */
    protected fun Map<String, Any>.getString(key: String, default: String = ""): String {
        return this[key]?.toString() ?: default
    }

    /** Helper: safely get an int parameter */
    protected fun Map<String, Any>.getInt(key: String, default: Int = 0): Int {
        return when (val v = this[key]) {
            is Number -> v.toInt()
            is String -> v.toIntOrNull() ?: default
            else -> default
        }
    }

    /** Helper: safely get a long parameter */
    protected fun Map<String, Any>.getLong(key: String, default: Long = 0L): Long {
        return when (val v = this[key]) {
            is Number -> v.toLong()
            is String -> v.toLongOrNull() ?: default
            else -> default
        }
    }

    /** Helper: safely get a boolean parameter */
    protected fun Map<String, Any>.getBool(key: String, default: Boolean = false): Boolean {
        return when (val v = this[key]) {
            is Boolean -> v
            is String -> v.lowercase() == "true"
            else -> default
        }
    }
}
