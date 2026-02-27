package ai.aria.os.tools

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import ai.aria.os.tools.base.AriaTool

/**
 * BrowserTool — opens URLs in the device's default browser.
 */
class BrowserTool(private val context: Context) : AriaTool() {

    companion object {
        const val TAG = "BrowserTool"
    }

    override val description = "Open a URL or website in the device's browser. " +
        "Can also perform a web search by passing a search query as the URL."

    override val inputSchema = mapOf(
        "type" to "object",
        "properties" to mapOf(
            "url" to mapOf(
                "type" to "string",
                "description" to "URL to open (e.g., 'https://google.com') or a search query"
            )
        ),
        "required" to listOf("url")
    )

    override suspend fun execute(input: Map<String, Any>): String {
        var url = input.getString("url")
        if (url.isBlank()) return "Error: 'url' is required"

        // Auto-add https:// if missing
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            // Looks like a search query
            url = if (url.contains(".") && !url.contains(" ")) {
                "https://$url"
            } else {
                "https://www.google.com/search?q=${Uri.encode(url)}"
            }
        }

        return try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            Log.i(TAG, "Opened browser: $url")
            "✅ Opened browser: $url"
        } catch (e: Exception) {
            Log.e(TAG, "Failed to open browser", e)
            "Error opening browser: ${e.message}"
        }
    }
}
