package ai.aria.os.memory

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "conversation_messages")
data class ConversationMessage(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val role: String,           // "user" | "assistant" | "tool"
    val content: String,
    val timestamp: Long = System.currentTimeMillis()
)
