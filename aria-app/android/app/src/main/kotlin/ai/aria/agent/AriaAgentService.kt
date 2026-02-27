package ai.aria.os.agent

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import androidx.lifecycle.LifecycleService
import androidx.lifecycle.lifecycleScope
import ai.aria.os.BuildConfig
import ai.aria.os.MainActivity
import ai.aria.os.llm.ClaudeClient
import ai.aria.os.llm.Message
import ai.aria.os.memory.AriaDatabase
import ai.aria.os.memory.ConversationMessage
import ai.aria.os.voice.AriaVoice
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class AriaAgentService : LifecycleService() {

    companion object {
        const val TAG = "AriaAgent"
        const val NOTIF_CHANNEL_ID = "aria_service"
        const val NOTIF_ID = 1001
        const val ACTION_SEND_MESSAGE = "ai.aria.os.SEND_MESSAGE"
        const val ACTION_START_LISTENING = "ai.aria.os.START_LISTENING"
        const val ACTION_STOP_LISTENING = "ai.aria.os.STOP_LISTENING"
        const val ACTION_REPLY = "ai.aria.os.REPLY"
        const val EXTRA_MESSAGE = "message"
    }

    private lateinit var claudeClient: ClaudeClient
    private lateinit var toolRegistry: ToolRegistry
    private lateinit var db: AriaDatabase
    private lateinit var ariaVoice: AriaVoice
    private val conversationHistory = mutableListOf<Message>()

    // Retrieve API key — first from BuildConfig (compile-time), fallback to SharedPreferences
    private fun getApiKey(): String {
        val buildKey = BuildConfig.CLAUDE_API_KEY
        if (buildKey.isNotBlank()) return buildKey
        val prefs = getSharedPreferences("aria_prefs", Context.MODE_PRIVATE)
        return prefs.getString("claude_api_key", "") ?: ""
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIF_ID, buildNotification("Aria is ready"))

        claudeClient = ClaudeClient(getApiKey())
        toolRegistry = ToolRegistry(this)
        db = AriaDatabase.getInstance(this)
        ariaVoice = AriaVoice(this)

        Log.i(TAG, "Aria Agent Service started on Android ${Build.VERSION.RELEASE} / ${Build.MODEL}")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)

        when (intent?.action) {
            ACTION_SEND_MESSAGE -> {
                val message = intent.getStringExtra(EXTRA_MESSAGE) ?: return START_STICKY
                handleUserMessage(message)
            }
            ACTION_START_LISTENING -> {
                // Voice listening is handled by WakeWordDetector / AriaVoice
                Log.d(TAG, "Start listening requested")
            }
            ACTION_STOP_LISTENING -> {
                Log.d(TAG, "Stop listening requested")
            }
        }

        return START_STICKY
    }

    private fun handleUserMessage(text: String) {
        updateNotification("Thinking...")
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                // Add to in-memory history
                conversationHistory.add(Message("user", text))

                // Persist to DB
                db.conversationDao().insert(
                    ConversationMessage(role = "user", content = text)
                )

                // First LLM call: may return tool calls
                val apiKey = getApiKey()
                if (apiKey.isBlank()) {
                    val err = "No API key configured. Please go to Aria Settings and enter your Claude API key."
                    broadcastReply(err)
                    ariaVoice.speak(err)
                    return@launch
                }

                claudeClient.updateApiKey(apiKey)

                var response = claudeClient.chat(
                    messages = conversationHistory,
                    tools = toolRegistry.getToolSchemas(),
                    systemPrompt = buildSystemPrompt()
                )

                // Agentic loop: keep processing tool calls until we get a final text response
                var loopCount = 0
                while (response.toolCalls != null && response.toolCalls!!.isNotEmpty() && loopCount < 5) {
                    loopCount++
                    Log.d(TAG, "Tool call loop $loopCount: ${response.toolCalls!!.map { it.name }}")

                    // Add assistant's tool_use turn to history
                    conversationHistory.add(
                        Message(role = "assistant", content = "", toolCalls = response.toolCalls)
                    )

                    // Execute each tool call
                    val toolResults = mutableListOf<Message.ToolResult>()
                    response.toolCalls!!.forEach { toolCall ->
                        Log.d(TAG, "Executing tool: ${toolCall.name} with input: ${toolCall.input}")
                        val tool = toolRegistry.getTool(toolCall.name)
                        val toolResult = try {
                            tool?.execute(toolCall.input) ?: "Error: Tool '${toolCall.name}' not found"
                        } catch (e: Exception) {
                            Log.e(TAG, "Tool ${toolCall.name} failed", e)
                            "Error executing ${toolCall.name}: ${e.message}"
                        }
                        toolResults.add(Message.ToolResult(toolCall.id, toolResult))
                    }

                    // Add tool results to history
                    conversationHistory.add(
                        Message(role = "user", content = "", toolResults = toolResults)
                    )

                    // Next LLM call
                    response = claudeClient.chat(
                        messages = conversationHistory,
                        tools = toolRegistry.getToolSchemas(),
                        systemPrompt = buildSystemPrompt()
                    )
                }

                // Final text response
                val reply = response.text ?: "I completed the action but have nothing more to add."
                conversationHistory.add(Message("assistant", reply))

                // Persist assistant reply
                db.conversationDao().insert(
                    ConversationMessage(role = "assistant", content = reply)
                )

                withContext(Dispatchers.Main) {
                    broadcastReply(reply)
                    ariaVoice.speak(reply)
                    updateNotification("Aria is ready")
                }

            } catch (e: Exception) {
                Log.e(TAG, "Error handling message", e)
                val err = "Sorry, I encountered an error: ${e.message}"
                withContext(Dispatchers.Main) {
                    broadcastReply(err)
                    ariaVoice.speak(err)
                    updateNotification("Aria is ready")
                }
            }
        }
    }

    private fun buildSystemPrompt(): String = """
        You are Aria, an AI assistant running natively on this Android device.
        You have direct access to the device's capabilities through tools.
        Be concise, helpful, and action-oriented.
        When the user asks you to do something, use your tools to actually do it — don't just describe how to do it.
        After using a tool, briefly confirm what you did.
        Device info: Android ${Build.VERSION.RELEASE} on ${Build.MODEL}.
        Current time: ${java.util.Date()}.
    """.trimIndent()

    private fun broadcastReply(text: String) {
        val intent = Intent(ACTION_REPLY).apply {
            putExtra("text", text)
            setPackage(packageName)
        }
        sendBroadcast(intent)
    }

    private fun updateNotification(text: String) {
        val notification = buildNotification(text)
        val nm = getSystemService(NotificationManager::class.java)
        nm.notify(NOTIF_ID, notification)
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            NOTIF_CHANNEL_ID,
            "Aria Service",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Aria AI assistant background service"
            setShowBadge(false)
        }
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(channel)
    }

    private fun buildNotification(text: String): Notification {
        val openIntent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, openIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return Notification.Builder(this, NOTIF_CHANNEL_ID)
            .setContentTitle("Aria")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    override fun onDestroy() {
        super.onDestroy()
        ariaVoice.shutdown()
        Log.i(TAG, "Aria Agent Service stopped")
    }

    override fun onBind(intent: Intent) = super.onBind(intent)
}
