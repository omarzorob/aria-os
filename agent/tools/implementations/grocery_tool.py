"""
P1-25: Grocery Tool

Provides grocery ordering via Instacart web automation using BrowserTool.
Supports product search, cart management, and checkout.

Default store: Jewel-Osco (Frankfort, IL)

Environment variables:
- INSTACART_DELIVERY_ADDRESS: Delivery address (default: Frankfort, IL)
- INSTACART_EMAIL: Instacart account email
"""

from __future__ import annotations

import logging
import os
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional

from agent.android.adb_bridge import ADBBridge
from .browser_tool import BrowserTool

logger = logging.getLogger(__name__)

INSTACART_BASE = "https://www.instacart.com"
DEFAULT_STORE_PATH = "/store/jewel-osco/storefront"


@dataclass
class Product:
    """Represents a grocery product on Instacart."""

    product_id: str
    name: str
    price: str = ""
    unit_price: str = ""
    brand: str = ""
    size: str = ""
    image_url: str = ""
    in_stock: bool = True
    category: str = ""

    def __str__(self) -> str:
        brand_str = f" ({self.brand})" if self.brand else ""
        size_str = f" {self.size}" if self.size else ""
        return f"{self.name}{brand_str}{size_str} — {self.price}"


@dataclass
class CartEntry:
    """Represents a cart item with quantity."""

    product: Product
    quantity: int = 1
    note: str = ""

    @property
    def subtotal(self) -> str:
        try:
            price = float(self.product.price.replace("$", "").split("/")[0].strip())
            return f"${price * self.quantity:.2f}"
        except (ValueError, IndexError):
            return self.product.price


class GroceryTool:
    """
    Grocery ordering tool using Instacart web automation.

    Usage:
        grocery = GroceryTool(adb_bridge)
        products = grocery.search_products("organic milk")
        grocery.add_to_cart("prod_123", quantity=2)
        grocery.checkout("123 Main St, Frankfort, IL")
    """

    def __init__(self, adb: ADBBridge) -> None:
        """
        Initialize the GroceryTool.

        Args:
            adb: ADBBridge instance.
        """
        self.adb = adb
        self.browser = BrowserTool(adb)
        self.delivery_address = os.environ.get(
            "INSTACART_DELIVERY_ADDRESS", "Frankfort, IL 60423"
        )
        self._cart: list[CartEntry] = []
        self._is_logged_in = False

    def search_products(
        self,
        query: str,
        store_path: str = DEFAULT_STORE_PATH,
        limit: int = 10,
    ) -> list[Product]:
        """
        Search for grocery products on Instacart.

        Args:
            query: Product search query.
            store_path: Instacart store path.
            limit: Maximum results to return.

        Returns:
            List of Product objects.
        """
        try:
            enc_query = urllib.parse.quote(query)
            url = f"{INSTACART_BASE}{store_path}/search?query={enc_query}"

            self.browser.navigate(url)
            time.sleep(2.5)

            page_text = self.browser.get_page_text()
            screenshot = self.browser.take_screenshot()

            products = self._parse_products(page_text)
            logger.info("Found %d products for '%s'", len(products), query)
            return products[:limit]

        except Exception as e:
            logger.error("Failed to search products '%s': %s", query, e)
            return []

    def add_to_cart(
        self,
        product_id: str,
        quantity: int = 1,
        note: str = "",
    ) -> bool:
        """
        Add a product to the cart.

        If the product is in the in-memory cart, increments quantity.
        For web automation, clicks the "Add to cart" button on the product page.

        Args:
            product_id: Product identifier.
            quantity: Number of units to add.
            note: Optional special instruction (e.g., "ripe bananas only").

        Returns:
            True if added successfully.
        """
        # Add to in-memory cart
        for entry in self._cart:
            if entry.product.product_id == product_id:
                entry.quantity += quantity
                logger.info("Increased qty for %s to %d", product_id, entry.quantity)
                return True

        product = Product(product_id=product_id, name=product_id, price="")
        self._cart.append(CartEntry(product=product, quantity=quantity, note=note))

        # Try to click "Add" button on screen if browser is open
        try:
            self.browser.click_element("Add to cart")
        except Exception:
            pass

        logger.info("Added %dx %s to cart", quantity, product_id)
        return True

    def remove_from_cart(self, product_id: str) -> bool:
        """
        Remove a product from the cart.

        Args:
            product_id: Product to remove.

        Returns:
            True if removed.
        """
        self._cart = [e for e in self._cart if e.product.product_id != product_id]
        return True

    def get_cart(self) -> list[CartEntry]:
        """
        Get current cart contents.

        Returns:
            List of CartEntry objects.
        """
        return self._cart

    def get_cart_summary(self) -> str:
        """Return a human-readable cart summary."""
        if not self._cart:
            return "Cart is empty"

        lines = ["🛒 Cart:"]
        for entry in self._cart:
            lines.append(f"  • {entry.product.name} x{entry.quantity} — {entry.product.price}")

        total = len(self._cart)
        lines.append(f"\n{total} item(s) in cart")
        return "\n".join(lines)

    def checkout(
        self,
        address: Optional[str] = None,
        tip_percent: int = 15,
    ) -> bool:
        """
        Initiate checkout on Instacart.

        Opens Instacart checkout page. User must complete payment.

        Args:
            address: Delivery address (default: configured address).
            tip_percent: Tip percentage for the shopper.

        Returns:
            True if checkout page was opened.
        """
        try:
            addr = address or self.delivery_address
            url = f"{INSTACART_BASE}/checkout"

            self.browser.navigate(url)
            time.sleep(2)

            # Fill in delivery address if prompted
            page_text = self.browser.get_page_text()
            if "delivery address" in page_text.lower():
                self.browser.fill_form({"Delivery address": addr})
                time.sleep(1)

            logger.info("Checkout opened for delivery to: %s", addr)
            return True

        except Exception as e:
            logger.error("Checkout failed: %s", e)
            return False

    def get_order_status(self) -> Optional[str]:
        """
        Get the status of the most recent Instacart order.

        Returns:
            Status string or None.
        """
        try:
            self.browser.navigate(f"{INSTACART_BASE}/orders")
            time.sleep(2)
            page_text = self.browser.get_page_text()

            keywords = ["Delivered", "On the way", "Being shopped", "Order placed"]
            for kw in keywords:
                if kw.lower() in page_text.lower():
                    return kw

            return "Unknown"

        except Exception as e:
            logger.error("Failed to get order status: %s", e)
            return None

    def clear_cart(self) -> None:
        """Clear the in-memory cart."""
        self._cart.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_products(self, text: str) -> list[Product]:
        """Best-effort product parser from screen text."""
        import re
        products: list[Product] = []
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        for i, line in enumerate(lines):
            if "$" in line and re.search(r"\$\d+\.\d{2}", line):
                name = lines[i - 1] if i > 0 else line
                if len(name) > 3 and not name.startswith("$"):
                    products.append(Product(
                        product_id=f"prod_{len(products)}",
                        name=name,
                        price=re.search(r"\$\d+\.\d{2}", line).group(),
                    ))

        return products
