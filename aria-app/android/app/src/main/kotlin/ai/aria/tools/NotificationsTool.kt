package ai.aria.os.tools

import android.content.Context
import android.util.Log
import com.google.gson.Gson
import ai.aria.os.accessibility.AriaAccessibilityService
import ai.aria.os.tools.base.AriaTool

/**
 * NotificationsTool — retrieves current notifications using the Accessibility Service.
 *
 * Note: For full notification access, a NotificationListenerService would be ideal.
 * Phase 1 uses the accessibility service to read notification shade content.
 */
class NotificationsTool(private val context: Context) : AriaTool() {

    companion object {
        const val TAG = "NotificationsTool"
    }

    private val gson = Gson()

    override val description = "Get a list of current notifications on the device. " +
        "Shows app name, title, and text of active notifications."

    override val inputSchema = mapOf(
        "type" to "object",
        "properties" to mapOf(
            "limit" to mapOf(
                "type" to "integer",
                "description" to "Maximum number of notifications to return (default: 10)"
            )
        ),
        "required" to emptyList<String>()
    )

    override suspend fun execute(input: Map<String, Any>): String {
        val limit = input.getInt("limit", 10)

        val service = AriaAccessibilityService.instance
        if (service == null) {
            return "Accessibility Service is not enabled. Please go to Settings → Accessibility → Aria → Enable."
        }

        return try {
            // Open notification shade
            val opened = service.performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS)

            if (!opened) {
                return "Could not open notification shade. Make sure Aria Accessibility Service is enabled."
            }

            // Brief pause for the shade to animate open
            Thread.sleep(800)

            // Read the screen content
            val screenText = service.getScreenText()
            val snapshot = service.getScreenSnapshot()

            // Close notification shade
            service.pressBack()

            if (screenText.isBlank()) {
                return "No notifications found or could not read notification shade."
            }

            // Parse the screen text into structured notifications
            val notifications = parseNotificationText(screenText, snapshot, limit)

            if (notifications.isEmpty()) {
                "No notifications currently active."
            } else {
                "📬 Notifications (${notifications.size}):\n" +
                    notifications.joinToString("\n") { "• ${it["app"]}: ${it["text"]}" }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to get notifications", e)
            "Error reading notifications: ${e.message}"
        }
    }

    private fun parseNotificationText(
        text: String,
        snapshot: List<Map<String, String>>,
        limit: Int
    ): List<Map<String, String>> {
        val notifications = mutableListOf<Map<String, String>>()

        // Filter out system UI elements and extract meaningful notification text
        val systemKeywords = listOf(
            "clear all", "manage", "notification",
            "settings", "silence", "snooze",
            "drag down", "notifications"
        )

        val lines = text.split("\n")
            .map { it.trim() }
            .filter { line ->
                line.length > 3 &&
                    !systemKeywords.any { keyword -> line.lowercase().contains(keyword) }
            }

        // Group into chunks of 2-3 lines per notification
        var i = 0
        while (i < lines.size && notifications.size < limit) {
            val notifText = lines.drop(i).take(2).joinToString(" — ")
            if (notifText.isNotBlank()) {
                notifications.add(mapOf(
                    "app" to (lines.getOrNull(i)?.take(30) ?: "Unknown"),
                    "text" to (lines.getOrNull(i + 1) ?: notifText).take(100)
                ))
            }
            i += 2
        }

        return notifications
    }
}
