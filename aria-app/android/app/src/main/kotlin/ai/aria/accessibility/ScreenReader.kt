package ai.aria.os.accessibility

import android.util.Log

/**
 * ScreenReader — higher-level abstraction over AriaAccessibilityService.
 *
 * Provides structured screen content extraction for use by AI tools and the agent.
 */
object ScreenReader {

    const val TAG = "ScreenReader"

    data class ScreenContent(
        val currentApp: String,
        val windowTitle: String,
        val visibleText: String,
        val interactiveElements: List<String>
    )

    /**
     * Get a full summary of what's currently on screen.
     * Returns null if accessibility service isn't connected.
     */
    fun getScreenContent(): ScreenContent? {
        val service = AriaAccessibilityService.instance ?: run {
            Log.w(TAG, "Accessibility service not connected")
            return null
        }

        val currentApp = service.getCurrentApp()
        val windowTitle = service.getCurrentWindowTitle()
        val visibleText = service.getScreenText()
        val snapshot = service.getScreenSnapshot()
        val interactiveElements = snapshot
            .filter { it["clickable"] == "true" }
            .mapNotNull { it["text"]?.takeIf { t -> t.isNotBlank() } ?: it["description"]?.takeIf { d -> d.isNotBlank() } }

        return ScreenContent(
            currentApp = currentApp,
            windowTitle = windowTitle,
            visibleText = visibleText,
            interactiveElements = interactiveElements
        )
    }

    /**
     * Get a concise text summary of the screen for inclusion in AI context.
     */
    fun getScreenSummary(): String {
        val content = getScreenContent() ?: return "Screen reader not available (enable Accessibility Service)"
        return buildString {
            append("Current app: ${content.currentApp}\n")
            if (content.windowTitle.isNotBlank()) {
                append("Window: ${content.windowTitle}\n")
            }
            if (content.visibleText.isNotBlank()) {
                append("Visible text: ${content.visibleText.take(500)}\n")
            }
            if (content.interactiveElements.isNotEmpty()) {
                append("Buttons/links: ${content.interactiveElements.take(10).joinToString(", ")}")
            }
        }
    }
}
