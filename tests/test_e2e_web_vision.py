"""End-to-end integration test for the social platform posting pipeline.

Tests the full chain:
    action_dispatch (3-tier) → WebVisionEngine → Playwright fallback

Uses Playwright to serve a synthetic Reddit-like page, then verifies that:
1. The Playwright fallback can find/click/type elements by label
2. The workflow system executes multi-step chains correctly
3. The action_dispatch integration correctly routes vision-only modules
4. The RedditModule.post_text() and TwitterModule.post_tweet() methods work structurally

Does NOT require Ollama/vision model (tests the pipeline without LLM).
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
# Synthetic Reddit-like page HTML
# ---------------------------------------------------------------------------

REDDIT_SUBMIT_HTML = """
<html>
<head><title>Submit to r/test - Reddit</title></head>
<body style="background:#1a1a1b; color:#d7dadc; font-family:sans-serif; padding:20px">
    <div style="max-width:800px; margin:0 auto">
        <h2 style="color:#d7dadc">Create a post</h2>
        <div style="background:#272729; border-radius:4px; padding:16px; margin-top:12px">
            <div style="display:flex; gap:8px; margin-bottom:12px">
                <button style="padding:8px 16px; background:#272729; color:#818384; border:1px solid #343536; border-radius:20px; cursor:pointer">Post</button>
                <button style="padding:8px 16px; background:#272729; color:#818384; border:1px solid #343536; border-radius:20px; cursor:pointer">Images & Video</button>
                <button style="padding:8px 16px; background:#272729; color:#818384; border:1px solid #343536; border-radius:20px; cursor:pointer">Link</button>
            </div>
            <input type="text" placeholder="Title" id="post-title"
                   style="width:100%; padding:10px; background:#1a1a1b; border:1px solid #343536; color:#d7dadc; border-radius:4px; font-size:14px; box-sizing:border-box; margin-bottom:12px">
            <textarea placeholder="Text (optional)" id="post-body"
                      style="width:100%; height:200px; padding:10px; background:#1a1a1b; border:1px solid #343536; color:#d7dadc; border-radius:4px; font-size:14px; box-sizing:border-box; resize:vertical"></textarea>
            <div style="display:flex; justify-content:flex-end; margin-top:12px">
                <button id="submit-btn" style="padding:8px 24px; background:#0079d3; color:white; border:none; border-radius:20px; font-weight:bold; cursor:pointer">Post</button>
            </div>
        </div>
    </div>
    <div id="result" style="display:none; margin-top:20px; padding:16px; background:#272729; border-radius:4px">
        <h3>Post submitted!</h3>
        <p id="result-title"></p>
        <p id="result-body"></p>
    </div>
    <script>
        document.getElementById('submit-btn').addEventListener('click', function() {
            var title = document.getElementById('post-title').value;
            var body = document.getElementById('post-body').value;
            document.getElementById('result-title').textContent = 'Title: ' + title;
            document.getElementById('result-body').textContent = 'Body: ' + body;
            document.getElementById('result').style.display = 'block';
        });
    </script>
</body>
</html>
"""

TWITTER_COMPOSE_HTML = """
<html>
<head><title>Compose new post / X</title></head>
<body style="background:#000; color:#e7e9ea; font-family:sans-serif; padding:20px">
    <div style="max-width:600px; margin:0 auto; background:#16181c; border-radius:16px; padding:16px">
        <div style="display:flex; gap:12px">
            <div style="width:40px; height:40px; background:#1d9bf0; border-radius:50%"></div>
            <div style="flex:1">
                <div contenteditable="true" aria-label="What is happening" data-placeholder="What is happening?!"
                     style="min-height:100px; color:#e7e9ea; font-size:20px; outline:none; padding:8px"
                     id="tweet-input">
                </div>
                <div style="display:flex; justify-content:flex-end; margin-top:12px; padding-top:12px; border-top:1px solid #2f3336">
                    <button id="post-btn" style="padding:8px 20px; background:#1d9bf0; color:white; border:none; border-radius:20px; font-weight:bold; cursor:pointer">Post</button>
                </div>
            </div>
        </div>
    </div>
    <div id="result" style="display:none; margin-top:20px; padding:16px; background:#16181c; border-radius:16px">
        <h3>Tweet posted!</h3>
        <p id="result-text"></p>
    </div>
    <script>
        document.getElementById('post-btn').addEventListener('click', function() {
            var text = document.getElementById('tweet-input').textContent || document.getElementById('tweet-input').innerText;
            document.getElementById('result-text').textContent = text;
            document.getElementById('result').style.display = 'block';
        });
    </script>
</body>
</html>
"""


# Skip during pytest collection — run directly: python tests/test_e2e_web_vision.py
if "pytest" in sys.modules:
    import pytest
    pytest.skip("E2E script — run directly", allow_module_level=True)

# ---------------------------------------------------------------------------
# Test 1: Playwright fallback on synthetic Reddit page
# ---------------------------------------------------------------------------

print("=== E2E: Playwright on Reddit-like page ===")

from vision.playwright_fallback import PlaywrightBrowser

try:
    with PlaywrightBrowser(headless=True, timeout=5000) as browser:
        browser.page.set_content(REDDIT_SUBMIT_HTML)

        # Find and verify elements exist
        title_field = browser.find_element("Title", "text_field")
        check("reddit: find title field", title_field is not None)

        body_field = browser.find_element("Text (optional)", "text_field")
        check("reddit: find body field", body_field is not None)

        post_btn = browser.find_element("Post", "button")
        check("reddit: find Post button", post_btn is not None)

        # Type into title
        type_title = browser.type_into("Title", "Test post from Onyx")
        check("reddit: type title ok", type_title.ok)
        title_val = browser.page.locator("#post-title").input_value()
        check("reddit: title value correct", title_val == "Test post from Onyx")

        # Type into body
        type_body = browser.type_into("Text (optional)", "This is an automated test post.")
        check("reddit: type body ok", type_body.ok)
        body_val = browser.page.locator("#post-body").input_value()
        check("reddit: body value correct", body_val == "This is an automated test post.")

        # Click submit (use locator directly since there are multiple "Post" buttons)
        browser.page.locator("#submit-btn").click()
        check("reddit: click submit ok", True)

        # Verify the result appeared
        browser.page.wait_for_selector("#result", state="visible", timeout=2000)
        result_title = browser.page.locator("#result-title").text_content()
        result_body = browser.page.locator("#result-body").text_content()
        check("reddit: result title", "Test post from Onyx" in result_title)
        check("reddit: result body", "automated test post" in result_body)

        print("  Reddit submit flow: COMPLETE")

except Exception as e:
    print(f"  ERROR: Reddit E2E failed: {e}")
    check("reddit: E2E", False)


# ---------------------------------------------------------------------------
# Test 2: Playwright fallback on synthetic Twitter page
# ---------------------------------------------------------------------------

print("\n=== E2E: Playwright on Twitter-like page ===")

try:
    with PlaywrightBrowser(headless=True, timeout=5000) as browser:
        browser.page.set_content(TWITTER_COMPOSE_HTML)

        # Find compose area (contenteditable div with aria-label)
        compose = browser.find_element("What is happening", "text_field")
        check("twitter: find compose area", compose is not None)

        # Find Post button
        post_btn = browser.find_element("Post", "button")
        check("twitter: find Post button", post_btn is not None)

        # Type tweet text into contenteditable
        browser.page.locator("#tweet-input").click()
        browser.page.locator("#tweet-input").type("Hello from Onyx! Testing automation.", delay=20)

        tweet_text = browser.page.locator("#tweet-input").text_content()
        check("twitter: tweet text typed", "Hello from Onyx" in tweet_text)

        # Click Post
        click_post = browser.click_by_text("Post", "button")
        check("twitter: click Post ok", click_post.ok)

        # Verify result
        browser.page.wait_for_selector("#result", state="visible", timeout=2000)
        result_text = browser.page.locator("#result-text").text_content()
        check("twitter: result has tweet", "Hello from Onyx" in result_text)

        print("  Twitter compose flow: COMPLETE")

except Exception as e:
    print(f"  ERROR: Twitter E2E failed: {e}")
    check("twitter: E2E", False)


# ---------------------------------------------------------------------------
# Test 3: WebWorkflow with Playwright (wait-only steps)
# ---------------------------------------------------------------------------

print("\n=== E2E: WebWorkflow execution (wait steps) ===")

from vision.web_vision_engine import WebVisionEngine, WebWorkflow, WorkflowStep, WorkflowResult

engine = WebVisionEngine(use_playwright_fallback=False)  # no PW for this test

# Build a workflow of only wait/key steps (no vision model needed)
wf = WebWorkflow(engine, "Test wait workflow")
wf.add_step(WorkflowStep(name="Wait 1", action="wait", wait_seconds=0.1, verify=False))
wf.add_step(WorkflowStep(name="Wait 2", action="wait", wait_seconds=0.1, verify=False))
wf.add_step(WorkflowStep(name="Wait 3", action="wait", wait_seconds=0.1, verify=False))

# Track via callback
step_log = []
wf.on_step(lambda idx, step, status: step_log.append((idx, step.name, status)))

result = wf.execute()
check("workflow ok", result.ok)
check("workflow name", result.workflow_name == "Test wait workflow")
check("workflow all passed", result.steps_passed == 3)
check("workflow none failed", result.steps_failed == 0)
check("workflow duration > 0", result.duration_seconds > 0)
check("workflow step_results", len(result.step_results) == 3)
check("callback fired", len(step_log) >= 6)  # running + passed for each
check("callback has running", any(s[2] == "running" for s in step_log))
check("callback has passed", any(s[2] == "passed" for s in step_log))

# Verify step results structure
for sr in result.step_results:
    check(f"step '{sr['name']}' status=passed", sr["status"] == "passed")


# ---------------------------------------------------------------------------
# Test 4: WebWorkflow with optional step failure
# ---------------------------------------------------------------------------

print("\n=== E2E: WebWorkflow with optional failure ===")

wf2 = WebWorkflow(engine, "Optional failure test")
wf2.add_step(WorkflowStep(name="Good step", action="wait", wait_seconds=0.05, verify=False))
wf2.add_step(WorkflowStep(
    name="Optional bad step",
    action="wait_for_element",  # will fail — no screen to search
    target="ZZZZZ_IMPOSSIBLE_ELEMENT_99999",
    wait_seconds=0.3,
    optional=True,  # should be skipped, not abort
    verify=False,
    recovery_actions=["retry"],  # minimal recovery to keep test fast
))
wf2.add_step(WorkflowStep(name="After optional", action="wait", wait_seconds=0.05, verify=False))

result2 = wf2.execute()
check("optional wf ok", result2.ok)
check("optional wf passed 2", result2.steps_passed == 2)
check("optional wf skipped 1", result2.steps_skipped == 1)
check("optional wf failed 0", result2.steps_failed == 0)


# ---------------------------------------------------------------------------
# Test 5: action_dispatch integration (structural)
# ---------------------------------------------------------------------------

print("\n=== E2E: action_dispatch integration ===")

from agent.action_dispatch import (
    _get_web_vision_engine,
    _is_vision_only,
    execute_action,
    get_registered_actions,
)

# Verify helpers
check("_is_vision_only(None) = False", not _is_vision_only(None))

class MockVisionModule:
    vision_only = True

class MockNormalModule:
    vision_only = False

check("_is_vision_only(vision) = True", _is_vision_only(MockVisionModule()))
check("_is_vision_only(normal) = False", not _is_vision_only(MockNormalModule()))

# WebVisionEngine loads lazily
engine_ref = _get_web_vision_engine()
check("lazy engine loaded", engine_ref is not None)

# Registered actions include click and type
actions = get_registered_actions()
check("click registered", "click" in actions)
check("type registered", "type" in actions)
check("key_press registered", "key_press" in actions)
check("scroll registered", "scroll" in actions)

# Execute a non-vision action (no app_module) — should work normally
done_result = execute_action({"action": "done", "params": {"reason": "test complete"}})
check("done action works", "complete" in done_result.lower())

# Execute wait action
wait_result = execute_action({"action": "wait", "params": {"seconds": 0.1}})
check("wait action works", "Waited" in wait_result or "wait" in wait_result.lower())


# ---------------------------------------------------------------------------
# Test 6: RedditModule structural verification
# ---------------------------------------------------------------------------

print("\n=== E2E: RedditModule structure ===")

from apps.modules.reddit import RedditModule

reddit = RedditModule()
check("reddit vision_only", reddit.vision_only)
check("reddit auto_confirm", reddit.auto_confirm)
check("reddit has post_text", callable(getattr(reddit, "post_text", None)))
check("reddit has post_comment", callable(getattr(reddit, "post_comment", None)))
check("reddit has save_debug_screenshot", callable(getattr(reddit, "save_debug_screenshot", None)))
check("reddit app_name", reddit.app_name == "reddit")
check("reddit window_title_hint", reddit.window_title_hint == "Reddit")


# ---------------------------------------------------------------------------
# Test 7: TwitterModule structural verification
# ---------------------------------------------------------------------------

print("\n=== E2E: TwitterModule structure ===")

from apps.modules.twitter import TwitterModule

twitter = TwitterModule()
check("twitter vision_only", twitter.vision_only)
check("twitter auto_confirm", twitter.auto_confirm)
check("twitter has post_tweet", callable(getattr(twitter, "post_tweet", None)))
check("twitter has save_debug_screenshot", callable(getattr(twitter, "save_debug_screenshot", None)))
check("twitter app_name", twitter.app_name == "twitter")


# ---------------------------------------------------------------------------
# Test 8: Full Playwright pipeline — Reddit submit with PlaywrightBrowser
# ---------------------------------------------------------------------------

print("\n=== E2E: Full Reddit submit via Playwright pipeline ===")

try:
    with PlaywrightBrowser(headless=True, timeout=5000) as pw:
        pw.page.set_content(REDDIT_SUBMIT_HTML)

        # Simulate the full workflow that RedditModule.post_text() would trigger
        # Step 1: Find and fill title
        title_el = pw.find_element("Title", "text_field")
        check("pipeline: found title", title_el is not None)

        r = pw.type_into("Title", "Onyx AI is now posting on Reddit")
        check("pipeline: typed title", r.ok)

        # Step 2: Find and fill body
        r = pw.type_into("Text (optional)", "This post was created entirely by Onyx's WebVisionEngine + Playwright fallback pipeline.")
        check("pipeline: typed body", r.ok)

        # Step 3: Click submit (by ID to avoid ambiguity with tab buttons)
        pw.page.locator("#submit-btn").click()
        check("pipeline: clicked Post", True)

        # Step 4: Verify post appeared
        pw.page.wait_for_selector("#result", state="visible", timeout=2000)
        page_text = pw.get_page_text()
        check("pipeline: result visible", "Post submitted" in page_text)
        check("pipeline: title in result", "Onyx AI" in page_text)
        check("pipeline: body in result", "WebVisionEngine" in page_text)

        print("  Full Reddit pipeline: COMPLETE")

except Exception as e:
    print(f"  ERROR: Pipeline test failed: {e}")
    check("pipeline: complete", False)


# ===========================================================================
print(f"\n{'='*50}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"FAILURES: {failed}")
    sys.exit(1)
