package ai.aria.os.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log

/**
 * WakeWordDetector — continuously listens for "Hey Aria" using Android SpeechRecognizer.
 *
 * Flow:
 * 1. start() — begins continuous recognition loop
 * 2. On each result, checks if it contains "aria" or "hey aria"
 * 3. If wake word detected → onWakeWordDetected() callback
 * 4. Automatically restarts recognition after each result or error
 * 5. stop() — halts the detection loop
 */
class WakeWordDetector(
    private val context: Context,
    private val onWakeWordDetected: (String) -> Unit
) {

    companion object {
        const val TAG = "WakeWord"

        val WAKE_WORDS = listOf(
            "hey aria",
            "aria",
            "ok aria",
            "hi aria",
            "hello aria"
        )
    }

    private var recognizer: SpeechRecognizer? = null
    private var isRunning = false
    private var restartDelayMs = 500L

    private val recognitionListener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
            Log.v(TAG, "Ready for speech")
        }

        override fun onBeginningOfSpeech() {
            Log.v(TAG, "Speech started")
        }

        override fun onRmsChanged(rmsdB: Float) {
            // Could be used to animate a waveform
        }

        override fun onBufferReceived(buffer: ByteArray?) {}

        override fun onEndOfSpeech() {
            Log.v(TAG, "Speech ended")
        }

        override fun onError(error: Int) {
            val errorMsg = when (error) {
                SpeechRecognizer.ERROR_AUDIO -> "audio error"
                SpeechRecognizer.ERROR_CLIENT -> "client error"
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "insufficient permissions"
                SpeechRecognizer.ERROR_NETWORK -> "network error"
                SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "network timeout"
                SpeechRecognizer.ERROR_NO_MATCH -> "no match"
                SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "recognizer busy"
                SpeechRecognizer.ERROR_SERVER -> "server error"
                SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "speech timeout"
                else -> "unknown error $error"
            }
            Log.d(TAG, "Recognition error: $errorMsg")

            // Restart after a delay (avoid tight loop on persistent errors)
            if (isRunning) {
                android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                    if (isRunning) startRecognition()
                }, restartDelayMs)
            }
        }

        override fun onResults(results: Bundle?) {
            val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION) ?: emptyList()
            Log.v(TAG, "Results: $matches")

            for (match in matches) {
                val lower = match.lowercase().trim()
                val detected = WAKE_WORDS.firstOrNull { lower.contains(it) }
                if (detected != null) {
                    Log.i(TAG, "Wake word detected: '$detected' in '$lower'")
                    onWakeWordDetected(match)
                    // Brief pause before restarting after wake word
                    if (isRunning) {
                        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                            if (isRunning) startRecognition()
                        }, 2000L)
                    }
                    return
                }
            }

            // No wake word — immediately restart
            if (isRunning) {
                android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                    if (isRunning) startRecognition()
                }, 100L)
            }
        }

        override fun onPartialResults(partialResults: Bundle?) {
            // Check partial results for faster wake word detection
            val partials = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION) ?: return
            for (partial in partials) {
                val lower = partial.lowercase().trim()
                if (WAKE_WORDS.any { lower.contains(it) }) {
                    Log.d(TAG, "Wake word in partial: $partial")
                    // Don't act on partials — wait for final result
                }
            }
        }

        override fun onEvent(eventType: Int, params: Bundle?) {}
    }

    /**
     * Start the continuous wake word detection loop.
     * Call from the main thread.
     */
    fun start() {
        if (isRunning) return
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            Log.e(TAG, "Speech recognition not available on this device")
            return
        }

        isRunning = true
        createRecognizer()
        startRecognition()
        Log.i(TAG, "Wake word detection started")
    }

    /**
     * Stop the detection loop and release resources.
     */
    fun stop() {
        isRunning = false
        recognizer?.cancel()
        recognizer?.destroy()
        recognizer = null
        Log.i(TAG, "Wake word detection stopped")
    }

    private fun createRecognizer() {
        recognizer?.destroy()
        recognizer = SpeechRecognizer.createSpeechRecognizer(context).apply {
            setRecognitionListener(recognitionListener)
        }
    }

    private fun startRecognition() {
        if (!isRunning) return

        // Recreate recognizer each time (avoids stale state on some devices)
        if (recognizer == null) createRecognizer()

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
            putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
            // Long listening window for wake word detection
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1500)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1000)
        }

        try {
            recognizer?.startListening(intent)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start recognition", e)
        }
    }
}
