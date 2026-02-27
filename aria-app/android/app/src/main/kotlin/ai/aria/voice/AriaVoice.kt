package ai.aria.os.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import java.util.Locale
import java.util.UUID

/**
 * AriaVoice — Android TextToSpeech wrapper for Aria's spoken responses.
 *
 * Features:
 * - US English voice
 * - Slightly faster speech rate (1.1x)
 * - Utterance completion callbacks
 * - Graceful handling of TTS initialization failure
 */
class AriaVoice(private val context: Context) {

    companion object {
        const val TAG = "AriaVoice"
    }

    private var tts: TextToSpeech? = null
    private var initialized = false
    private val pendingQueue = mutableListOf<String>()

    var onSpeakingStart: (() -> Unit)? = null
    var onSpeakingEnd: (() -> Unit)? = null

    init {
        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val result = tts?.setLanguage(Locale.US)
                if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                    Log.w(TAG, "US English not supported, using default")
                    tts?.language = Locale.getDefault()
                }

                // Slightly faster speech rate — feels more natural for an AI assistant
                tts?.setSpeechRate(1.1f)
                tts?.setPitch(1.0f)

                tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) {
                        Log.d(TAG, "TTS started: $utteranceId")
                        onSpeakingStart?.invoke()
                    }

                    override fun onDone(utteranceId: String?) {
                        Log.d(TAG, "TTS done: $utteranceId")
                        onSpeakingEnd?.invoke()
                    }

                    @Deprecated("Deprecated in API 21")
                    override fun onError(utteranceId: String?) {
                        Log.e(TAG, "TTS error: $utteranceId")
                        onSpeakingEnd?.invoke()
                    }

                    override fun onError(utteranceId: String?, errorCode: Int) {
                        Log.e(TAG, "TTS error $errorCode: $utteranceId")
                        onSpeakingEnd?.invoke()
                    }
                })

                initialized = true
                Log.i(TAG, "TTS initialized successfully")

                // Flush any pending utterances
                pendingQueue.forEach { text -> speakNow(text) }
                pendingQueue.clear()

            } else {
                Log.e(TAG, "TTS initialization failed with status: $status")
            }
        }
    }

    /**
     * Speak the given text aloud.
     * If TTS isn't initialized yet, queues the text.
     */
    fun speak(text: String) {
        if (!initialized) {
            Log.d(TAG, "TTS not ready, queuing: ${text.take(50)}")
            pendingQueue.add(text)
            return
        }
        speakNow(text)
    }

    private fun speakNow(text: String) {
        // Strip markdown formatting for cleaner speech
        val cleanText = text
            .replace(Regex("\\*{1,3}(.*?)\\*{1,3}"), "$1")   // bold/italic
            .replace(Regex("`{1,3}(.*?)`{1,3}"), "$1")        // code
            .replace(Regex("#+ "), "")                          // headers
            .replace(Regex("\\[(.+?)\\]\\(.+?\\)"), "$1")     // links

        val utteranceId = UUID.randomUUID().toString()
        tts?.speak(cleanText, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
        Log.d(TAG, "Speaking: ${cleanText.take(80)}")
    }

    /**
     * Stop any ongoing speech immediately.
     */
    fun stop() {
        tts?.stop()
    }

    /**
     * Check if TTS is currently speaking.
     */
    fun isSpeaking(): Boolean = tts?.isSpeaking == true

    /**
     * Release TTS resources. Call when the service is destroyed.
     */
    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        initialized = false
        Log.i(TAG, "TTS shut down")
    }
}
