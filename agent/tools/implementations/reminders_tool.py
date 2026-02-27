"""
P1-20: Reminders Tool

Provides alarm, timer, and reminder management via ADB.
Sets alarms in the Clock app, creates timers, and manages reminders.

Uses ADB alarm intents and content provider for clock apps.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from agent.android.adb_bridge import ADBBridge

logger = logging.getLogger(__name__)

ALARMS_URI = "content://com.android.deskclock/alarms"


@dataclass
class Alarm:
    """Represents a device alarm."""

    alarm_id: str
    hour: int
    minutes: int
    enabled: bool
    label: str = ""
    days_of_week: int = 0  # Bitmask: 0x01=Mon, 0x02=Tue, ..., 0x40=Sun
    vibrate: bool = True

    @property
    def time_str(self) -> str:
        return f"{self.hour:02d}:{self.minutes:02d}"

    def __str__(self) -> str:
        label = f" — {self.label}" if self.label else ""
        status = "ON" if self.enabled else "OFF"
        return f"Alarm {self.time_str} [{status}]{label}"


class RemindersTool:
    """
    Alarm and reminder management tool for Android.

    Usage:
        reminders = RemindersTool(adb_bridge)
        reminders.set_alarm("07:30", "Wake up")
        reminders.set_timer(300, "Pasta timer")
    """

    def __init__(self, adb: ADBBridge) -> None:
        """
        Initialize the RemindersTool.

        Args:
            adb: ADBBridge instance.
        """
        self.adb = adb

    def set_alarm(
        self,
        time_str: str,
        label: str = "",
        days: Optional[list[str]] = None,
        vibrate: bool = True,
        skip_ui: bool = False,
    ) -> bool:
        """
        Set an alarm.

        Args:
            time_str: Time in "HH:MM" or "H:MM AM/PM" format.
            label: Optional alarm label.
            days: Optional list of day names ["Monday", "Tuesday", ...].
            vibrate: Whether to vibrate when alarm fires.
            skip_ui: If True, set alarm silently without showing Clock UI.

        Returns:
            True if alarm was set.
        """
        try:
            hour, minute = self._parse_time(time_str)

            if skip_ui:
                return self._set_alarm_content_provider(hour, minute, label, vibrate)
            else:
                return self._set_alarm_intent(hour, minute, label, skip_ui=False)

        except (ValueError, ADBBridge.ADBError) as e:
            logger.error("Failed to set alarm for %s: %s", time_str, e)
            return False

    def cancel_alarm(self, alarm_id: str) -> bool:
        """
        Cancel an alarm by ID.

        Args:
            alarm_id: The alarm's database ID.

        Returns:
            True if cancelled.
        """
        try:
            self.adb._shell(
                f"content delete --uri {ALARMS_URI}/{alarm_id}"
            )
            logger.info("Cancelled alarm: %s", alarm_id)
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to cancel alarm %s: %s", alarm_id, e)
            return False

    def set_timer(self, seconds: int, label: str = "") -> bool:
        """
        Start a countdown timer.

        Args:
            seconds: Timer duration in seconds.
            label: Optional timer label.

        Returns:
            True if timer was started.
        """
        try:
            label_arg = f"--es label '{label}'" if label else ""
            self.adb._shell(
                f"am start -a android.intent.action.SET_TIMER "
                f"--ei length {seconds} "
                f"{label_arg} "
                f"--ez skip_ui true"
            )
            logger.info("Timer set: %ds (%s)", seconds, label)
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to set timer: %s", e)
            return False

    def set_timer_minutes(self, minutes: int, label: str = "") -> bool:
        """
        Start a countdown timer in minutes (convenience method).

        Args:
            minutes: Timer duration in minutes.
            label: Optional timer label.
        """
        return self.set_timer(minutes * 60, label)

    def list_alarms(self) -> list[Alarm]:
        """
        List all configured alarms on the device.

        Returns:
            List of Alarm objects.
        """
        try:
            output = self.adb._shell(
                f"content query --uri {ALARMS_URI} "
                f"--projection _id,hour,minutes,enabled,label,daysofweek,vibrate"
            )
            return self._parse_alarms(output)
        except ADBBridge.ADBError as e:
            logger.error("Failed to list alarms: %s", e)
            return []

    def set_reminder(self, text: str, trigger_time: str) -> bool:
        """
        Set a reminder (creates a calendar event with notification).

        Args:
            text: Reminder text/title.
            trigger_time: When to remind ("YYYY-MM-DD HH:MM" or "in X minutes").

        Returns:
            True if reminder was set.
        """
        try:
            # Parse relative time like "in 10 minutes"
            if trigger_time.lower().startswith("in "):
                trigger_dt = self._parse_relative_time(trigger_time)
            else:
                formats = ["%Y-%m-%d %H:%M", "%H:%M", "%Y-%m-%d"]
                trigger_dt = None
                for fmt in formats:
                    try:
                        trigger_dt = datetime.strptime(trigger_time.strip(), fmt)
                        if fmt == "%H:%M":
                            now = datetime.now()
                            trigger_dt = trigger_dt.replace(
                                year=now.year, month=now.month, day=now.day
                            )
                        break
                    except ValueError:
                        continue

                if not trigger_dt:
                    raise ValueError(f"Cannot parse time: {trigger_time}")

            start_ms = int(trigger_dt.timestamp() * 1000)
            end_ms = start_ms + 900000  # 15 minute duration

            # Create zero-duration calendar event with reminder
            self.adb._shell(
                f"content insert --uri content://com.android.calendar/events "
                f"--bind title:s:'{text}' "
                f"--bind dtstart:l:{start_ms} "
                f"--bind dtend:l:{end_ms} "
                f"--bind calendar_id:i:1 "
                f"--bind hasAlarm:i:1 "
                f"--bind eventTimezone:s:America/Chicago"
            )
            logger.info("Reminder set: '%s' at %s", text, trigger_dt)
            return True

        except (ValueError, ADBBridge.ADBError) as e:
            logger.error("Failed to set reminder: %s", e)
            return False

    def dismiss_alarm(self, alarm_id: str) -> bool:
        """Disable (but don't delete) an alarm."""
        try:
            self.adb._shell(
                f"content update --uri {ALARMS_URI}/{alarm_id} "
                f"--bind enabled:i:0"
            )
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to dismiss alarm %s: %s", alarm_id, e)
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _set_alarm_intent(
        self,
        hour: int,
        minute: int,
        label: str,
        skip_ui: bool = True,
    ) -> bool:
        """Set alarm using SET_ALARM intent."""
        skip_str = "true" if skip_ui else "false"
        label_arg = f"--es android.intent.extra.alarm.MESSAGE '{label}'" if label else ""
        self.adb._shell(
            f"am start -a android.intent.action.SET_ALARM "
            f"--ei android.intent.extra.alarm.HOUR {hour} "
            f"--ei android.intent.extra.alarm.MINUTES {minute} "
            f"--ez android.intent.extra.alarm.SKIP_UI {skip_str} "
            f"{label_arg}"
        )
        logger.info("Alarm set via intent: %02d:%02d (%s)", hour, minute, label)
        return True

    def _set_alarm_content_provider(
        self,
        hour: int,
        minute: int,
        label: str,
        vibrate: bool,
    ) -> bool:
        """Set alarm via content provider (silent)."""
        self.adb._shell(
            f"content insert --uri {ALARMS_URI} "
            f"--bind hour:i:{hour} "
            f"--bind minutes:i:{minute} "
            f"--bind enabled:i:1 "
            f"--bind vibrate:i:{1 if vibrate else 0} "
            f"--bind label:s:{label}"
        )
        return True

    def _parse_time(self, time_str: str) -> tuple[int, int]:
        """Parse time string to (hour, minute)."""
        time_str = time_str.strip()

        # Handle AM/PM
        is_pm = "pm" in time_str.lower()
        is_am = "am" in time_str.lower()
        clean = time_str.lower().replace("am", "").replace("pm", "").strip()

        parts = clean.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0

        if is_pm and hour != 12:
            hour += 12
        elif is_am and hour == 12:
            hour = 0

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Invalid time: {time_str}")

        return hour, minute

    def _parse_relative_time(self, text: str) -> datetime:
        """Parse relative time string like 'in 10 minutes'."""
        import re
        now = datetime.now()
        match = re.search(r"in\s+(\d+)\s+(minute|min|hour|second|sec)", text.lower())
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if "hour" in unit:
                return now + timedelta(hours=amount)
            elif "sec" in unit:
                return now + timedelta(seconds=amount)
            else:
                return now + timedelta(minutes=amount)
        raise ValueError(f"Cannot parse relative time: {text}")

    def _parse_alarms(self, output: str) -> list[Alarm]:
        """Parse content query output into Alarm objects."""
        alarms: list[Alarm] = []
        current: dict[str, str] = {}

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Row:"):
                if current:
                    alarm = self._dict_to_alarm(current)
                    if alarm:
                        alarms.append(alarm)
                current = {}
                row_data = line.split(" ", 2)[2] if len(line.split(" ", 2)) > 2 else ""
                for field_str in row_data.split(", "):
                    if "=" in field_str:
                        k, _, v = field_str.partition("=")
                        current[k.strip()] = v.strip()

        if current:
            alarm = self._dict_to_alarm(current)
            if alarm:
                alarms.append(alarm)

        return alarms

    def _dict_to_alarm(self, d: dict[str, str]) -> Optional[Alarm]:
        """Convert dict to Alarm."""
        try:
            return Alarm(
                alarm_id=d.get("_id", ""),
                hour=int(d.get("hour", 0)),
                minutes=int(d.get("minutes", 0)),
                enabled=d.get("enabled", "0") == "1",
                label=d.get("label", ""),
                days_of_week=int(d.get("daysofweek", 0)),
                vibrate=d.get("vibrate", "1") == "1",
            )
        except (ValueError, KeyError):
            return None
