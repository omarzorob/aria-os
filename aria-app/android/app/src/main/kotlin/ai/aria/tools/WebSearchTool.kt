package ai.aria.os.tools

import android.content.Context
import android.util.Log
import com.google.gson.JsonParser
import ai.aria.os.tools.base.AriaTool
import okhttp3.OkHttpClient
import okhttp3.Request
import java.net.URLEncoder

/**
 * WebSearchTool — searches the web using DuckDuckGo's Instant Answer API (no API key needed).
 * Returns the abstract/summary and top related topics.
 */
class WebSearchTool(private val context: Context) : AriaTool() {

    companion object {
        const val TAG = "WebSearchTool"
        const val DDG_API = "https://api.duckduckgo.com/"
    }

    private val client = OkHttpClient()

    override val description = "Search the web for information and get a summarized answer. " +
        "Uses DuckDuckGo. Good for facts, news, and quick lookups."

    override val inputSchema = mapOf(
        "type" to "object",
        "properties" to mapOf(
            "query" to mapOf(
                "type" to "string",
                "description" to "Search query"
            )
        ),
        "required" to listOf("query")
    )

    override suspend fun execute(input: Map<String, Any>): String {
        val query = input.getString("query")
        if (query.isBlank()) return "Error: 'query' is required"

        val encodedQuery = URLEncoder.encode(query, "UTF-8")
        val url = "$DDG_API?q=$encodedQuery&format=json&no_html=1&skip_disambig=1"

        return try {
            val request = Request.Builder()
                .url(url)
                .addHeader("User-Agent", "Aria-OS/0.1")
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: return "Error: Empty search response"

            if (!response.isSuccessful) {
                return "Search failed with status ${response.code}"
            }

            parseSearchResponse(body, query)
        } catch (e: Exception) {
            Log.e(TAG, "Search failed", e)
            "Error performing search: ${e.message}"
        }
    }

    private fun parseSearchResponse(body: String, query: String): String {
        return try {
            val json = JsonParser.parseString(body).asJsonObject

            val sb = StringBuilder()
            sb.append("🔍 Search results for: \"$query\"\n\n")

            // Abstract (main answer)
            val abstract = json.get("Abstract")?.asString ?: ""
            val abstractText = json.get("AbstractText")?.asString ?: ""
            val abstractSource = json.get("AbstractSource")?.asString ?: ""
            val abstractUrl = json.get("AbstractURL")?.asString ?: ""

            if (abstractText.isNotBlank()) {
                sb.append("**$abstractSource:** $abstractText\n")
                if (abstractUrl.isNotBlank()) sb.append("Source: $abstractUrl\n")
                sb.append("\n")
            }

            // Answer (instant answer)
            val answer = json.get("Answer")?.asString ?: ""
            if (answer.isNotBlank()) {
                sb.append("**Answer:** $answer\n\n")
            }

            // Definition
            val definition = json.get("Definition")?.asString ?: ""
            val definitionSource = json.get("DefinitionSource")?.asString ?: ""
            if (definition.isNotBlank()) {
                sb.append("**Definition ($definitionSource):** $definition\n\n")
            }

            // Related topics
            val relatedTopics = json.getAsJsonArray("RelatedTopics")
            if (relatedTopics != null && relatedTopics.size() > 0) {
                val topics = mutableListOf<String>()
                for (topicElement in relatedTopics) {
                    if (topics.size >= 5) break
                    val topic = topicElement.asJsonObject
                    val text = topic.get("Text")?.asString
                    if (!text.isNullOrBlank()) {
                        topics.add(text.take(100))
                    }
                }
                if (topics.isNotEmpty()) {
                    sb.append("**Related:**\n")
                    topics.forEach { sb.append("• $it\n") }
                }
            }

            val result = sb.toString().trim()
            if (result.length <= 30) {
                // No useful data from DDG — suggest a browser search
                "No direct answer found for \"$query\". Try asking me to search in the browser instead."
            } else {
                result
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to parse search response", e)
            "Error parsing search results: ${e.message}"
        }
    }
}
