"""
P2-6: Aria Wake Word Detector

Listens for "Hey Aria" or "Aria" trigger phrases to activate the assistant.
Supports two backends:
  1. Porcupine SDK — low-latency, on-device keyword detection (preferred)
  2. Simple polling — ADB-based audio transcription keyword check (fallback)

Environment variables:
    PORCUPINE_ACCESS_KEY: Picovoice Porcupine access key for SDK-based detection.

Usage:
    detector = WakeWordDetector()
    detector.start_listening(callback=lambda phrase: print(f"Heard: {phrase}"))
    # ... later ...
    detector.stop()
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DEFAULT_WAKE_WORDS = ["hey aria", "aria"]
POLLING_INTERVAL = 1.0  # Seconds between ADB transcription checks


class WakeWordDetector:
    """
    Wake word detector for Aria OS.

    Listens for configurable wake phrases and invokes a callback when detected.
    Uses Porcupine SDK if PORCUPINE_ACCESS_KEY is set; falls back to a
    simple ADB-polling approach otherwise.
    """

    def __init__(self, adb_bridge=None) -> None:
        """
        Initialize the wake word detector.

        Args:
            adb_bridge: Optional ADBBridge instance for the ADB polling backend.
                        Not required for Porcupine SDK mode.
        """
        self.adb = adb_bridge
        self._wake_words: list[str] = list(DEFAULT_WAKE_WORDS)
        self._callback: Optional[Callable[[str], None]] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._porcupine_key = os.environ.get("PORCUPINE_ACCESS_KEY", "")

        logger.info(
            "WakeWordDetector initialized (backend=%s, words=%s)",
            "porcupine" if self._porcupine_key else "adb-polling",
            self._wake_words,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_listening(self, callback: Callable[[str], None]) -> None:
        """
        Start listening for wake words in a background thread.

        Args:
            callback: Function called with the detected phrase when a wake word
                      is heard. Invoked from the background thread.

        Raises:
            RuntimeError: If the detector is already active.
        """
        if self._running:
            raise RuntimeError("WakeWordDetector is already listening. Call stop() first.")

        self._callback = callback
        self._running = True

        if self._porcupine_key:
            self._thread = threading.Thread(
                target=self._porcupine_loop,
                daemon=True,
                name="aria-wake-porcupine",
            )
        else:
            self._thread = threading.Thread(
                target=self._adb_polling_loop,
                daemon=True,
                name="aria-wake-adb-poll",
            )

        self._thread.start()
        logger.info("Wake word detection started")

    def stop(self) -> None:
        """Stop listening for wake words and terminate the background thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        logger.info("Wake word detection stopped")

    def is_active(self) -> bool:
        """
        Check whether the detector is currently listening.

        Returns:
            True if the background listener thread is running.
        """
        return self._running and self._thread is not None and self._thread.is_alive()

    def set_wake_words(self, words: list[str]) -> None:
        """
        Update the list of wake word phrases.

        Args:
            words: New list of phrases to listen for (case-insensitive).
                   Example: ["hey aria", "ok aria", "aria wake up"]
        """
        self._wake_words = [w.lower().strip() for w in words]
        logger.info("Wake words updated: %s", self._wake_words)

    # ------------------------------------------------------------------
    # Porcupine backend
    # ------------------------------------------------------------------

    def _porcupine_loop(self) -> None:
        """
        Background thread using the Porcupine SDK for keyword detection.

        Requires:
            - pvporcupine package (pip install pvporcupine)
            - PORCUPINE_ACCESS_KEY env var
            - PyAudio for microphone access
        """
        try:
            import pvporcupine  # type: ignore
            import pyaudio  # type: ignore
        except ImportError:
            logger.warning(
                "pvporcupine or pyaudio not installed — falling back to ADB polling"
            )
            self._adb_polling_loop()
            return

        porcupine = None
        pa = None
        audio_stream = None

        try:
            # Porcupine built-in keywords include "hey siri" style — we use custom if needed
            # For now use the built-in "Jarvis" or fall back to custom keyword files
            keywords = ["jarvis"]  # Closest built-in to "Hey Aria"

            porcupine = pvporcupine.create(
                access_key=self._porcupine_key,
                keywords=keywords,
            )

            pa = pyaudio.PyAudio()
            audio_stream = pa.open(
                rate=porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=porcupine.frame_length,
            )

            logger.info("Porcupine listening (keywords=%s)", keywords)

            while self._running:
                pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
                import struct
                pcm_unpacked = struct.unpack_from("h" * porcupine.frame_length, pcm)
                result = porcupine.process(pcm_unpacked)

                if result >= 0 and self._callback:
                    phrase = keywords[result] if result < len(keywords) else "aria"
                    logger.info("Wake word detected via Porcupine: %s", phrase)
                    try:
                        self._callback(phrase)
                    except Exception as cb_err:
                        logger.warning("Wake word callback error: %s", cb_err)

        except Exception as exc:
            logger.error("Porcupine error: %s — falling back to ADB polling", exc)
            self._adb_polling_loop()

        finally:
            if audio_stream:
                audio_stream.close()
            if pa:
                pa.terminate()
            if porcupine:
                porcupine.delete()

    # ------------------------------------------------------------------
    # ADB polling backend
    # ------------------------------------------------------------------

    def _adb_polling_loop(self) -> None:
        """
        Background thread that polls for wake words via ADB.

        Checks the Android clipboard, notifications, or a shared transcription
        buffer for recently spoken text containing the wake phrases.
        """
        logger.info("ADB polling wake word loop started (interval=%.1fs)", POLLING_INTERVAL)
        last_seen: str = ""

        while self._running:
            try:
                transcript = self._get_recent_transcription()
                if transcript and transcript != last_seen:
                    last_seen = transcript
                    lower = transcript.lower()
                    for phrase in self._wake_words:
                        if phrase in lower:
                            logger.info("Wake word detected via ADB poll: %s", phrase)
                            if self._callback:
                                try:
                                    self._callback(phrase)
                                except Exception as cb_err:
                                    logger.warning("Wake word callback error: %s", cb_err)
                            break  # Only fire once per transcription chunk

            except Exception as exc:
                logger.debug("ADB poll error (non-fatal): %s", exc)

            time.sleep(POLLING_INTERVAL)

        logger.info("ADB polling wake word loop stopped")

    def _get_recent_transcription(self) -> str:
        """
        Retrieve recently transcribed audio text via ADB.

        Reads from a shared file that the Aria Android app writes transcriptions
        to, or from the Android clipboard as a fallback.

        Returns:
            Recently transcribed text, or empty string if nothing new.
        """
        if self.adb is None:
            return ""

        # Try reading the Aria transcription temp file
        try:
            transcript = self.adb._shell(
                "cat /sdcard/aria_transcription.txt 2>/dev/null || echo ''"
            ).strip()
            if transcript:
                # Clear after reading so we don't re-trigger
                self.adb._shell("rm -f /sdcard/aria_transcription.txt")
                return transcript
        except Exception:
            pass

        # Fallback: check clipboard
        try:
            clip = self.adb._shell(
                "am broadcast -a aria.GET_CLIPBOARD --es result aria_clip 2>/dev/null || echo ''"
            ).strip()
            return clip
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # String representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"WakeWordDetector(active={self.is_active()}, "
            f"words={self._wake_words}, "
            f"backend={'porcupine' if self._porcupine_key else 'adb-polling'})"
        )
