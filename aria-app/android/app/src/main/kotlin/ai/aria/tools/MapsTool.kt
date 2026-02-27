package ai.aria.os.tools

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import ai.aria.os.tools.base.AriaTool

/**
 * MapsTool — opens navigation to a destination in Google Maps (or any maps app).
 */
class MapsTool(private val context: Context) : AriaTool() {

    companion object {
        const val TAG = "MapsTool"
    }

    override val description = "Get directions or navigate to a destination using Google Maps. " +
        "Supports driving, walking, biking, and transit modes."

    override val inputSchema = mapOf(
        "type" to "object",
        "properties" to mapOf(
            "destination" to mapOf(
                "type" to "string",
                "description" to "Destination address or place name (e.g., '123 Main St, Chicago' or 'Starbucks')"
            ),
            "mode" to mapOf(
                "type" to "string",
                "enum" to listOf("driving", "walking", "bicycling", "transit"),
                "description" to "Transportation mode (default: driving)",
                "default" to "driving"
            ),
            "origin" to mapOf(
                "type" to "string",
                "description" to "Starting point (optional, defaults to current location)"
            )
        ),
        "required" to listOf("destination")
    )

    override suspend fun execute(input: Map<String, Any>): String {
        val destination = input.getString("destination")
        val mode = input.getString("mode", "driving")
        val origin = input.getString("origin")

        if (destination.isBlank()) return "Error: 'destination' is required"

        val modeChar = when (mode.lowercase()) {
            "walking" -> "w"
            "bicycling", "biking", "bike" -> "b"
            "transit", "bus", "train" -> "r"
            else -> "d" // driving
        }

        // Build Google Maps navigation URI
        val destEncoded = Uri.encode(destination)
        val uri = if (origin.isNotBlank()) {
            val originEncoded = Uri.encode(origin)
            "https://www.google.com/maps/dir/?api=1&origin=$originEncoded&destination=$destEncoded&travelmode=${mode.lowercase()}"
        } else {
            "google.navigation:q=$destEncoded&mode=$modeChar"
        }

        return try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(uri)).apply {
                setPackage("com.google.android.apps.maps")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }

            // Try Google Maps first, fall back to any maps app
            if (context.packageManager.resolveActivity(intent, 0) != null) {
                context.startActivity(intent)
            } else {
                // Fallback to generic geo intent
                val fallbackIntent = Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=$destEncoded")).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(fallbackIntent)
            }

            Log.i(TAG, "Opened navigation to '$destination' via $mode")
            "🗺️ Opening navigation to '$destination' (${mode.replaceFirstChar { it.uppercase() }})"
        } catch (e: Exception) {
            Log.e(TAG, "Failed to open maps", e)
            "Error opening maps: ${e.message}. Make sure Google Maps is installed."
        }
    }
}
