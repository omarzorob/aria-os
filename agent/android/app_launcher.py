"""
P1-12: App Launcher

Provides high-level app management: list installed apps, launch by package name
or human-readable name, get the current foreground app, close, and force-stop.

Relies on ADBBridge for device communication.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .adb_bridge import ADBBridge

logger = logging.getLogger(__name__)


@dataclass
class InstalledApp:
    """Represents an installed Android application."""

    package_name: str
    label: str = ""
    version_name: str = ""
    version_code: str = ""
    is_system: bool = False

    def __str__(self) -> str:
        label = self.label or self.package_name
        return f"{label} ({self.package_name})"


class AppLauncher:
    """
    Manages Android application launching and lifecycle via ADB.

    Usage:
        launcher = AppLauncher(adb_bridge)
        apps = launcher.list_installed_apps()
        launcher.launch_app("com.google.android.youtube")
    """

    # Common app package name aliases for natural language lookup
    WELL_KNOWN_APPS: dict[str, str] = {
        "youtube": "com.google.android.youtube",
        "chrome": "com.android.chrome",
        "google chrome": "com.android.chrome",
        "maps": "com.google.android.apps.maps",
        "google maps": "com.google.android.apps.maps",
        "gmail": "com.google.android.gm",
        "phone": "com.google.android.dialer",
        "dialer": "com.google.android.dialer",
        "messages": "com.google.android.apps.messaging",
        "sms": "com.google.android.apps.messaging",
        "camera": "com.google.android.GoogleCamera",
        "settings": "com.android.settings",
        "calculator": "com.google.android.calculator",
        "calendar": "com.google.android.calendar",
        "contacts": "com.google.android.contacts",
        "clock": "com.google.android.deskclock",
        "alarm": "com.google.android.deskclock",
        "spotify": "com.spotify.music",
        "netflix": "com.netflix.mediaclient",
        "instagram": "com.instagram.android",
        "twitter": "com.twitter.android",
        "x": "com.twitter.android",
        "facebook": "com.facebook.katana",
        "whatsapp": "com.whatsapp",
        "uber": "com.ubercabs.rider",
        "uber eats": "com.ubercabs.eats",
        "ubereats": "com.ubercabs.eats",
        "amazon": "com.amazon.mShop.android.shopping",
        "files": "com.google.android.documentsui",
        "gallery": "com.google.android.apps.photos",
        "photos": "com.google.android.apps.photos",
    }

    def __init__(self, adb: ADBBridge) -> None:
        """
        Initialize the AppLauncher.

        Args:
            adb: ADBBridge instance for device communication.
        """
        self.adb = adb
        self._app_cache: list[InstalledApp] = []
        self._cache_timestamp: float = 0

    # ------------------------------------------------------------------
    # App listing
    # ------------------------------------------------------------------

    def list_installed_apps(
        self,
        include_system: bool = False,
        use_cache: bool = False,
    ) -> list[InstalledApp]:
        """
        List all installed applications on the device.

        Args:
            include_system: If True, include system apps.
            use_cache: If True, return cached list if available.

        Returns:
            List of InstalledApp objects.
        """
        import time

        if use_cache and self._app_cache and (time.time() - self._cache_timestamp < 300):
            apps = self._app_cache
            if not include_system:
                apps = [a for a in apps if not a.is_system]
            return apps

        # Get all packages with their paths (to detect system apps)
        flag = "" if include_system else "-3"
        output = self.adb._shell(f"pm list packages {flag} -f")

        apps: list[InstalledApp] = []
        for line in output.splitlines():
            line = line.strip()
            if not line.startswith("package:"):
                continue
            # Format: package:/path/to/apk.apk=com.package.name
            parts = line[len("package:"):].rsplit("=", 1)
            if len(parts) == 2:
                apk_path, package_name = parts
                is_system = "/system/" in apk_path or "/product/" in apk_path
                apps.append(InstalledApp(
                    package_name=package_name,
                    is_system=is_system,
                ))

        self._app_cache = apps
        self._cache_timestamp = time.time()
        logger.info("Found %d installed apps", len(apps))
        return apps

    def find_app_by_name(self, name: str) -> Optional[InstalledApp]:
        """
        Find an installed app by its label or known alias.

        Args:
            name: Human-readable app name (case-insensitive).

        Returns:
            InstalledApp if found, None otherwise.
        """
        name_lower = name.lower().strip()

        # Check well-known aliases first
        if name_lower in self.WELL_KNOWN_APPS:
            package = self.WELL_KNOWN_APPS[name_lower]
            return InstalledApp(package_name=package, label=name)

        # Check against installed packages
        apps = self.list_installed_apps(include_system=True, use_cache=True)
        for app in apps:
            if name_lower in app.package_name.lower():
                return app
            if app.label and name_lower in app.label.lower():
                return app

        return None

    # ------------------------------------------------------------------
    # Launch / Close
    # ------------------------------------------------------------------

    def launch_app(
        self,
        package_name: str,
        activity: Optional[str] = None,
    ) -> bool:
        """
        Launch an app by package name.

        Args:
            package_name: Android package name (e.g., "com.android.chrome").
            activity: Optional specific activity to launch.

        Returns:
            True if launched successfully.
        """
        try:
            if activity:
                component = f"{package_name}/{activity}"
                self.adb._shell(f"am start -n {component}")
            else:
                # Launch via monkey (simulates home screen tap)
                result = self.adb._shell(
                    f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
                )
                if "error" in result.lower() and "events injected: 0" in result.lower():
                    # Fallback: use am start with main intent
                    self.adb._shell(
                        f"am start -a android.intent.action.MAIN "
                        f"-c android.intent.category.LAUNCHER "
                        f"-n $(pm resolve-activity --brief {package_name} | tail -1)"
                    )
            logger.info("Launched: %s", package_name)
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to launch %s: %s", package_name, e)
            return False

    def launch_app_by_name(self, name: str) -> bool:
        """
        Launch an app by its human-readable name.

        Args:
            name: App name (e.g., "Chrome", "YouTube", "Maps").

        Returns:
            True if found and launched.
        """
        app = self.find_app_by_name(name)
        if app:
            return self.launch_app(app.package_name)
        logger.warning("App not found: %s", name)
        return False

    def get_current_app(self) -> str:
        """
        Get the package name of the currently foreground app.

        Returns:
            Package name string, or empty string if unknown.
        """
        try:
            # API 26+ method
            output = self.adb._shell(
                "dumpsys activity activities | grep -E 'mResumedActivity|ResumedActivity'"
            )
            match = re.search(r"([a-zA-Z][a-zA-Z0-9_.]+)/", output)
            if match:
                return match.group(1)

            # Fallback: window manager
            output2 = self.adb._shell(
                "dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'"
            )
            match2 = re.search(r"([a-zA-Z][a-zA-Z0-9_.]+)/", output2)
            if match2:
                return match2.group(1)

            return ""
        except ADBBridge.ADBError as e:
            logger.error("Could not get current app: %s", e)
            return ""

    def close_app(self, package_name: str) -> bool:
        """
        Close (background) an app by sending it to the background.
        This does NOT force-stop it; it just navigates home.

        For a hard stop, use force_stop().

        Args:
            package_name: Package name to close.

        Returns:
            True if navigation to home was successful.
        """
        try:
            current = self.get_current_app()
            if current == package_name:
                self.adb.press_key(3)  # HOME
            logger.info("Closed (backgrounded): %s", package_name)
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to close %s: %s", package_name, e)
            return False

    def force_stop(self, package_name: str) -> bool:
        """
        Force-stop an application.

        Args:
            package_name: Package name to force-stop.

        Returns:
            True if force-stopped successfully.
        """
        try:
            self.adb._shell(f"am force-stop {package_name}")
            logger.info("Force-stopped: %s", package_name)
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to force-stop %s: %s", package_name, e)
            return False

    def is_app_running(self, package_name: str) -> bool:
        """
        Check whether an app is currently running.

        Args:
            package_name: Package name to check.

        Returns:
            True if the app process is active.
        """
        try:
            output = self.adb._shell(f"ps -A | grep {package_name}")
            return package_name in output
        except ADBBridge.ADBError:
            return False
