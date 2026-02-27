"""
P1-22: Browser Tool

Controls Chrome on Android via ADB intents and accessibility service.
Supports navigation, content extraction, form filling, and screenshots.

Requires:
- Chrome (com.android.chrome) installed on device
- Accessibility service for DOM interaction
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

from agent.android.adb_bridge import ADBBridge

logger = logging.getLogger(__name__)

CHROME_PACKAGE = "com.android.chrome"
CHROME_ACTIVITY = "com.google.android.apps.chrome.Main"


class BrowserTool:
    """
    Web browser control tool for Android using ADB + Chrome.

    Usage:
        browser = BrowserTool(adb_bridge)
        browser.navigate("https://example.com")
        text = browser.get_page_text()
    """

    def __init__(self, adb: ADBBridge) -> None:
        """
        Initialize the BrowserTool.

        Args:
            adb: ADBBridge instance.
        """
        self.adb = adb
        self._current_url: str = ""

    def navigate(self, url: str) -> bool:
        """
        Navigate Chrome to the given URL.

        Args:
            url: URL to navigate to.

        Returns:
            True if navigation intent was dispatched.
        """
        try:
            # Ensure URL has scheme
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            # Use ACTION_VIEW intent to open URL in Chrome
            self.adb._shell(
                f"am start -a android.intent.action.VIEW "
                f"-d '{url}' "
                f"-n {CHROME_PACKAGE}/{CHROME_ACTIVITY}"
            )
            self._current_url = url
            # Wait for page load
            time.sleep(2.0)
            logger.info("Navigated to: %s", url)
            return True

        except ADBBridge.ADBError as e:
            logger.error("Failed to navigate to %s: %s", url, e)
            return False

    def get_page_text(self) -> str:
        """
        Extract visible text from the current browser page.

        Uses uiautomator dump to get all visible text elements in Chrome.

        Returns:
            Extracted text content from the page.
        """
        try:
            from agent.android.screen_reader import ScreenReader
            reader = ScreenReader(self.adb)
            screen_text = reader.get_screen_text()
            return screen_text
        except Exception as e:
            logger.error("Failed to get page text: %s", e)
            return ""

    def get_page_title(self) -> str:
        """
        Get the current page title from the Chrome address bar.

        Returns:
            Page title string, or empty string if not found.
        """
        try:
            from agent.android.screen_reader import ScreenReader
            reader = ScreenReader(self.adb)
            # The page title or URL is usually in the Chrome toolbar
            elements = reader.find_text_on_screen(self._current_url.split("/")[-1])
            if elements:
                return elements[0].text
            # Try to get from window manager
            output = self.adb._shell(
                "dumpsys window windows | grep -i 'mCurrentFocus' | head -1"
            )
            match = re.search(r'Chrome.*?"([^"]+)"', output)
            if match:
                return match.group(1)
            return self._current_url
        except Exception as e:
            logger.error("Failed to get page title: %s", e)
            return ""

    def click_element(self, selector: str) -> bool:
        """
        Click a UI element identified by text or resource ID.

        Args:
            selector: Text content or resource ID of the element to click.

        Returns:
            True if element was found and clicked.
        """
        try:
            from agent.android.screen_reader import ScreenReader
            reader = ScreenReader(self.adb)

            # Try to find by text first
            elements = reader.find_text_on_screen(selector)
            if elements:
                x, y = elements[0].center()
                self.adb.tap(x, y)
                time.sleep(0.5)
                logger.debug("Clicked element: %s at (%d, %d)", selector, x, y)
                return True

            # Try to find by resource ID
            clickable = reader.get_clickable_elements()
            for el in clickable:
                if selector in el.resource_id:
                    x, y = el.center()
                    self.adb.tap(x, y)
                    return True

            logger.warning("Element not found: %s", selector)
            return False

        except Exception as e:
            logger.error("Failed to click element %s: %s", selector, e)
            return False

    def fill_form(self, fields: dict[str, str]) -> bool:
        """
        Fill form fields with given values.

        Args:
            fields: Dict mapping field label/hint to value.
                    e.g., {"Email": "user@example.com", "Password": "secret"}

        Returns:
            True if all fields were filled.
        """
        try:
            from agent.android.screen_reader import ScreenReader
            reader = ScreenReader(self.adb)
            success = True

            for field_label, value in fields.items():
                # Find the edit field by its label or hint text
                matches = reader.find_text_on_screen(field_label)
                edit_fields = reader.get_edit_fields()

                field_found = False

                # Try to find by hint/label proximity
                for match in matches:
                    for ef in edit_fields:
                        # If edit field is near the label
                        if abs(ef.bounds[1] - match.bounds[1]) < 200:
                            x, y = ef.center()
                            self.adb.tap(x, y)
                            time.sleep(0.3)
                            self.adb.type_text(value)
                            field_found = True
                            break
                    if field_found:
                        break

                # Direct approach: tap edit fields in order
                if not field_found and edit_fields:
                    for ef in edit_fields:
                        if not ef.text and not ef.content_desc:
                            x, y = ef.center()
                            self.adb.tap(x, y)
                            time.sleep(0.3)
                            self.adb.type_text(value)
                            field_found = True
                            break

                if not field_found:
                    logger.warning("Could not find form field: %s", field_label)
                    success = False

                time.sleep(0.2)

            return success

        except Exception as e:
            logger.error("Failed to fill form: %s", e)
            return False

    def take_screenshot(self, save_path: Optional[str] = None) -> str:
        """
        Take a screenshot of the current browser state.

        Args:
            save_path: Optional local path to save screenshot.

        Returns:
            Local path to the saved screenshot.
        """
        return self.adb.take_screenshot(local_path=save_path)

    def go_back(self) -> bool:
        """
        Navigate back in browser history.

        Returns:
            True if back command was sent.
        """
        try:
            self.adb.press_key(4)  # KEYCODE_BACK
            time.sleep(0.5)
            logger.debug("Navigated back")
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to go back: %s", e)
            return False

    def go_forward(self) -> bool:
        """
        Navigate forward in browser history (Chrome menu → Forward).

        Returns:
            True if forward navigation was attempted.
        """
        try:
            # Chrome: long press back for forward (or use menu)
            self.adb.press_key("KEYCODE_FORWARD")
            time.sleep(0.5)
            return True
        except ADBBridge.ADBError:
            return False

    def reload(self) -> bool:
        """Reload the current page."""
        if self._current_url:
            return self.navigate(self._current_url)
        return False

    def search_on_page(self, query: str) -> list[str]:
        """
        Search for text on the current page using Chrome find-in-page.

        Args:
            query: Text to find.

        Returns:
            List of matching text snippets visible on screen.
        """
        try:
            from agent.android.screen_reader import ScreenReader
            reader = ScreenReader(self.adb)
            matches = reader.find_text_on_screen(query)
            return [m.text for m in matches]
        except Exception as e:
            logger.error("Failed to search on page: %s", e)
            return []

    def scroll_down(self, amount: int = 1) -> bool:
        """Scroll the page down."""
        try:
            width, height = self.adb.get_screen_size()
            cx = width // 2
            for _ in range(amount):
                self.adb.swipe(cx, int(height * 0.7), cx, int(height * 0.3), 300)
                time.sleep(0.2)
            return True
        except ADBBridge.ADBError:
            return False

    @property
    def current_url(self) -> str:
        """Return the current URL."""
        return self._current_url
