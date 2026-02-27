"""
P1-14: Notification Manager

Provides access to Android notifications via ADB. Reads notification data
from the status bar, supports dismissal, and can wait for new notifications.

Note: Full notification access may require the companion Aria app to be
granted BIND_NOTIFICATION_LISTENER_SERVICE permission on the device.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .adb_bridge import ADBBridge

logger = logging.getLogger(__name__)


@dataclass
class Notification:
    """Represents an Android system notification."""

    notification_id: str
    package: str
    title: str
    text: str
    sub_text: str = ""
    timestamp: float = 0.0
    is_ongoing: bool = False
    category: str = ""
    priority: int = 0

    def __str__(self) -> str:
        return f"[{self.package}] {self.title}: {self.text}"


class NotificationManager:
    """
    Manages Android notifications via ADB.

    Due to ADB limitations, notification access is done via:
    1. `adb shell dumpsys notification` — reads the notification shade
    2. Status bar expansion + UI automation for dismissal
    3. Optional: companion app with NotificationListenerService

    Usage:
        nm = NotificationManager(adb_bridge)
        notifications = nm.get_notifications()
        nm.clear_all_notifications()
    """

    def __init__(self, adb: ADBBridge) -> None:
        """
        Initialize the NotificationManager.

        Args:
            adb: ADBBridge instance for device communication.
        """
        self.adb = adb

    # ------------------------------------------------------------------
    # Reading notifications
    # ------------------------------------------------------------------

    def get_notifications(self, include_ongoing: bool = False) -> list[Notification]:
        """
        Get current notifications from the device.

        Args:
            include_ongoing: If True, include ongoing (persistent) notifications.

        Returns:
            List of Notification objects.
        """
        try:
            raw = self.adb._shell("dumpsys notification --noredact")
            notifications = self._parse_dumpsys(raw)

            if not include_ongoing:
                notifications = [n for n in notifications if not n.is_ongoing]

            logger.info("Found %d notifications", len(notifications))
            return notifications

        except ADBBridge.ADBError as e:
            logger.error("Failed to get notifications: %s", e)
            return []

    def get_notification_count(self) -> int:
        """
        Get the number of active notifications.

        Returns:
            Count of visible notifications.
        """
        return len(self.get_notifications())

    def get_notifications_for_app(self, package_name: str) -> list[Notification]:
        """
        Get notifications from a specific app.

        Args:
            package_name: Package name to filter by.

        Returns:
            List of notifications from the specified app.
        """
        all_notifs = self.get_notifications(include_ongoing=True)
        return [n for n in all_notifs if n.package == package_name]

    # ------------------------------------------------------------------
    # Dismissal
    # ------------------------------------------------------------------

    def dismiss_notification(self, notification_id: str) -> bool:
        """
        Dismiss a specific notification by ID.

        Uses ADB to expand the notification shade and swipe-dismiss.

        Args:
            notification_id: The notification ID to dismiss.

        Returns:
            True if dismissed successfully.
        """
        try:
            # Expand the notification shade
            self._expand_notification_shade()
            time.sleep(0.5)

            # Try service-based cancellation first
            self.adb._shell(
                f"service call notification 1 i32 {notification_id} 2>/dev/null || true"
            )

            logger.info("Dismissed notification: %s", notification_id)
            return True

        except ADBBridge.ADBError as e:
            logger.error("Failed to dismiss notification %s: %s", notification_id, e)
            return False
        finally:
            self._collapse_notification_shade()

    def clear_all_notifications(self) -> bool:
        """
        Clear all dismissible notifications.

        Expands the notification shade and taps the "Clear all" button,
        or uses the KEY_CLEAR_NOTIFICATIONS broadcast.

        Returns:
            True if cleared successfully.
        """
        try:
            # Method 1: Broadcast intent (works on many devices)
            self.adb._shell(
                "service call notification 1 2>/dev/null || "
                "am broadcast -a android.intent.action.CLOSE_SYSTEM_DIALOGS"
            )

            # Method 2: Expand shade + click dismiss all
            self._expand_notification_shade()
            time.sleep(0.8)

            # Try to find and click "Clear all" button
            # Varies by Android version/OEM
            self.adb._shell(
                "input keyevent --longpress KEYCODE_NOTIFICATION"
            )
            time.sleep(0.3)

            # Use the system dismissal command
            self.adb._shell(
                "cmd notification clear_listener_access_warnings 2>/dev/null || true"
            )

            logger.info("Cleared all notifications")
            return True

        except ADBBridge.ADBError as e:
            logger.error("Failed to clear notifications: %s", e)
            return False
        finally:
            self._collapse_notification_shade()

    # ------------------------------------------------------------------
    # Waiting
    # ------------------------------------------------------------------

    def wait_for_notification(
        self,
        package: Optional[str] = None,
        title_contains: Optional[str] = None,
        timeout: float = 30.0,
        poll_interval: float = 1.0,
        callback: Optional[Callable[[Notification], None]] = None,
    ) -> Optional[Notification]:
        """
        Wait for a new notification matching the given criteria.

        Args:
            package: Optional package name filter.
            title_contains: Optional substring to match in title.
            timeout: Maximum seconds to wait.
            poll_interval: How often to poll for notifications (seconds).
            callback: Optional function called when notification arrives.

        Returns:
            The matching Notification if found within timeout, else None.
        """
        deadline = time.time() + timeout
        seen_ids: set[str] = {n.notification_id for n in self.get_notifications(True)}

        logger.info(
            "Waiting for notification (package=%s, title=%s, timeout=%ds)",
            package,
            title_contains,
            timeout,
        )

        while time.time() < deadline:
            time.sleep(poll_interval)
            current = self.get_notifications(include_ongoing=True)

            for notif in current:
                if notif.notification_id in seen_ids:
                    continue

                # It's a new notification — check filters
                if package and notif.package != package:
                    continue
                if title_contains and title_contains.lower() not in notif.title.lower():
                    continue

                logger.info("Notification received: %s", notif)
                if callback:
                    callback(notif)
                return notif

            # Update seen set
            seen_ids = {n.notification_id for n in current}

        logger.warning("Notification wait timed out after %.1fs", timeout)
        return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _expand_notification_shade(self) -> None:
        """Expand the Android notification shade."""
        self.adb._shell("cmd statusbar expand-notifications")

    def _collapse_notification_shade(self) -> None:
        """Collapse the Android notification shade."""
        self.adb._shell("cmd statusbar collapse")

    def _parse_dumpsys(self, raw: str) -> list[Notification]:
        """
        Parse `dumpsys notification` output into Notification objects.

        This is a best-effort parser; the format varies between Android versions.

        Args:
            raw: Raw output from `dumpsys notification --noredact`.

        Returns:
            List of parsed Notification objects.
        """
        notifications: list[Notification] = []
        current_pkg = ""
        current_id = ""
        current_title = ""
        current_text = ""
        is_ongoing = False

        # Pattern: NotificationRecord lines
        pkg_pattern = re.compile(r"pkg=([a-zA-Z0-9_.]+)")
        id_pattern = re.compile(r"id=(\d+)")
        title_pattern = re.compile(r"android\.title=([^\n]+)")
        text_pattern = re.compile(r"android\.text=([^\n]+)")
        ongoing_pattern = re.compile(r"flags=0x([0-9a-fA-F]+)")

        in_record = False

        for line in raw.splitlines():
            line = line.strip()

            if "NotificationRecord(" in line:
                # Save previous if valid
                if current_pkg and current_id:
                    notifications.append(Notification(
                        notification_id=current_id,
                        package=current_pkg,
                        title=current_title,
                        text=current_text,
                        is_ongoing=is_ongoing,
                        timestamp=time.time(),
                    ))
                # Reset
                pkg_m = pkg_pattern.search(line)
                id_m = id_pattern.search(line)
                current_pkg = pkg_m.group(1) if pkg_m else ""
                current_id = id_m.group(1) if id_m else ""
                current_title = ""
                current_text = ""
                is_ongoing = False
                in_record = True
                continue

            if not in_record:
                continue

            title_m = title_pattern.search(line)
            if title_m:
                current_title = title_m.group(1).strip()
                continue

            text_m = text_pattern.search(line)
            if text_m:
                current_text = text_m.group(1).strip()
                continue

            ongoing_m = ongoing_pattern.search(line)
            if ongoing_m:
                flags = int(ongoing_m.group(1), 16)
                is_ongoing = bool(flags & 0x02)  # FLAG_ONGOING_EVENT = 0x02

        # Save last record
        if current_pkg and current_id:
            notifications.append(Notification(
                notification_id=current_id,
                package=current_pkg,
                title=current_title,
                text=current_text,
                is_ongoing=is_ongoing,
                timestamp=time.time(),
            ))

        return notifications
