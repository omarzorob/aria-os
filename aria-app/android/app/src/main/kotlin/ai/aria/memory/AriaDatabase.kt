package ai.aria.os.memory

import android.content.Context
import androidx.room.*
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Dao
interface ConversationDao {
    @Insert
    suspend fun insert(message: ConversationMessage): Long

    @Query("SELECT * FROM conversation_messages ORDER BY timestamp ASC")
    suspend fun getAll(): List<ConversationMessage>

    @Query("SELECT * FROM conversation_messages ORDER BY timestamp DESC LIMIT :limit")
    suspend fun getRecent(limit: Int): List<ConversationMessage>

    @Query("DELETE FROM conversation_messages")
    suspend fun deleteAll()

    @Query("DELETE FROM conversation_messages WHERE id NOT IN (SELECT id FROM conversation_messages ORDER BY timestamp DESC LIMIT :keepCount)")
    suspend fun pruneOld(keepCount: Int)

    @Query("SELECT COUNT(*) FROM conversation_messages")
    suspend fun count(): Int
}

@Dao
interface MemoryDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(fact: MemoryFact): Long

    @Update
    suspend fun update(fact: MemoryFact)

    @Query("SELECT * FROM memory_facts ORDER BY timestamp DESC")
    suspend fun getAll(): List<MemoryFact>

    @Query("SELECT * FROM memory_facts WHERE `key` = :key LIMIT 1")
    suspend fun getByKey(key: String): MemoryFact?

    @Query("DELETE FROM memory_facts")
    suspend fun deleteAll()

    @Delete
    suspend fun delete(fact: MemoryFact)
}

@Database(
    entities = [ConversationMessage::class, MemoryFact::class],
    version = 1,
    exportSchema = false
)
abstract class AriaDatabase : RoomDatabase() {

    abstract fun conversationDao(): ConversationDao
    abstract fun memoryDao(): MemoryDao

    companion object {
        private const val DB_NAME = "aria_database"

        @Volatile
        private var instance: AriaDatabase? = null

        fun getInstance(context: Context): AriaDatabase {
            return instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    AriaDatabase::class.java,
                    DB_NAME
                )
                    .fallbackToDestructiveMigration()
                    .build()
                    .also { instance = it }
            }
        }
    }
}
