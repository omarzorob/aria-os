"""
P1-24: Food Order Tool

Provides food ordering via UberEats web automation using the BrowserTool.
Supports restaurant search, menu browsing, and order placement.

Environment variables:
- UBEREATS_EMAIL: UberEats account email
- UBEREATS_DELIVERY_ADDRESS: Default delivery address

Note: Actual ordering requires logged-in UberEats account.
For automation, UberEats must be open and logged in on the device,
or use web automation via BrowserTool.
"""

from __future__ import annotations

import logging
import time
import os
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional

from agent.android.adb_bridge import ADBBridge
from .browser_tool import BrowserTool

logger = logging.getLogger(__name__)

UBEREATS_PACKAGE = "com.ubercabs.eats"
UBEREATS_WEB = "https://www.ubereats.com"


@dataclass
class Restaurant:
    """Represents a restaurant on UberEats."""

    name: str
    rating: float = 0.0
    delivery_time: str = ""
    delivery_fee: str = ""
    category: str = ""
    restaurant_id: str = ""
    url: str = ""

    def __str__(self) -> str:
        return (
            f"{self.name} — {self.category} "
            f"| ★{self.rating:.1f} | {self.delivery_time} | {self.delivery_fee}"
        )


@dataclass
class MenuItem:
    """Represents a menu item from a restaurant."""

    name: str
    description: str = ""
    price: str = ""
    item_id: str = ""
    category: str = ""
    customizable: bool = False

    def __str__(self) -> str:
        return f"{self.name} — {self.price}"


@dataclass
class CartItem:
    """Item in the order cart."""

    item: MenuItem
    quantity: int = 1
    special_instructions: str = ""


@dataclass
class Order:
    """Represents an UberEats order."""

    order_id: str
    restaurant: str
    items: list[CartItem]
    total: str
    status: str
    estimated_delivery: str = ""

    def __str__(self) -> str:
        return (
            f"Order {self.order_id} — {self.restaurant} "
            f"| {self.status} | {self.total} | ETA: {self.estimated_delivery}"
        )


class FoodOrderTool:
    """
    Food ordering via UberEats using browser automation.

    Usage:
        food = FoodOrderTool(adb_bridge)
        restaurants = food.search_restaurants("pizza")
        menu = food.get_menu("Domino's Pizza")
        food.place_order("Domino's Pizza", [{"name": "Margherita", "qty": 1}])
    """

    def __init__(self, adb: ADBBridge) -> None:
        """
        Initialize the FoodOrderTool.

        Args:
            adb: ADBBridge instance.
        """
        self.adb = adb
        self.browser = BrowserTool(adb)
        self.delivery_address = os.environ.get(
            "UBEREATS_DELIVERY_ADDRESS", "Frankfort, IL"
        )
        self._cart: list[CartItem] = []

    def search_restaurants(
        self,
        query: str,
        location: Optional[str] = None,
    ) -> list[Restaurant]:
        """
        Search for restaurants on UberEats.

        Args:
            query: Search query (cuisine type, restaurant name, dish).
            location: Delivery location (default: configured address).

        Returns:
            List of Restaurant objects.
        """
        loc = location or self.delivery_address

        # Try native app first
        if self._open_ubereats_app():
            return self._search_via_app(query)

        # Fallback: web
        return self._search_via_web(query, loc)

    def get_menu(self, restaurant_name: str) -> list[MenuItem]:
        """
        Get the menu for a specific restaurant.

        Args:
            restaurant_name: Name of the restaurant.

        Returns:
            List of MenuItem objects.
        """
        try:
            # Build search URL
            enc_name = urllib.parse.quote(restaurant_name)
            enc_addr = urllib.parse.quote(self.delivery_address)
            url = f"{UBEREATS_WEB}/search?q={enc_name}&pl={enc_addr}"

            self.browser.navigate(url)
            time.sleep(2)

            # Click first restaurant result
            self.browser.click_element(restaurant_name)
            time.sleep(2)

            # Extract menu items from screen
            page_text = self.browser.get_page_text()
            return self._parse_menu_items(page_text)

        except Exception as e:
            logger.error("Failed to get menu for %s: %s", restaurant_name, e)
            return []

    def place_order(
        self,
        restaurant: str,
        items: list[dict],
        delivery_address: Optional[str] = None,
    ) -> Optional[Order]:
        """
        Place a food order on UberEats.

        Args:
            restaurant: Restaurant name.
            items: List of dicts with "name" and optional "qty", "instructions".
            delivery_address: Delivery address (default: configured address).

        Returns:
            Order object if placed successfully, else None.

        Note: This opens UberEats and navigates through the order flow.
        Actual placement requires user confirmation for payment.
        """
        addr = delivery_address or self.delivery_address
        logger.info("Placing order at %s: %s items", restaurant, len(items))

        try:
            # Open UberEats app
            if not self._open_ubereats_app():
                logger.error("UberEats app not available")
                return None

            time.sleep(2)

            # Search for restaurant
            from agent.android.screen_reader import ScreenReader
            reader = ScreenReader(self.adb)
            search_fields = reader.get_edit_fields()

            if search_fields:
                x, y = search_fields[0].center()
                self.adb.tap(x, y)
                time.sleep(0.3)
                self.adb.type_text(restaurant)
                time.sleep(1)

            # Click on restaurant
            self.browser.click_element(restaurant)
            time.sleep(2)

            # Add items to cart
            for item_spec in items:
                item_name = item_spec.get("name", "")
                qty = item_spec.get("qty", 1)
                instructions = item_spec.get("instructions", "")

                for _ in range(qty):
                    self.browser.click_element(item_name)
                    time.sleep(0.5)

            # Note: Return a pending order (actual payment requires user action)
            return Order(
                order_id="PENDING",
                restaurant=restaurant,
                items=[CartItem(
                    item=MenuItem(name=i.get("name", ""), price=""),
                    quantity=i.get("qty", 1),
                ) for i in items],
                total="",
                status="pending_payment",
                estimated_delivery="30-45 min",
            )

        except Exception as e:
            logger.error("Failed to place order: %s", e)
            return None

    def get_order_status(self, order_id: Optional[str] = None) -> Optional[Order]:
        """
        Get the status of a current or recent order.

        Args:
            order_id: Optional order ID to look up.

        Returns:
            Order object with current status.
        """
        try:
            self._open_ubereats_app()
            time.sleep(1)

            # Navigate to orders screen
            self.browser.click_element("Orders")
            time.sleep(1)

            page_text = self.browser.get_page_text()
            # Parse basic status from screen text
            if "Arriving" in page_text or "on the way" in page_text.lower():
                status = "on_the_way"
            elif "Preparing" in page_text:
                status = "preparing"
            elif "Picked up" in page_text:
                status = "picked_up"
            elif "Delivered" in page_text:
                status = "delivered"
            else:
                status = "unknown"

            return Order(
                order_id=order_id or "current",
                restaurant="",
                items=[],
                total="",
                status=status,
            )

        except Exception as e:
            logger.error("Failed to get order status: %s", e)
            return None

    def get_cart(self) -> list[CartItem]:
        """Return the current in-memory cart."""
        return self._cart

    def clear_cart(self) -> None:
        """Clear the in-memory cart."""
        self._cart.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _open_ubereats_app(self) -> bool:
        """Open the UberEats app."""
        try:
            self.adb._shell(
                f"am start -n {UBEREATS_PACKAGE}/.app.MainActivity "
                f"2>/dev/null || "
                f"monkey -p {UBEREATS_PACKAGE} -c android.intent.category.LAUNCHER 1"
            )
            time.sleep(2)
            return True
        except ADBBridge.ADBError:
            return False

    def _search_via_app(self, query: str) -> list[Restaurant]:
        """Search for restaurants via the UberEats app."""
        from agent.android.screen_reader import ScreenReader
        reader = ScreenReader(self.adb)

        try:
            # Tap search
            self.browser.click_element("Search")
            time.sleep(0.5)

            # Type query
            fields = reader.get_edit_fields()
            if fields:
                x, y = fields[0].center()
                self.adb.tap(x, y)
                self.adb.type_text(query)
                time.sleep(1)

            page_text = reader.get_screen_text()
            return self._parse_restaurants(page_text)

        except Exception:
            return []

    def _search_via_web(self, query: str, location: str) -> list[Restaurant]:
        """Search for restaurants via UberEats web."""
        enc_query = urllib.parse.quote(query)
        enc_loc = urllib.parse.quote(location)
        self.browser.navigate(f"{UBEREATS_WEB}/search?q={enc_query}&pl={enc_loc}")
        time.sleep(2)
        page_text = self.browser.get_page_text()
        return self._parse_restaurants(page_text)

    def _parse_restaurants(self, text: str) -> list[Restaurant]:
        """Best-effort parser for restaurant listings from screen text."""
        restaurants: list[Restaurant] = []
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        for i, line in enumerate(lines[:50]):  # Scan first 50 lines
            # Heuristic: lines with ratings and delivery info look like restaurants
            if "★" in line or "min" in line.lower():
                name = lines[i - 1] if i > 0 else line
                restaurants.append(Restaurant(
                    name=name,
                    rating=self._extract_rating(line),
                    delivery_time=self._extract_delivery_time(line),
                ))

        return restaurants[:10]

    def _parse_menu_items(self, text: str) -> list[MenuItem]:
        """Best-effort menu item parser."""
        items: list[MenuItem] = []
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        for i, line in enumerate(lines):
            if "$" in line:
                name = lines[i - 1] if i > 0 else line
                items.append(MenuItem(name=name, price=line))

        return items[:30]

    def _extract_rating(self, text: str) -> float:
        """Extract numeric rating from text."""
        import re
        match = re.search(r"★?\s*(\d+\.?\d*)", text)
        return float(match.group(1)) if match else 0.0

    def _extract_delivery_time(self, text: str) -> str:
        """Extract delivery time estimate from text."""
        import re
        match = re.search(r"(\d+[-–]\d+\s*min)", text, re.IGNORECASE)
        return match.group(1) if match else ""
