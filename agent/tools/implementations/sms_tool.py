"""
P1-15: SMS Tool

Provides SMS functionality via ADB content provider queries and broadcasts.
Reads SMS from the device content provider, sends via adb shell am broadcast.

Required permissions on device:
- READ_SMS, SEND_SMS (Aria app must be set as default SMS app or have grants)

Environment variables:
- (none — uses ADB)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from agent.android.adb_bridge import ADBBridge

logger = logging.getLogger(__name__)

# Android SMS content provider URI
SMS_URI = "content://sms"
SMS_INBOX_URI = "content://sms/inbox"
SMS_SENT_URI = "content://sms/sent"


@dataclass
class SMSMessage:
    """Represents an SMS message."""

    message_id: str
    address: str  # Phone number
    body: str
    date: int  # Unix timestamp in ms
    read: bool
    thread_id: str
    type: int  # 1=inbox, 2=sent

    @property
    def is_read(self) -> bool:
        return self.read

    def __str__(self) -> str:
        direction = "→" if self.type == 2 else "←"
        return f"{direction} {self.address}: {self.body[:80]}"


class SMSTool:
    """
    SMS tool for reading and sending text messages via ADB.

    Usage:
        sms = SMSTool(adb_bridge)
        messages = sms.read_sms(count=5)
        sms.send_sms("+15551234567", "Hello from Aria!")
    """

    def __init__(self, adb: ADBBridge) -> None:
        """
        Initialize the SMSTool.

        Args:
            adb: ADBBridge instance.
        """
        self.adb = adb

    def send_sms(self, to: str, message: str) -> bool:
        """
        Send an SMS message.

        Uses Android's SMS intent via am broadcast. Requires the Aria app
        to handle the broadcast (or a companion script via Termux/ADB).

        Args:
            to: Recipient phone number (e.g., "+15551234567").
            message: Message body text.

        Returns:
            True if the send command was dispatched successfully.
        """
        try:
            # Escape message for shell
            escaped_msg = message.replace("'", "\\'").replace('"', '\\"')
            escaped_to = to.replace("+", "\\+")

            # Send via am start with ACTION_SENDTO
            cmd = (
                f"am start -a android.intent.action.SENDTO "
                f"-d 'smsto:{escaped_to}' "
                f"--es sms_body '{escaped_msg}' "
                f"--ez exit_on_sent true"
            )
            self.adb._shell(cmd)
            time.sleep(0.5)

            # Auto-confirm send by pressing the send button (enter/green button)
            # This may vary by SMS app
            self.adb.press_key("KEYCODE_ENTER")

            logger.info("SMS sent to %s", to)
            return True

        except ADBBridge.ADBError as e:
            logger.error("Failed to send SMS to %s: %s", to, e)
            return False

    def read_sms(self, count: int = 10, box: str = "inbox") -> list[SMSMessage]:
        """
        Read SMS messages from the device.

        Args:
            count: Maximum number of messages to return.
            box: "inbox", "sent", or "all".

        Returns:
            List of SMSMessage objects, newest first.
        """
        uri = {
            "inbox": SMS_INBOX_URI,
            "sent": SMS_SENT_URI,
            "all": SMS_URI,
        }.get(box, SMS_INBOX_URI)

        try:
            output = self.adb._shell(
                f"content query --uri {uri} "
                f"--projection _id,address,body,date,read,thread_id,type "
                f"--sort 'date DESC' "
                f"--limit {count}"
            )
            return self._parse_content_query(output)

        except ADBBridge.ADBError as e:
            logger.error("Failed to read SMS: %s", e)
            return []

    def get_unread_sms(self) -> list[SMSMessage]:
        """
        Get all unread SMS messages from the inbox.

        Returns:
            List of unread SMSMessage objects.
        """
        try:
            output = self.adb._shell(
                f"content query --uri {SMS_INBOX_URI} "
                f"--projection _id,address,body,date,read,thread_id,type "
                f"--where 'read=0' "
                f"--sort 'date DESC'"
            )
            return self._parse_content_query(output)

        except ADBBridge.ADBError as e:
            logger.error("Failed to get unread SMS: %s", e)
            return []

    def search_sms(self, query: str, count: int = 20) -> list[SMSMessage]:
        """
        Search SMS messages for a keyword.

        Args:
            query: Search string (matches phone number or body).
            count: Maximum results to return.

        Returns:
            List of matching SMSMessage objects.
        """
        try:
            escaped = query.replace("'", "\\'")
            output = self.adb._shell(
                f"content query --uri {SMS_URI} "
                f"--projection _id,address,body,date,read,thread_id,type "
                f"--where \"body LIKE '%{escaped}%' OR address LIKE '%{escaped}%'\" "
                f"--sort 'date DESC' "
                f"--limit {count}"
            )
            return self._parse_content_query(output)

        except ADBBridge.ADBError as e:
            logger.error("Failed to search SMS: %s", e)
            return []

    def get_unread_count(self) -> int:
        """Return the count of unread SMS messages."""
        return len(self.get_unread_sms())

    def _parse_content_query(self, output: str) -> list[SMSMessage]:
        """
        Parse `adb shell content query` output into SMSMessage objects.

        Args:
            output: Raw content query output.

        Returns:
            List of SMSMessage objects.
        """
        messages: list[SMSMessage] = []
        current: dict[str, str] = {}

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Row:"):
                if current:
                    msg = self._dict_to_sms(current)
                    if msg:
                        messages.append(msg)
                current = {}
                # Parse inline fields: Row: 0 _id=1, address=..., ...
                row_data = line.split(" ", 2)[2] if len(line.split(" ", 2)) > 2 else ""
                for field in row_data.split(", "):
                    if "=" in field:
                        k, _, v = field.partition("=")
                        current[k.strip()] = v.strip()
            elif "=" in line and current is not None:
                k, _, v = line.partition("=")
                current[k.strip()] = v.strip()

        # Don't forget the last record
        if current:
            msg = self._dict_to_sms(current)
            if msg:
                messages.append(msg)

        return messages

    def _dict_to_sms(self, d: dict[str, str]) -> Optional[SMSMessage]:
        """Convert a parsed dict to an SMSMessage."""
        try:
            return SMSMessage(
                message_id=d.get("_id", ""),
                address=d.get("address", ""),
                body=d.get("body", ""),
                date=int(d.get("date", 0)),
                read=d.get("read", "0") == "1",
                thread_id=d.get("thread_id", ""),
                type=int(d.get("type", 1)),
            )
        except (ValueError, KeyError):
            return None
