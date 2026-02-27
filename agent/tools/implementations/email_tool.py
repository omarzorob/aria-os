"""
P1-16: Email Tool

Provides email functionality via standard SMTP (send) and IMAP (read/search).
Credentials are loaded from environment variables.

Environment variables (required):
- SMTP_HOST: SMTP server hostname (e.g., smtp.gmail.com)
- SMTP_PORT: SMTP port (default: 587)
- SMTP_USER: Email address / username
- SMTP_PASS: Email password or app password
- IMAP_HOST: IMAP server hostname (e.g., imap.gmail.com)
- IMAP_PORT: IMAP port (default: 993)

For Gmail, use App Passwords and enable IMAP in Gmail settings.
"""

from __future__ import annotations

import email as email_lib
import imaplib
import logging
import os
import smtplib
import ssl
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import decode_header
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Represents an email message."""

    message_id: str
    subject: str
    sender: str
    recipients: list[str]
    body: str
    date: str
    is_read: bool = False
    is_flagged: bool = False
    folder: str = "INBOX"
    uid: str = ""

    def __str__(self) -> str:
        return f"From: {self.sender} | Subject: {self.subject}"


class EmailTool:
    """
    Email tool for reading and sending emails via SMTP/IMAP.

    Usage:
        email_tool = EmailTool()
        email_tool.send_email("friend@example.com", "Hello", "How are you?")
        messages = email_tool.read_inbox(count=5)
    """

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_pass: Optional[str] = None,
        imap_host: Optional[str] = None,
        imap_port: Optional[int] = None,
    ) -> None:
        """
        Initialize the EmailTool.

        Credentials can be provided directly or via environment variables.
        """
        self.smtp_host = smtp_host or os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user = smtp_user or os.environ.get("SMTP_USER", "")
        self.smtp_pass = smtp_pass or os.environ.get("SMTP_PASS", "")
        self.imap_host = imap_host or os.environ.get("IMAP_HOST", "imap.gmail.com")
        self.imap_port = imap_port or int(os.environ.get("IMAP_PORT", "993"))

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    def send_email(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
    ) -> bool:
        """
        Send an email via SMTP.

        Args:
            to: Recipient email address or list of addresses.
            subject: Email subject.
            body: Plain text body.
            html_body: Optional HTML version of the body.
            cc: Optional CC addresses.
            bcc: Optional BCC addresses.

        Returns:
            True if sent successfully.
        """
        if not self.smtp_user or not self.smtp_pass:
            logger.error("SMTP credentials not configured (SMTP_USER, SMTP_PASS)")
            return False

        recipients = [to] if isinstance(to, str) else to
        if cc:
            recipients += cc
        if bcc:
            recipients += bcc

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.smtp_user
            msg["To"] = ", ".join([to] if isinstance(to, str) else to)
            if cc:
                msg["Cc"] = ", ".join(cc)

            msg.attach(MIMEText(body, "plain", "utf-8"))
            if html_body:
                msg.attach(MIMEText(html_body, "html", "utf-8"))

            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.smtp_user, recipients, msg.as_string())

            logger.info("Email sent to %s: %s", recipients, subject)
            return True

        except smtplib.SMTPException as e:
            logger.error("Failed to send email: %s", e)
            return False

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read_inbox(
        self,
        count: int = 10,
        folder: str = "INBOX",
        unread_only: bool = False,
    ) -> list[EmailMessage]:
        """
        Read emails from the inbox.

        Args:
            count: Maximum number of messages to return.
            folder: Mailbox folder (default: "INBOX").
            unread_only: If True, only return unread messages.

        Returns:
            List of EmailMessage objects, newest first.
        """
        try:
            with self._imap_connect() as imap:
                imap.select(folder, readonly=True)

                criteria = "UNSEEN" if unread_only else "ALL"
                _, uid_data = imap.uid("search", None, criteria)

                if not uid_data or not uid_data[0]:
                    return []

                uids = uid_data[0].split()
                # Get most recent `count` messages
                recent_uids = uids[-count:][::-1]

                messages: list[EmailMessage] = []
                for uid in recent_uids:
                    msg = self._fetch_message(imap, uid, folder)
                    if msg:
                        messages.append(msg)

                return messages

        except (imaplib.IMAP4.error, OSError) as e:
            logger.error("Failed to read inbox: %s", e)
            return []

    def search_emails(
        self,
        query: str,
        folder: str = "INBOX",
        count: int = 10,
    ) -> list[EmailMessage]:
        """
        Search emails for a keyword.

        Args:
            query: Search string (searches subject and body).
            folder: Mailbox folder to search.
            count: Maximum results to return.

        Returns:
            List of matching EmailMessage objects.
        """
        try:
            with self._imap_connect() as imap:
                imap.select(folder, readonly=True)

                # IMAP SEARCH with TEXT
                encoded_query = query.encode("utf-8")
                _, uid_data = imap.uid(
                    "search",
                    "CHARSET",
                    "UTF-8",
                    "TEXT",
                    encoded_query,
                )

                if not uid_data or not uid_data[0]:
                    return []

                uids = uid_data[0].split()
                recent_uids = uids[-count:][::-1]

                messages: list[EmailMessage] = []
                for uid in recent_uids:
                    msg = self._fetch_message(imap, uid, folder)
                    if msg:
                        messages.append(msg)

                return messages

        except (imaplib.IMAP4.error, OSError) as e:
            logger.error("Failed to search emails: %s", e)
            return []

    def get_unread_count(self, folder: str = "INBOX") -> int:
        """
        Get the number of unread emails.

        Args:
            folder: Mailbox folder to check.

        Returns:
            Count of unread messages.
        """
        try:
            with self._imap_connect() as imap:
                imap.select(folder, readonly=True)
                _, data = imap.uid("search", None, "UNSEEN")
                if data and data[0]:
                    return len(data[0].split())
                return 0
        except (imaplib.IMAP4.error, OSError) as e:
            logger.error("Failed to get unread count: %s", e)
            return 0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _imap_connect(self) -> imaplib.IMAP4_SSL:
        """Create and return an authenticated IMAP connection."""
        if not self.smtp_user or not self.smtp_pass:
            raise ValueError("IMAP credentials not configured (SMTP_USER, SMTP_PASS)")

        imap = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        imap.login(self.smtp_user, self.smtp_pass)
        return imap

    def _fetch_message(
        self,
        imap: imaplib.IMAP4_SSL,
        uid: bytes,
        folder: str,
    ) -> Optional[EmailMessage]:
        """Fetch a single message by UID and parse it."""
        try:
            _, data = imap.uid("fetch", uid, "(RFC822 FLAGS)")
            if not data or data[0] is None:
                return None

            raw_email = data[0][1]
            flags_str = data[0][0].decode() if data[0][0] else ""

            msg = email_lib.message_from_bytes(raw_email)

            subject = _decode_header_value(msg.get("Subject", ""))
            sender = _decode_header_value(msg.get("From", ""))
            date = msg.get("Date", "")
            msg_id = msg.get("Message-ID", uid.decode())
            is_read = "\\Seen" in flags_str

            # Extract body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    if ct == "text/plain" and not part.get("Content-Disposition"):
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            body = payload.decode(charset, errors="replace")
                            break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")

            return EmailMessage(
                message_id=msg_id,
                subject=subject,
                sender=sender,
                recipients=[msg.get("To", "")],
                body=body[:2000],  # Truncate long bodies
                date=date,
                is_read=is_read,
                folder=folder,
                uid=uid.decode(),
            )

        except Exception as e:
            logger.warning("Failed to parse email (uid=%s): %s", uid, e)
            return None


def _decode_header_value(value: str) -> str:
    """Decode encoded email header values to plain string."""
    if not value:
        return ""
    parts = decode_header(value)
    decoded_parts = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts)
