package ai.aria.os.tools

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.ContactsContract
import android.util.Log
import ai.aria.os.tools.base.AriaTool

/**
 * PhoneTool — initiates phone calls using Android's ACTION_CALL intent.
 * Resolves contact names to phone numbers if needed.
 */
class PhoneTool(private val context: Context) : AriaTool() {

    companion object {
        const val TAG = "PhoneTool"
    }

    override val description = "Make a phone call to a contact or phone number. " +
        "Provide either a contact name (e.g., 'Dad') or a phone number."

    override val inputSchema = mapOf(
        "type" to "object",
        "properties" to mapOf(
            "to" to mapOf(
                "type" to "string",
                "description" to "Contact name or phone number to call"
            )
        ),
        "required" to listOf("to")
    )

    override suspend fun execute(input: Map<String, Any>): String {
        val to = input.getString("to")
        if (to.isBlank()) return "Error: 'to' field is required"

        val phoneNumber = if (to.any { it.isLetter() }) {
            resolveContact(to) ?: return "Error: Could not find contact '$to'. Please try a phone number."
        } else {
            to.replace(Regex("[^0-9+]"), "")
        }

        return try {
            val callIntent = Intent(Intent.ACTION_CALL).apply {
                data = Uri.parse("tel:$phoneNumber")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(callIntent)
            Log.i(TAG, "Calling $phoneNumber")
            "📞 Calling $to ($phoneNumber)..."
        } catch (e: SecurityException) {
            "Error: CALL_PHONE permission not granted. Please grant phone permission."
        } catch (e: Exception) {
            Log.e(TAG, "Failed to make call", e)
            "Error making call: ${e.message}"
        }
    }

    private fun resolveContact(name: String): String? {
        val cursor = context.contentResolver.query(
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
                return number.replace(Regex("[^0-9+]"), "")
            }
        }
        return null
    }
}
