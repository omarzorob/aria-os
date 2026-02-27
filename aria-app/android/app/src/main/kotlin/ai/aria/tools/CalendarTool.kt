package ai.aria.os.tools

import android.content.ContentValues
import android.content.Context
import android.provider.CalendarContract
import android.util.Log
import com.google.gson.Gson
import ai.aria.os.tools.base.AriaTool
import java.text.SimpleDateFormat
import java.util.*

/**
 * CalendarTool — reads and creates calendar events using Android's CalendarContract.
 */
class CalendarTool(private val context: Context) : AriaTool() {

    companion object {
        const val TAG = "CalendarTool"
    }

    private val gson = Gson()
    private val displayFormat = SimpleDateFormat("EEE MMM d, h:mm a", Locale.US)
    private val inputFormat = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US)

    override val description = "Get upcoming calendar events or create a new calendar event. " +
        "Use action='get' to read events, action='create' to add a new event."

    override val inputSchema = mapOf(
        "type" to "object",
        "properties" to mapOf(
            "action" to mapOf(
                "type" to "string",
                "enum" to listOf("get", "create"),
                "description" to "Whether to get events or create a new one"
            ),
            "days_ahead" to mapOf(
                "type" to "integer",
                "description" to "For 'get': number of days ahead to look (default: 7)"
            ),
            "title" to mapOf(
                "type" to "string",
                "description" to "For 'create': event title"
            ),
            "start_time" to mapOf(
                "type" to "string",
                "description" to "For 'create': start time in format 'yyyy-MM-dd HH:mm'"
            ),
            "end_time" to mapOf(
                "type" to "string",
                "description" to "For 'create': end time in format 'yyyy-MM-dd HH:mm'"
            ),
            "location" to mapOf(
                "type" to "string",
                "description" to "For 'create': event location (optional)"
            ),
            "description" to mapOf(
                "type" to "string",
                "description" to "For 'create': event description/notes (optional)"
            )
        ),
        "required" to listOf("action")
    )

    override suspend fun execute(input: Map<String, Any>): String {
        return when (input.getString("action", "get")) {
            "get" -> getEvents(input.getInt("days_ahead", 7))
            "create" -> createEvent(input)
            else -> "Error: action must be 'get' or 'create'"
        }
    }

    private fun getEvents(daysAhead: Int): String {
        val now = System.currentTimeMillis()
        val end = now + (daysAhead * 24 * 60 * 60 * 1000L)

        val events = mutableListOf<Map<String, String>>()

        val cursor = context.contentResolver.query(
            CalendarContract.Events.CONTENT_URI,
            arrayOf(
                CalendarContract.Events._ID,
                CalendarContract.Events.TITLE,
                CalendarContract.Events.DTSTART,
                CalendarContract.Events.DTEND,
                CalendarContract.Events.EVENT_LOCATION,
                CalendarContract.Events.DESCRIPTION
            ),
            "${CalendarContract.Events.DTSTART} >= ? AND ${CalendarContract.Events.DTSTART} <= ? " +
                "AND ${CalendarContract.Events.DELETED} = 0",
            arrayOf(now.toString(), end.toString()),
            "${CalendarContract.Events.DTSTART} ASC"
        )

        cursor?.use {
            val titleCol = it.getColumnIndex(CalendarContract.Events.TITLE)
            val startCol = it.getColumnIndex(CalendarContract.Events.DTSTART)
            val endCol = it.getColumnIndex(CalendarContract.Events.DTEND)
            val locationCol = it.getColumnIndex(CalendarContract.Events.EVENT_LOCATION)
            val descCol = it.getColumnIndex(CalendarContract.Events.DESCRIPTION)

            while (it.moveToNext() && events.size < 20) {
                val title = if (titleCol >= 0) it.getString(titleCol) ?: "Untitled" else "Untitled"
                val start = if (startCol >= 0) it.getLong(startCol) else 0L
                val end2 = if (endCol >= 0) it.getLong(endCol) else 0L
                val location = if (locationCol >= 0) it.getString(locationCol) ?: "" else ""
                val desc = if (descCol >= 0) it.getString(descCol) ?: "" else ""

                events.add(mapOf(
                    "title" to title,
                    "start" to displayFormat.format(Date(start)),
                    "end" to displayFormat.format(Date(end2)),
                    "location" to location,
                    "description" to desc
                ))
            }
        }

        if (events.isEmpty()) {
            return "No events found in the next $daysAhead days."
        }

        Log.d(TAG, "Found ${events.size} events")
        return gson.toJson(events)
    }

    private fun createEvent(input: Map<String, Any>): String {
        val title = input.getString("title")
        val startStr = input.getString("start_time")
        val endStr = input.getString("end_time")

        if (title.isBlank()) return "Error: 'title' is required for creating an event"
        if (startStr.isBlank()) return "Error: 'start_time' is required (format: yyyy-MM-dd HH:mm)"

        val startMs = try {
            inputFormat.parse(startStr)?.time ?: return "Error: Invalid start_time format. Use yyyy-MM-dd HH:mm"
        } catch (e: Exception) {
            return "Error parsing start_time: ${e.message}"
        }

        val endMs = if (endStr.isNotBlank()) {
            try {
                inputFormat.parse(endStr)?.time ?: (startMs + 60 * 60 * 1000L)
            } catch (e: Exception) {
                startMs + 60 * 60 * 1000L  // Default: 1 hour
            }
        } else {
            startMs + 60 * 60 * 1000L
        }

        // Get first available calendar ID
        val calId = getDefaultCalendarId() ?: return "Error: No calendar found on device"

        val values = ContentValues().apply {
            put(CalendarContract.Events.CALENDAR_ID, calId)
            put(CalendarContract.Events.TITLE, title)
            put(CalendarContract.Events.DTSTART, startMs)
            put(CalendarContract.Events.DTEND, endMs)
            put(CalendarContract.Events.EVENT_TIMEZONE, TimeZone.getDefault().id)
            val location = input.getString("location")
            if (location.isNotBlank()) put(CalendarContract.Events.EVENT_LOCATION, location)
            val description = input.getString("description")
            if (description.isNotBlank()) put(CalendarContract.Events.DESCRIPTION, description)
        }

        return try {
            val uri = context.contentResolver.insert(CalendarContract.Events.CONTENT_URI, values)
            if (uri != null) {
                Log.i(TAG, "Created event '$title' at $startStr")
                "✅ Created event: '$title' on ${displayFormat.format(Date(startMs))}" +
                    (if (input.getString("location").isNotBlank()) " at ${input.getString("location")}" else "")
            } else {
                "Error: Failed to create event (null URI returned)"
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to create event", e)
            "Error creating event: ${e.message}"
        }
    }

    private fun getDefaultCalendarId(): Long? {
        val cursor = context.contentResolver.query(
            CalendarContract.Calendars.CONTENT_URI,
            arrayOf(CalendarContract.Calendars._ID, CalendarContract.Calendars.IS_PRIMARY),
            null, null,
            "${CalendarContract.Calendars.IS_PRIMARY} DESC"
        )
        cursor?.use {
            if (it.moveToFirst()) {
                return it.getLong(0)
            }
        }
        return null
    }
}
