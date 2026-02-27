package ai.aria.os.tools

import android.content.Context
import android.provider.ContactsContract
import android.util.Log
import com.google.gson.Gson
import ai.aria.os.tools.base.AriaTool

/**
 * ContactsTool — searches contacts and returns structured contact data.
 */
class ContactsTool(private val context: Context) : AriaTool() {

    companion object {
        const val TAG = "ContactsTool"
    }

    private val gson = Gson()

    override val description = "Search contacts by name or get contact details including phone number and email. " +
        "Returns a list of matching contacts."

    override val inputSchema = mapOf(
        "type" to "object",
        "properties" to mapOf(
            "query" to mapOf(
                "type" to "string",
                "description" to "Name or partial name to search for. Leave empty to get all contacts."
            ),
            "limit" to mapOf(
                "type" to "integer",
                "description" to "Maximum number of results to return (default: 5)",
                "default" to 5
            )
        ),
        "required" to listOf("query")
    )

    override suspend fun execute(input: Map<String, Any>): String {
        val query = input.getString("query")
        val limit = input.getInt("limit", 5)

        val contacts = mutableListOf<Map<String, String>>()

        // Query phone numbers
        val phoneMap = mutableMapOf<String, MutableMap<String, String>>()

        val phoneCursor = context.contentResolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            arrayOf(
                ContactsContract.CommonDataKinds.Phone.CONTACT_ID,
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                ContactsContract.CommonDataKinds.Phone.NUMBER,
                ContactsContract.CommonDataKinds.Phone.TYPE
            ),
            if (query.isNotBlank())
                "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} LIKE ?"
            else null,
            if (query.isNotBlank()) arrayOf("%$query%") else null,
            "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} ASC"
        )

        phoneCursor?.use { cursor ->
            val idCol = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.CONTACT_ID)
            val nameCol = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
            val numCol = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.NUMBER)

            while (cursor.moveToNext() && phoneMap.size < limit) {
                val id = cursor.getString(idCol)
                val name = cursor.getString(nameCol) ?: continue
                val number = cursor.getString(numCol) ?: continue

                if (!phoneMap.containsKey(id)) {
                    phoneMap[id] = mutableMapOf("name" to name, "phone" to number, "email" to "")
                }
            }
        }

        // Query emails for the found contacts
        if (phoneMap.isNotEmpty()) {
            val ids = phoneMap.keys.joinToString(",") { "?" }
            val emailCursor = context.contentResolver.query(
                ContactsContract.CommonDataKinds.Email.CONTENT_URI,
                arrayOf(
                    ContactsContract.CommonDataKinds.Email.CONTACT_ID,
                    ContactsContract.CommonDataKinds.Email.ADDRESS
                ),
                "${ContactsContract.CommonDataKinds.Email.CONTACT_ID} IN ($ids)",
                phoneMap.keys.toTypedArray(),
                null
            )
            emailCursor?.use { cursor ->
                val idCol = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Email.CONTACT_ID)
                val emailCol = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Email.ADDRESS)
                while (cursor.moveToNext()) {
                    val id = cursor.getString(idCol)
                    val email = cursor.getString(emailCol) ?: continue
                    phoneMap[id]?.set("email", email)
                }
            }
        }

        contacts.addAll(phoneMap.values)

        if (contacts.isEmpty()) {
            return if (query.isNotBlank()) {
                "No contacts found matching '$query'"
            } else {
                "No contacts found"
            }
        }

        Log.d(TAG, "Found ${contacts.size} contacts for query '$query'")
        return gson.toJson(contacts)
    }
}
