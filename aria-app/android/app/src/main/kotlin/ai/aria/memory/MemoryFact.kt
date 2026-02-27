package ai.aria.os.memory

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "memory_facts",
    indices = [Index(value = ["key"], unique = true)]
)
data class MemoryFact(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val key: String,            // e.g. "user_name", "home_address", "favorite_music"
    val value: String,          // e.g. "Omar", "123 Main St", "hip-hop"
    val timestamp: Long = System.currentTimeMillis()
)
