package ai.aria.os.tools

import android.content.Context
import android.media.AudioManager
import android.os.SystemClock
import android.util.Log
import android.view.KeyEvent
import ai.aria.os.tools.base.AriaTool

/**
 * MusicTool — controls media playback using AudioManager key events.
 * Works with any media app (Spotify, YouTube Music, Apple Music, etc.)
 */
class MusicTool(private val context: Context) : AriaTool() {

    companion object {
        const val TAG = "MusicTool"
    }

    private val audioManager: AudioManager =
        context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    override val description = "Control music/media playback. Supports: play, pause, next track, " +
        "previous track, stop, volume up, volume down."

    override val inputSchema = mapOf(
        "type" to "object",
        "properties" to mapOf(
            "action" to mapOf(
                "type" to "string",
                "enum" to listOf("play", "pause", "toggle", "next", "previous", "stop", "volume_up", "volume_down"),
                "description" to "Playback action to perform"
            )
        ),
        "required" to listOf("action")
    )

    override suspend fun execute(input: Map<String, Any>): String {
        val action = input.getString("action", "toggle")

        return when (action.lowercase()) {
            "play" -> {
                sendMediaKey(KeyEvent.KEYCODE_MEDIA_PLAY)
                "▶️ Playing media"
            }
            "pause" -> {
                sendMediaKey(KeyEvent.KEYCODE_MEDIA_PAUSE)
                "⏸️ Paused media"
            }
            "toggle", "play_pause" -> {
                sendMediaKey(KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE)
                "⏯️ Toggled play/pause"
            }
            "next", "skip", "forward" -> {
                sendMediaKey(KeyEvent.KEYCODE_MEDIA_NEXT)
                "⏭️ Skipped to next track"
            }
            "previous", "prev", "back" -> {
                sendMediaKey(KeyEvent.KEYCODE_MEDIA_PREVIOUS)
                "⏮️ Going to previous track"
            }
            "stop" -> {
                sendMediaKey(KeyEvent.KEYCODE_MEDIA_STOP)
                "⏹️ Stopped media"
            }
            "volume_up" -> {
                audioManager.adjustStreamVolume(
                    AudioManager.STREAM_MUSIC,
                    AudioManager.ADJUST_RAISE,
                    AudioManager.FLAG_SHOW_UI
                )
                val vol = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
                val maxVol = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                "🔊 Volume: $vol/$maxVol"
            }
            "volume_down" -> {
                audioManager.adjustStreamVolume(
                    AudioManager.STREAM_MUSIC,
                    AudioManager.ADJUST_LOWER,
                    AudioManager.FLAG_SHOW_UI
                )
                val vol = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
                val maxVol = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                "🔉 Volume: $vol/$maxVol"
            }
            else -> "Error: Unknown action '$action'. Use: play, pause, toggle, next, previous, stop, volume_up, volume_down"
        }
    }

    private fun sendMediaKey(keyCode: Int) {
        val eventTime = SystemClock.uptimeMillis()
        val downEvent = KeyEvent(eventTime, eventTime, KeyEvent.ACTION_DOWN, keyCode, 0)
        val upEvent = KeyEvent(eventTime, eventTime, KeyEvent.ACTION_UP, keyCode, 0)

        audioManager.dispatchMediaKeyEvent(downEvent)
        audioManager.dispatchMediaKeyEvent(upEvent)
        Log.d(TAG, "Sent media key: $keyCode")
    }
}
