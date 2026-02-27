package ai.aria.os.tools

import android.content.Context
import android.database.Cursor
import android.provider.ContactsContract
import android.telephony.SmsManager
import android.util.Log
import ai.aria.os.tools.base.AriaTool

/**
 * SmsTool — sends SMS text messages using Android's SmsManager.
 * Resolves contact names to phone numbers via ContactsContract.
 */
class SmsTool(private val context: Context) : AriaTool() {

    companion object {
        const val TAG = "SmsTool"
    }

    override val description = "Send an SMS text message to a contact or phone number. " +
        "You can use a contact name (e.g., 'Mom') or a direct phone number."

    override val inputSchema = mapOf(
        "type" to "object",
        "properties" to mapOf(
            "to" to mapOf(
                "type" to "string",
                "description" to "Contact name or phone number to send the SMS to"
            ),
            "message" to mapOf(
                "type" to "string",
                "description" to "The text message content to send"
            )
        ),
        "required" to listOf("to", "message")
    )

    override suspend fun execute(input: Map<String, Any>): String {
        val to = input.getString("to")
        val message = input.getString("message")

        if (to.isBlank()) return "Error: 'to' field is required"
        if (message.isBlank()) return "Error: 'message' field is required"

        // Resolve contact name to phone number if needed
        val phoneNumber = if (to.any { it.isLetter() }) {
            resolveContact(to) ?: return "Error: Could not find contact '$to'. Please try a different name or use a phone number directly."
        } else {
            to.replace(Regex("[^0-9+]"), "")
        }

        return try {
            @Suppress("DEPRECATION")
            val smsManager = SmsManager.getDefault()
            // Split long messages automatically
            val parts = smsManager.divideMessage(message)
            smsManager.sendMultipartTextMessage(phoneNumber, null, parts, null, null)
            Log.i(TAG, "SMS sent to $phoneNumber")
            "✅ SMS sent to $to ($phoneNumber): \"${message.take(50)}${if (message.length > 50) "..." else ""}\""
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send SMS", e)
            "Error sending SMS: ${e.message}"
        }
    }

    private fun resolveContact(name: String): String? {
        val cursor: Cursor? = context.contentResolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            arrayOf(
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                ContactsContract.CommonDataKinds.Phone.NUMBER
            ),
            "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} LIKE ?",
            arrayOf("%$name%"),
            null
        )

        cursor?.use {
            if (it.moveToFirst()) {
                val number = it.getString(it.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.NUMBER))
                Log.d(TAG, "Resolved '$name' → $number")
                return number.replace(Regex("[^0-9+]"), "")
            }
        }
        return null
    }
}
