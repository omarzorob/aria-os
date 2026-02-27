"""
Aria Voice Pipeline
- Listens for wake word ("Hey Aria")
- Records until user stops speaking (VAD)
- Transcribes with Whisper (on-device)
- Speaks responses with edge-tts
"""

import asyncio
import io
import os
import tempfile
import threading
import time
import logging
import numpy as np
import sounddevice as sd
import soundfile as sf
import whisper
import edge_tts

log = logging.getLogger("aria.voice")

# ── Config ────────────────────────────────────────────────────────────────────
SAMPLE_RATE    = 16000
CHANNELS       = 1
WHISPER_MODEL  = os.environ.get("ARIA_WHISPER_MODEL", "base")
TTS_VOICE      = os.environ.get("ARIA_TTS_VOICE", "en-US-AriaNeural")
WAKE_WORD      = os.environ.get("ARIA_WAKE_WORD", "hey aria").lower()
VAD_SILENCE_S  = 1.2    # seconds of silence before stopping recording
VAD_THRESHOLD  = 0.015  # RMS threshold for speech detection
MAX_RECORD_S   = 30     # max recording length


class VoicePipeline:
    def __init__(self):
        log.info(f"Loading Whisper ({WHISPER_MODEL})...")
        self.model = whisper.load_model(WHISPER_MODEL)
        log.info("Whisper ready ✅")
        self._is_speaking = False

    # ── Wake Word Detection ───────────────────────────────────────────────────
    def detect_wake_word(self, audio_chunk: np.ndarray) -> bool:
        """Simple Whisper-based wake word detection (Phase 1).
        Phase 2 will use Porcupine for always-on efficiency."""
        try:
            result = self.model.transcribe(
                audio_chunk.astype(np.float32),
                fp16=False,
                language="en"
            )
            text = result["text"].lower().strip()
            return WAKE_WORD in text
        except Exception:
            return False

    # ── Voice Activity Detection ──────────────────────────────────────────────
    def is_speech(self, chunk: np.ndarray) -> bool:
        """Check if audio chunk contains speech via RMS energy."""
        rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2) / (32768 ** 2))
        return rms > VAD_THRESHOLD

    # ── Record Until Silence ──────────────────────────────────────────────────
    def record_utterance(self) -> np.ndarray | None:
        """Record audio until the user stops speaking. Returns audio array."""
        log.info("Listening...")
        frames = []
        silence_start = None
        start_time = time.time()
        chunk_size = int(SAMPLE_RATE * 0.1)  # 100ms chunks

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16") as stream:
            while True:
                chunk, _ = stream.read(chunk_size)
                frames.append(chunk.copy())

                if self.is_speech(chunk):
                    silence_start = None
                else:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > VAD_SILENCE_S:
                        break  # Silence long enough — done

                if time.time() - start_time > MAX_RECORD_S:
                    log.warning("Max recording time reached")
                    break

        if not frames:
            return None

        audio = np.concatenate(frames, axis=0).flatten()
        log.info(f"Recorded {len(audio) / SAMPLE_RATE:.1f}s of audio")
        return audio.astype(np.float32) / 32768.0  # normalize to [-1, 1]

    # ── Transcribe ────────────────────────────────────────────────────────────
    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio with Whisper."""
        result = self.model.transcribe(audio, fp16=False, language="en")
        text = result["text"].strip()
        log.info(f"[Heard] {text}")
        return text

    # ── Speak ─────────────────────────────────────────────────────────────────
    async def speak_async(self, text: str):
        """Convert text to speech and play it."""
        if self._is_speaking:
            return
        self._is_speaking = True
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            await edge_tts.Communicate(text, TTS_VOICE).save(tmp.name)

            data, samplerate = sf.read(tmp.name)
            sd.play(data, samplerate)
            sd.wait()
            os.unlink(tmp.name)
        except Exception as e:
            log.error(f"TTS error: {e}")
        finally:
            self._is_speaking = False

    def speak(self, text: str):
        """Synchronous wrapper for speak_async."""
        asyncio.run(self.speak_async(text))

    # ── Full Pipeline ─────────────────────────────────────────────────────────
    def listen_and_transcribe(self) -> str | None:
        """Record one utterance and return transcribed text."""
        audio = self.record_utterance()
        if audio is None or len(audio) < SAMPLE_RATE * 0.3:
            return None  # Too short — probably noise
        return self.transcribe(audio)

    def run_continuous(self, on_utterance: callable):
        """
        Continuous loop: listen → transcribe → call on_utterance(text).
        Runs in foreground. Call in a thread for non-blocking use.
        """
        log.info(f"Voice pipeline active. Say '{WAKE_WORD}' to start.")
        while True:
            try:
                text = self.listen_and_transcribe()
                if text and len(text) > 2:
                    on_utterance(text)
            except KeyboardInterrupt:
                break
            except Exception as e:
                log.error(f"Pipeline error: {e}")
                time.sleep(1)
