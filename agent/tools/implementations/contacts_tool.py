"""
P1-18: Contacts Tool

Provides contact management via ADB content provider queries on the
Android contacts database (content://com.android.contacts/...).

Required permissions on device:
- READ_CONTACTS, WRITE_CONTACTS
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from agent.android.adb_bridge import ADBBridge

logger = logging.getLogger(__name__)

CONTACTS_URI = "content://com.android.contacts/contacts"
PHONES_URI = "content://com.android.contacts/phones"
EMAILS_URI = "content://com.android.contacts/emails"
RAW_CONTACTS_URI = "content://com.android.contacts/raw_contacts"


@dataclass
class Contact:
    """Represents an Android contact."""

    contact_id: str
    display_name: str
    phone_numbers: list[str] = field(default_factory=list)
    email_addresses: list[str] = field(default_factory=list)
    starred: bool = False
    times_contacted: int = 0
    photo_uri: str = ""

    @property
    def primary_phone(self) -> str:
        return self.phone_numbers[0] if self.phone_numbers else ""

    @property
    def primary_email(self) -> str:
        return self.email_addresses[0] if self.email_addresses else ""

    def __str__(self) -> str:
        parts = [self.display_name]
        if self.phone_numbers:
            parts.append(self.phone_numbers[0])
        if self.email_addresses:
            parts.append(self.email_addresses[0])
        return " | ".join(parts)


class ContactsTool:
    """
    Contact management tool using ADB content provider queries.

    Usage:
        contacts = ContactsTool(adb_bridge)
        results = contacts.search_contacts("Alice")
        contacts.add_contact("Bob Smith", "+15551234567")
    """

    def __init__(self, adb: ADBBridge) -> None:
        """
        Initialize the ContactsTool.

        Args:
            adb: ADBBridge instance.
        """
        self.adb = adb

    def search_contacts(self, query: str, limit: int = 10) -> list[Contact]:
        """
        Search contacts by name or phone number.

        Args:
            query: Search string.
            limit: Maximum results to return.

        Returns:
            List of matching Contact objects.
        """
        try:
            escaped = query.replace("'", "\\'")
            output = self.adb._shell(
                f"content query --uri {PHONES_URI} "
                f"--projection contact_id,display_name,number "
                f"--where \"display_name LIKE '%{escaped}%' OR number LIKE '%{escaped}%'\" "
                f"--sort 'display_name ASC' "
                f"--limit {limit}"
            )
            return self._parse_phone_query(output)

        except ADBBridge.ADBError as e:
            logger.error("Failed to search contacts: %s", e)
            return []

    def get_contact(self, name: str) -> Optional[Contact]:
        """
        Get a contact by exact display name (case-insensitive).

        Args:
            name: Contact display name.

        Returns:
            Contact if found, else None.
        """
        results = self.search_contacts(name, limit=5)
        name_lower = name.lower()
        for contact in results:
            if contact.display_name.lower() == name_lower:
                return contact
        # Return first result if no exact match
        return results[0] if results else None

    def list_contacts(
        self,
        limit: int = 100,
        starred_only: bool = False,
    ) -> list[Contact]:
        """
        List all contacts.

        Args:
            limit: Maximum number of contacts to return.
            starred_only: If True, return only starred/favorite contacts.

        Returns:
            List of Contact objects sorted by name.
        """
        try:
            where = "starred=1" if starred_only else ""
            where_arg = f"--where '{where}'" if where else ""

            output = self.adb._shell(
                f"content query --uri {PHONES_URI} "
                f"--projection contact_id,display_name,number "
                f"{where_arg} "
                f"--sort 'display_name ASC' "
                f"--limit {limit}"
            )
            return self._parse_phone_query(output)

        except ADBBridge.ADBError as e:
            logger.error("Failed to list contacts: %s", e)
            return []

    def add_contact(
        self,
        name: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        account_type: str = "com.google",
        account_name: str = "",
    ) -> bool:
        """
        Add a new contact to the device.

        Args:
            name: Contact display name.
            phone: Phone number (optional).
            email: Email address (optional).
            account_type: Android account type.
            account_name: Account name (e.g., Gmail address).

        Returns:
            True if the contact was created successfully.
        """
        try:
            # Insert raw contact
            insert_cmd = (
                f"content insert --uri {RAW_CONTACTS_URI} "
                f"--bind account_type:s:{account_type} "
                f"--bind account_name:s:{account_name}"
            )
            output = self.adb._shell(insert_cmd)

            # Extract new row ID
            raw_id_match = re.search(r"result=(\d+)", output)
            if not raw_id_match:
                logger.warning("Could not get raw_contact_id from: %s", output)
                # Fallback: use Intent-based contact creation
                return self._add_contact_via_intent(name, phone, email)

            raw_id = raw_id_match.group(1)

            # Insert display name
            self.adb._shell(
                f"content insert "
                f"--uri content://com.android.contacts/data "
                f"--bind raw_contact_id:i:{raw_id} "
                f"--bind mimetype:s:vnd.android.cursor.item/name "
                f"--bind display_name:s:{name}"
            )

            # Insert phone number
            if phone:
                self.adb._shell(
                    f"content insert "
                    f"--uri content://com.android.contacts/data "
                    f"--bind raw_contact_id:i:{raw_id} "
                    f"--bind mimetype:s:vnd.android.cursor.item/phone_v2 "
                    f"--bind data1:s:{phone} "
                    f"--bind data2:i:2"  # 2 = TYPE_MOBILE
                )

            # Insert email
            if email:
                self.adb._shell(
                    f"content insert "
                    f"--uri content://com.android.contacts/data "
                    f"--bind raw_contact_id:i:{raw_id} "
                    f"--bind mimetype:s:vnd.android.cursor.item/email_v2 "
                    f"--bind data1:s:{email} "
                    f"--bind data2:i:1"  # 1 = TYPE_HOME
                )

            logger.info("Added contact: %s", name)
            return True

        except ADBBridge.ADBError as e:
            logger.error("Failed to add contact %s: %s", name, e)
            return False

    def _add_contact_via_intent(
        self,
        name: str,
        phone: Optional[str],
        email: Optional[str],
    ) -> bool:
        """Fallback: open Add Contact screen via Intent."""
        try:
            cmd = (
                "am start -a android.intent.action.INSERT "
                "-t vnd.android.cursor.dir/person "
                f"-e name '{name}'"
            )
            if phone:
                cmd += f" -e phone '{phone}'"
            if email:
                cmd += f" -e email '{email}'"
            self.adb._shell(cmd)
            return True
        except ADBBridge.ADBError as e:
            logger.error("Intent-based contact add failed: %s", e)
            return False

    def delete_contact(self, contact_id: str) -> bool:
        """
        Delete a contact by ID.

        Args:
            contact_id: The contact's _id from the contacts database.

        Returns:
            True if deleted successfully.
        """
        try:
            self.adb._shell(
                f"content delete --uri {CONTACTS_URI}/{contact_id}"
            )
            logger.info("Deleted contact: %s", contact_id)
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to delete contact %s: %s", contact_id, e)
            return False

    def get_contact_count(self) -> int:
        """Return the total number of contacts."""
        return len(self.list_contacts(limit=10000))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_phone_query(self, output: str) -> list[Contact]:
        """Parse content query output from the phones table."""
        contacts_map: dict[str, Contact] = {}

        current: dict[str, str] = {}
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Row:"):
                if current:
                    self._merge_phone_row(current, contacts_map)
                current = {}
                row_data = line.split(" ", 2)[2] if len(line.split(" ", 2)) > 2 else ""
                for field_str in row_data.split(", "):
                    if "=" in field_str:
                        k, _, v = field_str.partition("=")
                        current[k.strip()] = v.strip()

        if current:
            self._merge_phone_row(current, contacts_map)

        return list(contacts_map.values())

    def _merge_phone_row(
        self,
        row: dict[str, str],
        contacts: dict[str, Contact],
    ) -> None:
        """Merge a phone row into the contacts map (one contact may have multiple numbers)."""
        cid = row.get("contact_id", row.get("_id", ""))
        if not cid:
            return

        if cid not in contacts:
            contacts[cid] = Contact(
                contact_id=cid,
                display_name=row.get("display_name", ""),
            )

        number = row.get("number", "")
        if number and number not in contacts[cid].phone_numbers:
            contacts[cid].phone_numbers.append(number)
