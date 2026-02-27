"""
P1-17: Phone Tool

Provides phone call management via ADB telecom commands and keycodes.
Supports dialing, answering, ending calls, and reading call history.

Required permissions on device:
- READ_CALL_LOG, CALL_PHONE (Aria app or ADB shell permissions)
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from agent.android.adb_bridge import ADBBridge

logger = logging.getLogger(__name__)


class CallState(str, Enum):
    """Android telephony call states."""
    IDLE = "idle"
    RINGING = "ringing"
    OFFHOOK = "offhook"
    UNKNOWN = "unknown"


@dataclass
class CallRecord:
    """Represents an entry in the call log."""

    call_id: str
    number: str
    name: str
    call_type: int  # 1=incoming, 2=outgoing, 3=missed, 4=voicemail
    date: int  # Unix timestamp in ms
    duration: int  # Duration in seconds
    is_new: bool = False

    @property
    def type_label(self) -> str:
        return {1: "incoming", 2: "outgoing", 3: "missed", 4: "voicemail"}.get(
            self.call_type, "unknown"
        )

    def __str__(self) -> str:
        name = self.name or self.number
        return f"{self.type_label.capitalize()} — {name} ({self.duration}s)"


class PhoneTool:
    """
    Phone call management tool using ADB telecom controls.

    Usage:
        phone = PhoneTool(adb_bridge)
        phone.dial("+15551234567")
        time.sleep(10)
        phone.end_call()
    """

    # Android telecom keycodes
    KEYCODE_CALL = 5
    KEYCODE_ENDCALL = 6
    KEYCODE_ANSWER = 5  # Same as CALL on most devices

    def __init__(self, adb: ADBBridge) -> None:
        """
        Initialize the PhoneTool.

        Args:
            adb: ADBBridge instance.
        """
        self.adb = adb

    def dial(self, number: str) -> bool:
        """
        Dial a phone number.

        Opens the dialer and initiates a call using ACTION_CALL intent.
        Requires CALL_PHONE permission or ADB shell root.

        Args:
            number: Phone number to dial (e.g., "+15551234567").

        Returns:
            True if dialing was initiated successfully.
        """
        try:
            # Clean the number
            clean_num = re.sub(r"[^\d+]", "", number)

            # Use am start ACTION_CALL (requires CALL_PHONE permission)
            self.adb._shell(
                f"am start -a android.intent.action.CALL -d 'tel:{clean_num}'"
            )
            logger.info("Dialing: %s", clean_num)
            return True

        except ADBBridge.ADBError as e:
            logger.error("Failed to dial %s: %s", number, e)
            return False

    def end_call(self) -> bool:
        """
        End the current call.

        Returns:
            True if end-call command was sent.
        """
        try:
            # Method 1: telecom command (Android 6+)
            self.adb._shell("telecom end-call 2>/dev/null || true")
            # Method 2: keycode
            self.adb.press_key(self.KEYCODE_ENDCALL)
            logger.info("Call ended")
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to end call: %s", e)
            return False

    def answer_call(self) -> bool:
        """
        Answer an incoming call.

        Returns:
            True if answer command was sent.
        """
        try:
            # Method 1: input keyevent KEYCODE_CALL
            self.adb.press_key(self.KEYCODE_CALL)
            # Method 2: telecom
            self.adb._shell(
                "am broadcast -a android.intent.action.ANSWER 2>/dev/null || true"
            )
            logger.info("Call answered")
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to answer call: %s", e)
            return False

    def reject_call(self) -> bool:
        """
        Reject an incoming call.

        Returns:
            True if reject command was sent.
        """
        try:
            self.adb.press_key(self.KEYCODE_ENDCALL)
            logger.info("Call rejected")
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to reject call: %s", e)
            return False

    def get_call_state(self) -> CallState:
        """
        Get the current telephony call state.

        Returns:
            CallState enum value.
        """
        try:
            output = self.adb._shell(
                "dumpsys telephony.registry | grep -i 'mCallState' | head -1"
            )
            if "RINGING" in output.upper():
                return CallState.RINGING
            elif "OFFHOOK" in output.upper():
                return CallState.OFFHOOK
            elif "IDLE" in output.upper():
                return CallState.IDLE

            # Fallback: check call log activity
            call_output = self.adb._shell(
                "dumpsys activity activities | grep -i 'InCallActivity' | head -1"
            )
            if "InCallActivity" in call_output:
                return CallState.OFFHOOK

            return CallState.IDLE

        except ADBBridge.ADBError as e:
            logger.error("Failed to get call state: %s", e)
            return CallState.UNKNOWN

    def get_recent_calls(self, count: int = 20) -> list[CallRecord]:
        """
        Get recent call log entries.

        Args:
            count: Maximum number of records to return.

        Returns:
            List of CallRecord objects, newest first.
        """
        try:
            output = self.adb._shell(
                f"content query --uri content://call_log/calls "
                f"--projection _id,number,name,type,date,duration,new "
                f"--sort 'date DESC' "
                f"--limit {count}"
            )
            return self._parse_call_log(output)

        except ADBBridge.ADBError as e:
            logger.error("Failed to get recent calls: %s", e)
            return []

    def wait_for_call(
        self,
        timeout: float = 60.0,
        from_number: Optional[str] = None,
    ) -> bool:
        """
        Wait for an incoming call.

        Args:
            timeout: Maximum seconds to wait.
            from_number: Optional number to wait for specifically.

        Returns:
            True if a call was detected.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            state = self.get_call_state()
            if state == CallState.RINGING:
                logger.info("Incoming call detected")
                return True
            time.sleep(1.0)
        return False

    def _parse_call_log(self, output: str) -> list[CallRecord]:
        """Parse `adb shell content query` call log output."""
        records: list[CallRecord] = []
        current: dict[str, str] = {}

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Row:"):
                if current:
                    rec = self._dict_to_call_record(current)
                    if rec:
                        records.append(rec)
                current = {}
                row_data = line.split(" ", 2)[2] if len(line.split(" ", 2)) > 2 else ""
                for field in row_data.split(", "):
                    if "=" in field:
                        k, _, v = field.partition("=")
                        current[k.strip()] = v.strip()

        if current:
            rec = self._dict_to_call_record(current)
            if rec:
                records.append(rec)

        return records

    def _dict_to_call_record(self, d: dict[str, str]) -> Optional[CallRecord]:
        """Convert parsed dict to CallRecord."""
        try:
            return CallRecord(
                call_id=d.get("_id", ""),
                number=d.get("number", ""),
                name=d.get("name", ""),
                call_type=int(d.get("type", 1)),
                date=int(d.get("date", 0)),
                duration=int(d.get("duration", 0)),
                is_new=d.get("new", "0") == "1",
            )
        except (ValueError, KeyError):
            return None
