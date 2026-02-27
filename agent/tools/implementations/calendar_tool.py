"""
P1-19: Calendar Tool

Provides calendar event management via ADB content provider queries on
the Android Calendar content provider (content://com.android.calendar/...).

Required permissions on device:
- READ_CALENDAR, WRITE_CALENDAR
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from agent.android.adb_bridge import ADBBridge

logger = logging.getLogger(__name__)

EVENTS_URI = "content://com.android.calendar/events"
CALENDARS_URI = "content://com.android.calendar/calendars"
INSTANCES_URI = "content://com.android.calendar/instances/when"


@dataclass
class CalendarEvent:
    """Represents a calendar event."""

    event_id: str
    title: str
    description: str
    location: str
    start_time: int  # Unix timestamp in ms
    end_time: int    # Unix timestamp in ms
    all_day: bool = False
    calendar_id: str = ""
    organizer: str = ""
    recurring: bool = False

    @property
    def start_dt(self) -> datetime:
        return datetime.fromtimestamp(self.start_time / 1000)

    @property
    def end_dt(self) -> datetime:
        return datetime.fromtimestamp(self.end_time / 1000)

    @property
    def duration_minutes(self) -> int:
        return int((self.end_time - self.start_time) / 60000)

    def __str__(self) -> str:
        return (
            f"{self.title} | "
            f"{self.start_dt.strftime('%Y-%m-%d %H:%M')} — "
            f"{self.end_dt.strftime('%H:%M')}"
            + (f" @ {self.location}" if self.location else "")
        )


class CalendarTool:
    """
    Calendar management tool using ADB content provider queries.

    Usage:
        cal = CalendarTool(adb_bridge)
        events = cal.get_today_events()
        cal.create_event("Doctor", "2024-03-15 10:00", "2024-03-15 11:00")
    """

    def __init__(self, adb: ADBBridge) -> None:
        """
        Initialize the CalendarTool.

        Args:
            adb: ADBBridge instance.
        """
        self.adb = adb

    def get_events(self, days: int = 7) -> list[CalendarEvent]:
        """
        Get calendar events for the next N days.

        Args:
            days: Number of days ahead to fetch events for.

        Returns:
            List of CalendarEvent objects sorted by start time.
        """
        now_ms = int(time.time() * 1000)
        end_ms = now_ms + days * 24 * 3600 * 1000

        try:
            output = self.adb._shell(
                f"content query --uri '{INSTANCES_URI}/{now_ms}/{end_ms}' "
                f"--projection event_id,title,description,eventLocation,"
                f"begin,end,allDay,calendar_id,organizer,rrule "
                f"--sort 'begin ASC'"
            )
            return self._parse_events(output)

        except ADBBridge.ADBError as e:
            logger.error("Failed to get calendar events: %s", e)
            # Fallback: query events table directly
            return self._get_events_direct(now_ms, end_ms)

    def get_today_events(self) -> list[CalendarEvent]:
        """
        Get all calendar events for today.

        Returns:
            List of today's CalendarEvent objects.
        """
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)

        start_ms = int(start_of_day.timestamp() * 1000)
        end_ms = int(end_of_day.timestamp() * 1000)

        try:
            output = self.adb._shell(
                f"content query --uri '{INSTANCES_URI}/{start_ms}/{end_ms}' "
                f"--projection event_id,title,description,eventLocation,begin,end,allDay "
                f"--sort 'begin ASC'"
            )
            return self._parse_events(output)

        except ADBBridge.ADBError as e:
            logger.error("Failed to get today's events: %s", e)
            return []

    def create_event(
        self,
        title: str,
        start: str,
        end: str,
        location: str = "",
        description: str = "",
        calendar_id: str = "1",
        all_day: bool = False,
    ) -> bool:
        """
        Create a new calendar event.

        Args:
            title: Event title.
            start: Start time as "YYYY-MM-DD HH:MM" or "YYYY-MM-DD" for all-day.
            end: End time as "YYYY-MM-DD HH:MM".
            location: Optional event location.
            description: Optional event description.
            calendar_id: Calendar ID to create in (default: "1").
            all_day: If True, create as all-day event.

        Returns:
            True if event was created successfully.
        """
        try:
            start_ms = self._parse_datetime_to_ms(start)
            end_ms = self._parse_datetime_to_ms(end)

            # Insert via content provider
            cmd = (
                f"content insert --uri {EVENTS_URI} "
                f"--bind title:s:{title} "
                f"--bind dtstart:l:{start_ms} "
                f"--bind dtend:l:{end_ms} "
                f"--bind calendar_id:i:{calendar_id} "
                f"--bind allDay:i:{1 if all_day else 0} "
                f"--bind hasAlarm:i:1 "
                f"--bind eventTimezone:s:America/Chicago"
            )
            if location:
                cmd += f" --bind eventLocation:s:'{location}'"
            if description:
                cmd += f" --bind description:s:'{description}'"

            output = self.adb._shell(cmd)
            logger.info("Created event: %s at %s", title, start)
            return True

        except (ADBBridge.ADBError, ValueError) as e:
            logger.error("Failed to create event '%s': %s", title, e)
            return False

    def search_events(self, query: str, days_ahead: int = 30) -> list[CalendarEvent]:
        """
        Search calendar events by title or description keyword.

        Args:
            query: Search string.
            days_ahead: How many days ahead to search.

        Returns:
            List of matching CalendarEvent objects.
        """
        try:
            now_ms = int(time.time() * 1000)
            end_ms = now_ms + days_ahead * 24 * 3600 * 1000
            escaped = query.replace("'", "\\'")

            output = self.adb._shell(
                f"content query --uri {EVENTS_URI} "
                f"--projection _id,title,description,eventLocation,dtstart,dtend,allDay "
                f"--where \"title LIKE '%{escaped}%' OR description LIKE '%{escaped}%'\" "
                f"--sort 'dtstart ASC' "
                f"--limit 20"
            )
            return self._parse_events(output, use_dtstart=True)

        except ADBBridge.ADBError as e:
            logger.error("Failed to search events: %s", e)
            return []

    def delete_event(self, event_id: str) -> bool:
        """
        Delete a calendar event.

        Args:
            event_id: The event's ID.

        Returns:
            True if deleted.
        """
        try:
            self.adb._shell(f"content delete --uri {EVENTS_URI}/{event_id}")
            logger.info("Deleted event: %s", event_id)
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to delete event %s: %s", event_id, e)
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_events_direct(self, start_ms: int, end_ms: int) -> list[CalendarEvent]:
        """Fallback: query events table directly (no instances)."""
        try:
            output = self.adb._shell(
                f"content query --uri {EVENTS_URI} "
                f"--projection _id,title,description,eventLocation,dtstart,dtend,allDay "
                f"--where 'dtstart >= {start_ms} AND dtstart <= {end_ms}' "
                f"--sort 'dtstart ASC' "
                f"--limit 50"
            )
            return self._parse_events(output, use_dtstart=True)
        except ADBBridge.ADBError:
            return []

    def _parse_events(
        self,
        output: str,
        use_dtstart: bool = False,
    ) -> list[CalendarEvent]:
        """Parse content query output into CalendarEvent objects."""
        events: list[CalendarEvent] = []
        current: dict[str, str] = {}

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Row:"):
                if current:
                    ev = self._dict_to_event(current, use_dtstart)
                    if ev:
                        events.append(ev)
                current = {}
                row_data = line.split(" ", 2)[2] if len(line.split(" ", 2)) > 2 else ""
                for field_str in row_data.split(", "):
                    if "=" in field_str:
                        k, _, v = field_str.partition("=")
                        current[k.strip()] = v.strip()

        if current:
            ev = self._dict_to_event(current, use_dtstart)
            if ev:
                events.append(ev)

        return events

    def _dict_to_event(
        self,
        d: dict[str, str],
        use_dtstart: bool,
    ) -> Optional[CalendarEvent]:
        """Convert parsed dict to CalendarEvent."""
        try:
            start_key = "dtstart" if use_dtstart else "begin"
            end_key = "dtend" if use_dtstart else "end"
            return CalendarEvent(
                event_id=d.get("event_id", d.get("_id", "")),
                title=d.get("title", ""),
                description=d.get("description", ""),
                location=d.get("eventLocation", ""),
                start_time=int(d.get(start_key, 0)),
                end_time=int(d.get(end_key, 0)),
                all_day=d.get("allDay", "0") == "1",
                calendar_id=d.get("calendar_id", ""),
                organizer=d.get("organizer", ""),
                recurring=bool(d.get("rrule", "")),
            )
        except (ValueError, KeyError):
            return None

    def _parse_datetime_to_ms(self, dt_str: str) -> int:
        """Parse datetime string to milliseconds timestamp."""
        formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(dt_str.strip(), fmt)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse datetime: {dt_str}")
