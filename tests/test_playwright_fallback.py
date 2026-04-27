"""Tests for Playwright fallback — DOM-level web interaction.

Tests the selector strategies, browser lifecycle, and DOM interaction
without needing a live web server (uses data: URLs and inline HTML).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name}")
        failed += 1


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

print("=== DOMElement & PlaywrightResult ===")
from vision.playwright_fallback import DOMElement, PlaywrightResult, SelectorStrategy, PlaywrightBrowser

el = DOMElement(
    selector="button:has-text('Submit')",
    tag="button",
    text="Submit",
    visible=True,
    enabled=True,
)
check("element selector", el.selector == "button:has-text('Submit')")
check("element tag", el.tag == "button")
check("element text", el.text == "Submit")
check("element visible", el.visible)
check("element enabled", el.enabled)

result = PlaywrightResult(ok=True, selector="button", details="Clicked Submit")
check("result ok", result.ok)
check("result method", result.method == "playwright")
check("result selector", result.selector == "button")

fail_result = PlaywrightResult(ok=False, error="Element not found")
check("fail result", not fail_result.ok)
check("fail error", fail_result.error == "Element not found")


# ---------------------------------------------------------------------------
# Selector strategies
# ---------------------------------------------------------------------------

print("\n=== SelectorStrategy ===")

# Button selectors
btn_selectors = SelectorStrategy.for_button("Create Post")
check("button selectors non-empty", len(btn_selectors) > 0)
check("button has :has-text", any(":has-text('Create Post')" in s for s in btn_selectors))
check("button has role=button", any("role='button'" in s for s in btn_selectors))
check("button has text=", any("text=" in s for s in btn_selectors))
print(f"  Button selectors ({len(btn_selectors)}): {btn_selectors[:3]}...")

# Text field selectors
field_selectors = SelectorStrategy.for_text_field("Title")
check("field selectors non-empty", len(field_selectors) > 0)
check("field has placeholder", any("placeholder" in s for s in field_selectors))
check("field has aria-label", any("aria-label" in s for s in field_selectors))
check("field has name", any("name" in s for s in field_selectors))
check("field has contenteditable", any("contenteditable" in s for s in field_selectors))
print(f"  Field selectors ({len(field_selectors)}): {field_selectors[:3]}...")

# Link selectors
link_selectors = SelectorStrategy.for_link("Home")
check("link selectors non-empty", len(link_selectors) > 0)
check("link has a:has-text", any("a:has-text('Home')" in s for s in link_selectors))

# for_any with type hints
any_btn = SelectorStrategy.for_any("Submit", "button")
check("for_any button == for_button", any_btn == SelectorStrategy.for_button("Submit"))

any_field = SelectorStrategy.for_any("Email", "text_field")
check("for_any text_field == for_text_field", any_field == SelectorStrategy.for_text_field("Email"))

any_link = SelectorStrategy.for_any("About", "link")
check("for_any link == for_link", any_link == SelectorStrategy.for_link("About"))

# for_any without type hint — returns all strategies
any_all = SelectorStrategy.for_any("Something")
check("for_any no type returns all", len(any_all) > len(btn_selectors))

# Escaping
escaped_selectors = SelectorStrategy.for_button("It's a test")
check("escapes apostrophe", any("It\\'s a test" in s for s in escaped_selectors))


# ---------------------------------------------------------------------------
# PlaywrightBrowser construction
# ---------------------------------------------------------------------------

print("\n=== PlaywrightBrowser construction ===")
browser = PlaywrightBrowser(headless=True, timeout=5000)
check("browser created", browser is not None)
check("browser not started", not browser._started)
check("browser headless", browser._headless)
check("browser timeout", browser._timeout == 5000)
check("browser page None", browser.page is None)


# ---------------------------------------------------------------------------
# PlaywrightBrowser lifecycle + DOM interaction (headless)
# ---------------------------------------------------------------------------

print("\n=== PlaywrightBrowser live tests (headless) ===")
try:
    started = browser.start()
    check("browser started", started)
    check("browser._started flag", browser._started)
    check("browser has page", browser.page is not None)

    # Set page content directly (avoids data: URL quirks with links)
    browser.page.set_content("""
    <html><body style="padding:20px">
        <h1>Test Page</h1>
        <button id="btn1">Create Post</button>
        <button id="btn2" disabled>Disabled Button</button>
        <input type="text" placeholder="Title" id="title-input">
        <textarea placeholder="Body text" id="body-input"></textarea>
        <a href="https://example.com/home" style="display:inline-block;padding:4px">Home</a>
        <a href="https://example.com/about" style="display:inline-block;padding:4px">About</a>
        <div contenteditable="true" aria-label="Rich editor">Edit here</div>
    </body></html>
    """)
    check("set_content ok", True)
    check("page has url", len(browser.get_page_url()) > 0)

    # Find elements
    btn = browser.find_element("Create Post", "button")
    check("find button", btn is not None)
    if btn:
        check("button tag", btn.tag == "button")
        check("button text has Create Post", "Create Post" in btn.text)
        check("button visible", btn.visible)
        check("button enabled", btn.enabled)

    field = browser.find_element("Title", "text_field")
    check("find text field", field is not None)
    if field:
        check("field tag is input", field.tag == "input")

    body_field = browser.find_element("Body text", "text_field")
    check("find textarea", body_field is not None)
    if body_field:
        check("textarea tag", body_field.tag == "textarea")

    link = browser.find_element("Home", "link")
    check("find link", link is not None)
    if link:
        check("link tag is a", link.tag == "a")

    # Element not found
    missing = browser.find_element("Nonexistent Button", "button", timeout=1000)
    check("missing element is None", missing is None)

    # Find all interactive elements
    all_els = browser.find_all_interactive()
    check("find_all returns list", isinstance(all_els, list))
    check("find_all found elements", len(all_els) > 0)
    tags = [e.tag for e in all_els]
    check("find_all has buttons", "button" in tags)
    check("find_all has inputs", "input" in tags or "textarea" in tags)
    check("find_all has links", "a" in tags)
    print(f"  Found {len(all_els)} interactive elements")

    # Click
    click_result = browser.click_by_text("Create Post", "button")
    check("click ok", click_result.ok)
    check("click has selector", len(click_result.selector) > 0)

    # Click missing
    click_miss = browser.click_by_text("Missing Button")
    check("click missing fails", not click_miss.ok)
    check("click missing has error", len(click_miss.error) > 0)

    # Type into field
    type_result = browser.type_into("Title", "My test post")
    check("type ok", type_result.ok)
    check("type has selector", len(type_result.selector) > 0)

    # Verify typed text
    title_val = browser.page.locator("#title-input").input_value()
    check("typed text present", title_val == "My test post")

    # Type into textarea
    type_body = browser.type_into("Body text", "Hello world")
    check("type textarea ok", type_body.ok)
    body_val = browser.page.locator("#body-input").input_value()
    check("textarea text present", body_val == "Hello world")

    # Type missing field
    type_miss = browser.type_into("Nonexistent Field", "text")
    check("type missing fails", not type_miss.ok)

    # Key press
    key_result = browser.press_key("Tab")
    check("key press ok", key_result.ok)

    # Scroll
    scroll_result = browser.scroll_page("down", 100)
    check("scroll ok", scroll_result.ok)

    # Get page text
    page_text = browser.get_page_text()
    check("page text non-empty", len(page_text) > 0)
    check("page text has content", "Test Page" in page_text)
    check("page text has button text", "Create Post" in page_text)

    # Get page URL
    page_url = browser.get_page_url()
    check("page url non-empty", len(page_url) > 0)

    # Screenshot
    ss_path = browser.screenshot()
    check("screenshot returns path", len(ss_path) > 0)
    if ss_path:
        check("screenshot file exists", os.path.isfile(ss_path))
        # Cleanup
        try:
            os.remove(ss_path)
        except Exception:
            pass

    # Wait for element (already on page)
    waited = browser.wait_for_element("Create Post", "button", timeout=2000)
    check("wait_for existing element", waited is not None)

    # Wait for missing element (should timeout quickly)
    waited_miss = browser.wait_for_element("Ghost Button", "button", timeout=1000)
    check("wait_for missing returns None", waited_miss is None)

except Exception as e:
    print(f"  SKIP: Live tests failed with: {e}")
    # Mark remaining as skipped
    for name in ["browser started", "navigate ok"]:
        check(f"SKIP: {name}", False)

finally:
    browser.close()
    check("browser closed", not browser._started)
    check("browser page None after close", browser.page is None)


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

print("\n=== Context manager ===")
try:
    with PlaywrightBrowser(headless=True, timeout=3000) as b:
        check("context manager started", b._started)
        b.navigate("data:text/html,<html><body>Context test</body></html>")
        text = b.get_page_text()
        check("context manager page text", "Context test" in text)
    check("context manager closed", not b._started)
except Exception as e:
    print(f"  SKIP: Context manager test failed: {e}")
    check("context manager", False)


# ---------------------------------------------------------------------------
# CDP connection (skip if no Chrome running with debugging)
# ---------------------------------------------------------------------------

print("\n=== CDP connection (best effort) ===")
cdp_browser = PlaywrightBrowser(headless=True)
cdp_ok = cdp_browser.connect_cdp("http://localhost:9222")
if cdp_ok:
    check("CDP connected", True)
    cdp_browser.close()
else:
    print("  SKIP: No Chrome debugging instance found (expected)")
    check("CDP skip is ok", True)


# ---------------------------------------------------------------------------
# WebVisionEngine Playwright integration
# ---------------------------------------------------------------------------

print("\n=== WebVisionEngine Playwright integration ===")
from vision.web_vision_engine import WebVisionEngine

engine = WebVisionEngine(use_playwright_fallback=True)
check("engine has playwright flag", engine._use_playwright)
check("engine playwright not loaded yet", engine._playwright_browser is None)

engine_no_pw = WebVisionEngine(use_playwright_fallback=False)
check("engine without playwright", not engine_no_pw._use_playwright)
pw = engine_no_pw._get_playwright()
check("engine no-pw returns None", pw is None)


# ===========================================================================
print(f"\n{'='*50}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"FAILURES: {failed}")
    sys.exit(1)
