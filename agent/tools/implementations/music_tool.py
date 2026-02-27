"""
P1-27: Music Tool

Controls music playback on Android via ADB media keys, Spotify deep links,
and YouTube Music intents. Supports play, pause, skip, volume, and track info.

Supported apps:
- Spotify (com.spotify.music) — primary
- YouTube Music (com.google.android.apps.youtube.music) — fallback

Environment variables:
- MUSIC_APP: "spotify" or "youtube_music" (default: "spotify")
- SPOTIFY_CLIENT_ID: Optional Spotify Web API key for search
- SPOTIFY_CLIENT_SECRET: Optional Spotify Web API key
"""

from __future__ import annotations

import logging
import os
import time
import urllib.parse
from dataclasses import dataclass
from typing import Optional

from agent.android.adb_bridge import ADBBridge

logger = logging.getLogger(__name__)

SPOTIFY_PACKAGE = "com.spotify.music"
YOUTUBE_MUSIC_PACKAGE = "com.google.android.apps.youtube.music"

# Android media keycodes
KEYCODE_MEDIA_PLAY = 126
KEYCODE_MEDIA_PAUSE = 127
KEYCODE_MEDIA_PLAY_PAUSE = 85
KEYCODE_MEDIA_STOP = 86
KEYCODE_MEDIA_NEXT = 87
KEYCODE_MEDIA_PREVIOUS = 88
KEYCODE_VOLUME_UP = 24
KEYCODE_VOLUME_DOWN = 25
KEYCODE_VOLUME_MUTE = 164


@dataclass
class Track:
    """Represents a music track."""

    title: str
    artist: str
    album: str = ""
    duration_ms: int = 0
    is_playing: bool = False
    progress_ms: int = 0

    def __str__(self) -> str:
        return f"🎵 {self.title} — {self.artist}"

    @property
    def duration_str(self) -> str:
        if not self.duration_ms:
            return "--:--"
        total_sec = self.duration_ms // 1000
        return f"{total_sec // 60}:{total_sec % 60:02d}"

    @property
    def progress_str(self) -> str:
        if not self.progress_ms:
            return "0:00"
        total_sec = self.progress_ms // 1000
        return f"{total_sec // 60}:{total_sec % 60:02d}"


class MusicTool:
    """
    Music playback control tool for Android.

    Controls Spotify/YouTube Music via ADB media intents and keys.

    Usage:
        music = MusicTool(adb_bridge)
        music.play("lo-fi hip hop")
        music.set_volume(70)
        track = music.get_current_track()
    """

    def __init__(self, adb: ADBBridge) -> None:
        """
        Initialize the MusicTool.

        Args:
            adb: ADBBridge instance.
        """
        self.adb = adb
        self.preferred_app = os.environ.get("MUSIC_APP", "spotify").lower()

    @property
    def _package(self) -> str:
        """Return the active music app package name."""
        return SPOTIFY_PACKAGE if self.preferred_app == "spotify" else YOUTUBE_MUSIC_PACKAGE

    def play(self, query: Optional[str] = None) -> bool:
        """
        Start or resume music playback.

        If query is provided, searches for and plays the track/artist/playlist.
        If no query, resumes current playback.

        Args:
            query: Optional search query (song name, artist, playlist).

        Returns:
            True if playback was initiated.
        """
        try:
            if query:
                return self._play_query(query)
            else:
                self.adb.press_key(KEYCODE_MEDIA_PLAY)
                logger.info("Resumed playback")
                return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to play: %s", e)
            return False

    def pause(self) -> bool:
        """
        Pause music playback.

        Returns:
            True if pause command was sent.
        """
        try:
            self.adb.press_key(KEYCODE_MEDIA_PAUSE)
            logger.info("Paused playback")
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to pause: %s", e)
            return False

    def resume(self) -> bool:
        """
        Resume paused playback.

        Returns:
            True if resume command was sent.
        """
        return self.play()

    def toggle_play_pause(self) -> bool:
        """Toggle between play and pause."""
        try:
            self.adb.press_key(KEYCODE_MEDIA_PLAY_PAUSE)
            return True
        except ADBBridge.ADBError:
            return False

    def skip(self) -> bool:
        """
        Skip to the next track.

        Returns:
            True if skip command was sent.
        """
        try:
            self.adb.press_key(KEYCODE_MEDIA_NEXT)
            logger.info("Skipped to next track")
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to skip: %s", e)
            return False

    def previous(self) -> bool:
        """
        Go back to the previous track.

        Returns:
            True if previous command was sent.
        """
        try:
            self.adb.press_key(KEYCODE_MEDIA_PREVIOUS)
            logger.info("Previous track")
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to go previous: %s", e)
            return False

    def stop(self) -> bool:
        """Stop music playback."""
        try:
            self.adb.press_key(KEYCODE_MEDIA_STOP)
            return True
        except ADBBridge.ADBError:
            return False

    def set_volume(self, level: int) -> bool:
        """
        Set the media volume level.

        Args:
            level: Volume level (0-100).

        Returns:
            True if volume was set.
        """
        try:
            level = max(0, min(100, level))
            # Get max volume steps (usually 15 for media)
            max_volume_output = self.adb._shell(
                "media volume --get --stream 3 2>/dev/null || echo '15'"
            )
            # Parse max volume
            max_vol = 15  # Default Android media stream max
            import re
            match = re.search(r"max=(\d+)", max_volume_output)
            if match:
                max_vol = int(match.group(1))

            target_steps = int(level * max_vol / 100)

            # Use media volume command (Android 6+)
            self.adb._shell(f"media volume --set {target_steps} --stream 3")
            logger.info("Volume set to %d%% (%d/%d steps)", level, target_steps, max_vol)
            return True

        except ADBBridge.ADBError as e:
            logger.error("Failed to set volume: %s", e)
            # Fallback: use key events
            return self._set_volume_keyevent(level)

    def get_current_track(self) -> Optional[Track]:
        """
        Get information about the currently playing track.

        Returns:
            Track object if music is playing, else None.
        """
        try:
            # Try dumpsys media_session
            output = self.adb._shell(
                "dumpsys media_session | grep -A 20 'MediaSession' | head -25"
            )

            # Parse metadata
            title = self._extract_field(output, "title")
            artist = self._extract_field(output, "artist")
            album = self._extract_field(output, "album")

            if title:
                return Track(
                    title=title,
                    artist=artist or "Unknown Artist",
                    album=album or "",
                    is_playing="STATE_PLAYING" in output,
                )

            # Fallback: try to read from notification shade
            output2 = self.adb._shell(
                "dumpsys notification --noredact | grep -i 'music\\|spotify\\|playing' | head -5"
            )
            if output2:
                return Track(
                    title="Unknown",
                    artist="Unknown",
                    is_playing=True,
                )

            return None

        except ADBBridge.ADBError as e:
            logger.error("Failed to get current track: %s", e)
            return None

    def mute(self) -> bool:
        """Mute audio."""
        try:
            self.adb.press_key(KEYCODE_VOLUME_MUTE)
            return True
        except ADBBridge.ADBError:
            return False

    def get_volume(self) -> int:
        """
        Get current media volume level (0-100).

        Returns:
            Volume percentage.
        """
        try:
            output = self.adb._shell("media volume --get --stream 3 2>/dev/null")
            import re
            match = re.search(r"volume=(\d+).*?max=(\d+)", output)
            if match:
                vol, max_vol = int(match.group(1)), int(match.group(2))
                return int(vol * 100 / max_vol)
            return -1
        except ADBBridge.ADBError:
            return -1

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _play_query(self, query: str) -> bool:
        """Play a specific track/artist/playlist by query."""
        if self.preferred_app == "spotify":
            return self._play_spotify(query)
        else:
            return self._play_youtube_music(query)

    def _play_spotify(self, query: str) -> bool:
        """Search and play via Spotify deep link."""
        try:
            enc_query = urllib.parse.quote(query)
            # Open Spotify search
            self.adb._shell(
                f"am start -a android.intent.action.VIEW "
                f"-d 'spotify:search:{enc_query}' "
                f"-p {SPOTIFY_PACKAGE}"
            )
            time.sleep(1.5)
            # Press enter/first result
            self.adb.press_key("KEYCODE_DPAD_DOWN")
            time.sleep(0.3)
            self.adb.press_key("KEYCODE_ENTER")
            logger.info("Playing Spotify: %s", query)
            return True
        except ADBBridge.ADBError as e:
            logger.error("Spotify play failed: %s", e)
            return False

    def _play_youtube_music(self, query: str) -> bool:
        """Search and play via YouTube Music."""
        try:
            enc_query = urllib.parse.quote(query)
            self.adb._shell(
                f"am start -a android.intent.action.SEARCH "
                f"-p {YOUTUBE_MUSIC_PACKAGE} "
                f"--es query '{enc_query}'"
            )
            time.sleep(1.5)
            self.adb.press_key("KEYCODE_DPAD_DOWN")
            self.adb.press_key("KEYCODE_ENTER")
            logger.info("Playing YouTube Music: %s", query)
            return True
        except ADBBridge.ADBError as e:
            logger.error("YouTube Music play failed: %s", e)
            return False

    def _set_volume_keyevent_relative(self, direction: str, steps: int) -> bool:
        """Adjust volume up or down using keyevent."""
        key = KEYCODE_VOLUME_UP if direction == "up" else KEYCODE_VOLUME_DOWN
        for _ in range(steps):
            self.adb.press_key(key)
            time.sleep(0.05)
        return True

    def _set_volume_keyevent(self, target_percent: int) -> bool:
        """Set volume via key events by pressing volume up/down repeatedly."""
        try:
            current = self.get_volume()
            if current < 0:
                # Press up to max first, then adjust
                for _ in range(20):
                    self.adb.press_key(KEYCODE_VOLUME_DOWN)
                steps = int(target_percent / 7)  # ~7% per step
                for _ in range(steps):
                    self.adb.press_key(KEYCODE_VOLUME_UP)
            else:
                diff = target_percent - current
                if diff > 0:
                    steps = max(1, abs(diff) // 7)
                    for _ in range(steps):
                        self.adb.press_key(KEYCODE_VOLUME_UP)
                        time.sleep(0.05)
                else:
                    steps = max(1, abs(diff) // 7)
                    for _ in range(steps):
                        self.adb.press_key(KEYCODE_VOLUME_DOWN)
                        time.sleep(0.05)
            return True
        except ADBBridge.ADBError:
            return False

    def _extract_field(self, text: str, field: str) -> str:
        """Extract a field value from dumpsys output."""
        import re
        pattern = rf"{field}[=:\s]+([^\n]+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().strip('"').strip("'")
        return ""
