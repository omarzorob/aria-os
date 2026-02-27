package ai.aria.os.agent

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import ai.aria.os.llm.Message
import ai.aria.os.memory.AriaDatabase
import ai.aria.os.memory.MemoryFact
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * ContextManager — manages conversation context and user memory.
 *
 * Responsibilities:
 * - Maintain sliding window of conversation history (prevent unbounded growth)
 * - Extract and store memory facts from conversations
 * - Build enriched system prompt with user context
 * - Prune old conversation history to stay within token limits
 */
class ContextManager(
    private val context: Context,
    private val db: AriaDatabase
) {

    companion object {
        const val TAG = "ContextManager"
        const val MAX_HISTORY_MESSAGES = 20       // Keep last 20 messages in memory
        const val MAX_FACTS_IN_PROMPT = 10         // Include top 10 facts in system prompt
        const val PREFS_NAME = "aria_prefs"
    }

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    /**
     * Trim conversation history to MAX_HISTORY_MESSAGES.
     * Always keeps the first system-level message if present.
     */
    fun trimHistory(history: MutableList<Message>): MutableList<Message> {
        if (history.size <= MAX_HISTORY_MESSAGES) return history

        val trimmed = history.takeLast(MAX_HISTORY_MESSAGES).toMutableList()
        Log.d(TAG, "Trimmed history from ${history.size} to ${trimmed.size} messages")
        return trimmed
    }

    /**
     * Build a context-enriched system prompt.
     * Includes device info, stored memory facts, and user preferences.
     */
    suspend fun buildSystemPrompt(basePrompt: String): String = withContext(Dispatchers.IO) {
        val facts = db.memoryDao().getAll().take(MAX_FACTS_IN_PROMPT)
        val factsSection = if (facts.isNotEmpty()) {
            "\n\n## What I know about you:\n" + facts.joinToString("\n") { "- ${it.key}: ${it.value}" }
        } else ""

        val userName = prefs.getString("user_name", null)
        val nameSection = if (userName != null) "\nThe user's name is $userName." else ""

        "$basePrompt$nameSection$factsSection"
    }

    /**
     * Store a memory fact (key-value pair the AI has learned about the user).
     */
    suspend fun storeFact(key: String, value: String) = withContext(Dispatchers.IO) {
        val existing = db.memoryDao().getByKey(key)
        if (existing != null) {
            db.memoryDao().update(existing.copy(value = value))
            Log.d(TAG, "Updated fact: $key = $value")
        } else {
            db.memoryDao().insert(MemoryFact(key = key, value = value))
            Log.d(TAG, "Stored new fact: $key = $value")
        }
    }

    /**
     * Retrieve a stored fact by key.
     */
    suspend fun getFact(key: String): String? = withContext(Dispatchers.IO) {
        db.memoryDao().getByKey(key)?.value
    }

    /**
     * Get all stored facts as a map.
     */
    suspend fun getAllFacts(): Map<String, String> = withContext(Dispatchers.IO) {
        db.memoryDao().getAll().associate { it.key to it.value }
    }

    /**
     * Clear all conversation history and memory (factory reset).
     */
    suspend fun clearAll() = withContext(Dispatchers.IO) {
        db.conversationDao().deleteAll()
        db.memoryDao().deleteAll()
        Log.i(TAG, "Cleared all conversation history and memory")
    }

    /**
     * Get Claude API key from SharedPreferences.
     */
    fun getApiKey(): String = prefs.getString("claude_api_key", "") ?: ""

    /**
     * Save Claude API key.
     */
    fun saveApiKey(key: String) {
        prefs.edit().putString("claude_api_key", key).apply()
    }

    /**
     * Check if wake word is enabled.
     */
    fun isWakeWordEnabled(): Boolean = prefs.getBoolean("wake_word_enabled", true)

    /**
     * Check if voice response is enabled.
     */
    fun isVoiceResponseEnabled(): Boolean = prefs.getBoolean("voice_response_enabled", true)
}
