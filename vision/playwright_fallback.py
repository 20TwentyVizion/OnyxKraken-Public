"""Playwright Fallback — DOM-level web interaction when vision fails.

When the WebVisionEngine's OpenCV + vision model approach can't find an
element (e.g., the page has unusual styling, or the element is hidden behind
overlays), this module provides direct DOM access via Playwright.

Two modes:
    HEADED   — Launches a visible Chromium window (useful for demos, debugging)
    HEADLESS — No visible window (useful for background tasks, CI)

Can also connect to the user's existing Chrome session via CDP (Chrome DevTools
Protocol) for interacting with pages the user is already logged into.

Architecture:
    PlaywrightBrowser  — manages browser lifecycle + page access
    DOMInteractor      — find/click/type/scroll via CSS/XPath selectors
    SelectorStrategy   — generates selectors from visual descriptions

Usage:
    from vision.playwright_fallback import PlaywrightBrowser

    browser = PlaywrightBrowser(headless=False)
    browser.navigate("https://www.reddit.com/r/test/submit")
    browser.click_by_text("Create Post")
    browser.type_into("title", "My post title")
    browser.click_by_text("Post")
    browser.close()
"""

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_log = logging.getLogger("vision.playwright_fallback")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class DOMElement:
    """A DOM element found via Playwright."""
    selector: str
    tag: str = ""
    text: str = ""
    placeholder: str = ""
    role: str = ""
    aria_label: str = ""
    visible: bool = True
    enabled: bool = True
    bounding_box: Optional[Dict] = None  # {x, y, width, height}


@dataclass
class PlaywrightResult:
    """Result of a Playwright interaction."""
    ok: bool
    method: str = "playwright"
    selector: str = ""
    error: str = ""
    details: str = ""
    page_url: str = ""


# ---------------------------------------------------------------------------
# Selector strategies — how to find elements by description
# ---------------------------------------------------------------------------

class SelectorStrategy:
    """Generates CSS/XPath selectors from visual element descriptions.

    Maps human-readable labels (like "Create Post", "Title field") to
    multiple selector strategies, tried in order of specificity.
    """

    @staticmethod
    def for_button(label: str) -> List[str]:
        """Generate selectors for a button with the given label."""
        escaped = label.replace("'", "\\'")
        return [
            f"button:has-text('{escaped}')",
            f"[role='button']:has-text('{escaped}')",
            f"a:has-text('{escaped}')",
            f"input[type='submit'][value='{escaped}']",
            f"input[type='button'][value='{escaped}']",
            f"[data-testid*='{label.lower().replace(' ', '')}']",
            f"text='{escaped}'",
        ]

    @staticmethod
    def for_text_field(label: str) -> List[str]:
        """Generate selectors for a text input with the given label."""
        escaped = label.replace("'", "\\'")
        lower = label.lower()
        return [
            f"input[placeholder*='{escaped}' i]",
            f"textarea[placeholder*='{escaped}' i]",
            f"[aria-label*='{escaped}' i]",
            f"input[name*='{lower}']",
            f"textarea[name*='{lower}']",
            f"label:has-text('{escaped}') + input",
            f"label:has-text('{escaped}') + textarea",
            f"[data-testid*='{lower.replace(' ', '')}'] input",
            f"[data-testid*='{lower.replace(' ', '')}'] textarea",
            f"[contenteditable='true'][aria-label*='{escaped}' i]",
            f"[contenteditable='true'][data-placeholder*='{escaped}' i]",
        ]

    @staticmethod
    def for_link(label: str) -> List[str]:
        """Generate selectors for a link with the given text."""
        escaped = label.replace("'", "\\'")
        return [
            f"a:has-text('{escaped}')",
            f"[role='link']:has-text('{escaped}')",
            f"text='{escaped}'",
        ]

    @staticmethod
    def for_any(label: str, element_type: str = "") -> List[str]:
        """Generate selectors based on element type, or try all strategies."""
        if element_type == "button":
            return SelectorStrategy.for_button(label)
        elif element_type == "text_field":
            return SelectorStrategy.for_text_field(label)
        elif element_type == "link":
            return SelectorStrategy.for_link(label)
        else:
            # Try all strategies
            selectors = []
            selectors.extend(SelectorStrategy.for_button(label))
            selectors.extend(SelectorStrategy.for_text_field(label))
            selectors.extend(SelectorStrategy.for_link(label))
            return selectors


# ---------------------------------------------------------------------------
# PlaywrightBrowser — browser lifecycle + interaction
# ---------------------------------------------------------------------------

class PlaywrightBrowser:
    """Manages a Playwright browser instance for DOM-level web interaction.

    This is the fallback when vision-based detection fails. It provides
    direct access to the DOM for reliable element finding and interaction.

    Usage:
        browser = PlaywrightBrowser(headless=False)
        browser.navigate("https://www.reddit.com")
        browser.click_by_text("Create Post")
        browser.type_into("Title", "My post")
        browser.close()
    """

    def __init__(self, headless: bool = False, timeout: float = 30000):
        """Initialize Playwright browser.

        Args:
            headless: If True, no visible browser window.
            timeout: Default timeout for operations in milliseconds.
        """
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._headless = headless
        self._timeout = timeout
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Launch the browser. Returns True if successful."""
        if self._started:
            return True
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=self._headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            self._context = self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            self._context.set_default_timeout(self._timeout)
            self._page = self._context.new_page()
            self._started = True
            _log.info("Playwright browser started (headless=%s)", self._headless)
            return True
        except Exception as e:
            _log.error("Failed to start Playwright browser: %s", e)
            return False

    def connect_cdp(self, endpoint: str = "http://localhost:9222") -> bool:
        """Connect to an existing Chrome instance via CDP.

        This allows interacting with pages the user is already logged into
        (Reddit, Twitter, YouTube, etc.) without needing to log in again.

        Launch Chrome with: chrome.exe --remote-debugging-port=9222

        Args:
            endpoint: CDP endpoint URL.

        Returns:
            True if connected successfully.
        """
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(endpoint)
            contexts = self._browser.contexts
            if contexts:
                self._context = contexts[0]
                pages = self._context.pages
                if pages:
                    self._page = pages[0]
                else:
                    self._page = self._context.new_page()
            else:
                self._context = self._browser.new_context()
                self._page = self._context.new_page()
            self._started = True
            _log.info("Connected to existing Chrome via CDP at %s", endpoint)
            return True
        except Exception as e:
            _log.error("Failed to connect via CDP: %s", e)
            return False

    def close(self):
        """Close the browser and clean up."""
        try:
            if self._page:
                self._page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            _log.debug("Cleanup error: %s", e)
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self._started = False
            _log.info("Playwright browser closed")

    def _ensure_started(self) -> bool:
        if not self._started:
            return self.start()
        return True

    @property
    def page(self):
        """Access the current Playwright page for advanced usage."""
        return self._page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, url: str, wait_until: str = "domcontentloaded") -> PlaywrightResult:
        """Navigate to a URL.

        Args:
            url: Target URL.
            wait_until: When to consider navigation done.
                "domcontentloaded" — DOM is ready (fast).
                "load" — All resources loaded (slow but complete).
                "networkidle" — No network activity for 500ms.
        """
        if not self._ensure_started():
            return PlaywrightResult(ok=False, error="Browser not started")
        try:
            self._page.goto(url, wait_until=wait_until)
            _log.info("Navigated to %s", url)
            return PlaywrightResult(
                ok=True, details=f"Navigated to {url}",
                page_url=self._page.url,
            )
        except Exception as e:
            _log.error("Navigation failed: %s", e)
            return PlaywrightResult(ok=False, error=str(e))

    def wait_for_load(self, timeout: float = 10000) -> PlaywrightResult:
        """Wait for page to finish loading."""
        if not self._page:
            return PlaywrightResult(ok=False, error="No page")
        try:
            self._page.wait_for_load_state("networkidle", timeout=timeout)
            return PlaywrightResult(ok=True, details="Page loaded")
        except Exception as e:
            return PlaywrightResult(ok=False, error=f"Load timeout: {e}")

    # ------------------------------------------------------------------
    # Element finding
    # ------------------------------------------------------------------

    def find_element(self, label: str,
                     element_type: str = "",
                     timeout: float = 5000) -> Optional[DOMElement]:
        """Find a DOM element by its label using multiple selector strategies.

        Args:
            label: Visual label of the element (e.g., "Create Post", "Title").
            element_type: Optional type hint ("button", "text_field", "link").
            timeout: Max time to wait for element (ms).

        Returns:
            DOMElement if found, None otherwise.
        """
        if not self._page:
            return None

        selectors = SelectorStrategy.for_any(label, element_type)

        for selector in selectors:
            try:
                locator = self._page.locator(selector).first
                if locator.is_visible(timeout=min(timeout, 2000)):
                    bbox = None
                    try:
                        bbox = locator.bounding_box()
                    except Exception:
                        pass
                    tag = locator.evaluate("el => el.tagName.toLowerCase()")
                    text_content = ""
                    try:
                        text_content = locator.text_content() or ""
                    except Exception:
                        pass
                    return DOMElement(
                        selector=selector,
                        tag=tag,
                        text=text_content[:200],
                        bounding_box=bbox,
                        visible=True,
                        enabled=locator.is_enabled(),
                    )
            except Exception:
                continue

        _log.debug("Element '%s' not found with any selector strategy", label)
        return None

    def find_all_interactive(self) -> List[DOMElement]:
        """Find all interactive elements on the current page.

        Useful for debugging — shows what Playwright can see.
        """
        if not self._page:
            return []

        elements = []
        try:
            # Buttons
            for btn in self._page.locator("button:visible").all():
                try:
                    elements.append(DOMElement(
                        selector="button",
                        tag="button",
                        text=(btn.text_content() or "")[:100],
                        visible=True,
                    ))
                except Exception:
                    pass

            # Text inputs
            for inp in self._page.locator("input[type='text']:visible, input:not([type]):visible, textarea:visible").all():
                try:
                    elements.append(DOMElement(
                        selector="input/textarea",
                        tag=inp.evaluate("el => el.tagName.toLowerCase()"),
                        placeholder=inp.get_attribute("placeholder") or "",
                        aria_label=inp.get_attribute("aria-label") or "",
                        visible=True,
                    ))
                except Exception:
                    pass

            # Links
            for link in self._page.locator("a:visible").all()[:20]:
                try:
                    elements.append(DOMElement(
                        selector="a",
                        tag="a",
                        text=(link.text_content() or "")[:100],
                        visible=True,
                    ))
                except Exception:
                    pass
        except Exception as e:
            _log.warning("Error scanning interactive elements: %s", e)

        return elements

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def click_by_text(self, label: str,
                      element_type: str = "") -> PlaywrightResult:
        """Click an element found by its visible text label."""
        if not self._page:
            return PlaywrightResult(ok=False, error="No page")

        element = self.find_element(label, element_type)
        if not element:
            return PlaywrightResult(
                ok=False,
                error=f"Element '{label}' not found in DOM",
            )

        try:
            self._page.locator(element.selector).first.click()
            _log.info("Playwright clicked '%s' via %s", label, element.selector)
            return PlaywrightResult(
                ok=True,
                selector=element.selector,
                details=f"Clicked '{label}'",
                page_url=self._page.url,
            )
        except Exception as e:
            return PlaywrightResult(ok=False, error=f"Click failed: {e}")

    def type_into(self, field_label: str, text: str,
                  clear_first: bool = True) -> PlaywrightResult:
        """Type text into a field found by its label.

        Args:
            field_label: Label of the field (placeholder, aria-label, name, etc.).
            text: Text to type.
            clear_first: Whether to clear existing content first.
        """
        if not self._page:
            return PlaywrightResult(ok=False, error="No page")

        element = self.find_element(field_label, element_type="text_field")
        if not element:
            return PlaywrightResult(
                ok=False,
                error=f"Text field '{field_label}' not found in DOM",
            )

        try:
            locator = self._page.locator(element.selector).first
            if clear_first:
                locator.fill(text)
            else:
                locator.type(text, delay=30)
            _log.info("Playwright typed into '%s' via %s", field_label, element.selector)
            return PlaywrightResult(
                ok=True,
                selector=element.selector,
                details=f"Typed into '{field_label}'",
            )
        except Exception as e:
            return PlaywrightResult(ok=False, error=f"Type failed: {e}")

    def press_key(self, key: str) -> PlaywrightResult:
        """Press a keyboard key on the page."""
        if not self._page:
            return PlaywrightResult(ok=False, error="No page")
        try:
            self._page.keyboard.press(key)
            return PlaywrightResult(ok=True, details=f"Pressed {key}")
        except Exception as e:
            return PlaywrightResult(ok=False, error=f"Key press failed: {e}")

    def scroll_page(self, direction: str = "down",
                    amount: int = 300) -> PlaywrightResult:
        """Scroll the page."""
        if not self._page:
            return PlaywrightResult(ok=False, error="No page")
        try:
            delta = amount if direction == "down" else -amount
            self._page.mouse.wheel(0, delta)
            time.sleep(0.3)
            return PlaywrightResult(ok=True, details=f"Scrolled {direction} {amount}px")
        except Exception as e:
            return PlaywrightResult(ok=False, error=f"Scroll failed: {e}")

    def screenshot(self, path: str = "") -> str:
        """Take a screenshot. Returns the file path."""
        if not self._page:
            return ""
        if not path:
            debug_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data", "debug_screenshots",
            )
            os.makedirs(debug_dir, exist_ok=True)
            path = os.path.join(debug_dir, f"pw_{int(time.time())}.png")
        try:
            self._page.screenshot(path=path)
            return path
        except Exception as e:
            _log.warning("Screenshot failed: %s", e)
            return ""

    def get_page_text(self) -> str:
        """Get all visible text on the page."""
        if not self._page:
            return ""
        try:
            return self._page.inner_text("body")[:5000]
        except Exception:
            return ""

    def get_page_url(self) -> str:
        """Get the current page URL."""
        if not self._page:
            return ""
        return self._page.url

    # ------------------------------------------------------------------
    # Convenience: wait for element
    # ------------------------------------------------------------------

    def wait_for_element(self, label: str,
                         element_type: str = "",
                         timeout: float = 10000) -> Optional[DOMElement]:
        """Wait for an element to appear in the DOM."""
        if not self._page:
            return None

        selectors = SelectorStrategy.for_any(label, element_type)
        for selector in selectors:
            try:
                locator = self._page.locator(selector).first
                locator.wait_for(state="visible", timeout=timeout)
                tag = locator.evaluate("el => el.tagName.toLowerCase()")
                return DOMElement(
                    selector=selector,
                    tag=tag,
                    text=(locator.text_content() or "")[:200],
                    visible=True,
                )
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.close()
