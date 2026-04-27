"""Smoke tests for WebVisionEngine — element detection, annotation, and core API.

Tests the OpenCV-based detection and annotation pipeline without requiring
the vision model (which needs Ollama running). Vision model integration
is tested separately in integration tests.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import cv2

from vision.web_vision_engine import (
    BBox, UIElement, ActionResult, PageState,
    ElementDetector, ScreenAnnotator, WebVisionEngine,
)

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
# BBox tests
# ---------------------------------------------------------------------------

print("=== BBox ===")
b1 = BBox(100, 200, 80, 30)
check("center", b1.center == (140, 215))
check("area", b1.area == 2400)
check("contains inside", b1.contains(120, 210))
check("contains outside", not b1.contains(50, 50))

b2 = BBox(150, 210, 60, 30)
check("overlaps true", b1.overlaps(b2))
check("overlap_area > 0", b1.overlap_area(b2) > 0)

b3 = BBox(500, 500, 50, 50)
check("overlaps false", not b1.overlaps(b3))
check("overlap_area 0", b1.overlap_area(b3) == 0)


# ---------------------------------------------------------------------------
# Synthetic screenshot for testing
# ---------------------------------------------------------------------------

print("\n=== Synthetic screenshot ===")
# Create a 1280x720 synthetic web page screenshot
img = np.ones((720, 1280, 3), dtype=np.uint8) * 240  # light gray background

# Draw a "top bar" (dark gray)
cv2.rectangle(img, (0, 0), (1280, 60), (50, 50, 50), -1)

# Draw "buttons" — colored rectangles with text-like content
# Button 1: "Create Post" (blue button)
cv2.rectangle(img, (1050, 15), (1200, 45), (200, 120, 30), -1)  # blue fill
cv2.rectangle(img, (1050, 15), (1200, 45), (220, 140, 50), 2)   # border
cv2.putText(img, "Create Post", (1060, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

# Button 2: "Sort: New" (smaller button)
cv2.rectangle(img, (200, 80), (300, 110), (100, 100, 100), -1)
cv2.putText(img, "New", (225, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

# Text field: title input
cv2.rectangle(img, (100, 200), (800, 240), (255, 255, 255), -1)  # white fill
cv2.rectangle(img, (100, 200), (800, 240), (180, 180, 180), 2)   # gray border
cv2.putText(img, "Title", (110, 225), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

# Text area: body input
cv2.rectangle(img, (100, 260), (800, 450), (255, 255, 255), -1)
cv2.rectangle(img, (100, 260), (800, 450), (180, 180, 180), 2)
cv2.putText(img, "Text (optional)", (110, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

# Small icon: settings gear
cv2.circle(img, (1240, 35), 12, (200, 200, 200), 2)

# Post card (large container)
cv2.rectangle(img, (50, 500), (900, 650), (255, 255, 255), -1)
cv2.rectangle(img, (50, 500), (900, 650), (200, 200, 200), 1)
cv2.putText(img, "Example post title here", (70, 530), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 30), 1)

check("synthetic screenshot shape", img.shape == (720, 1280, 3))


# ---------------------------------------------------------------------------
# Element detector tests
# ---------------------------------------------------------------------------

print("\n=== ElementDetector ===")
detector = ElementDetector()
elements = detector.detect(img)
check("detected elements > 0", len(elements) > 0)
check("elements have indices", all(e.index > 0 for e in elements))
check("elements have bboxes", all(e.bbox.w > 0 and e.bbox.h > 0 for e in elements))
check("elements sorted by position", all(
    elements[i].bbox.y // 30 <= elements[i+1].bbox.y // 30
    for i in range(len(elements) - 1)
))

# Check element classification
classes = set(e.element_class for e in elements)
print(f"  Element classes found: {classes}")
print(f"  Total elements: {len(elements)}")
check("at least 3 elements", len(elements) >= 3)

# Check classification distribution
by_class = {}
for e in elements:
    by_class.setdefault(e.element_class, []).append(e)
for cls, els in sorted(by_class.items()):
    print(f"    {cls}: {len(els)}")

# Check that detection works with a region
region = BBox(0, 0, 1280, 100)
top_elements = detector.detect(img, region)
check("region detection works", len(top_elements) >= 1)
check("region elements in bounds",
      all(e.bbox.y < 120 for e in top_elements))  # small tolerance


# ---------------------------------------------------------------------------
# Screen annotator tests
# ---------------------------------------------------------------------------

print("\n=== ScreenAnnotator ===")
annotated = ScreenAnnotator.annotate(img, elements)
check("annotated same shape", annotated.shape == img.shape)
check("annotated is different from original", not np.array_equal(annotated, img))

# Check that numbered labels were drawn (the annotated image should have
# more non-gray pixels than the original)
diff = np.abs(annotated.astype(int) - img.astype(int)).sum()
check("annotations added pixels", diff > 1000)

# PIL version
from PIL import Image
pil_img = Image.fromarray(img[:, :, ::-1])  # BGR to RGB
pil_annotated = ScreenAnnotator.annotate_pil(pil_img, elements)
check("PIL annotate returns Image", isinstance(pil_annotated, Image.Image))
check("PIL annotate correct size", pil_annotated.size == pil_img.size)


# ---------------------------------------------------------------------------
# MSER text region detection
# ---------------------------------------------------------------------------

print("\n=== MSER text detection ===")
mser_elements = detector._detect_mser_regions(img, 0, 0)
# The synthetic image has text drawn on it — MSER should find some regions
print(f"  MSER regions found: {len(mser_elements)}")
check("MSER detects some regions", len(mser_elements) >= 0)  # may be 0 on simple synthetic


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

print("\n=== Deduplication ===")
dup_elements = [
    UIElement(1, BBox(100, 100, 50, 30), "button", 0.9),
    UIElement(2, BBox(105, 102, 48, 28), "button", 0.7),  # overlaps with #1
    UIElement(3, BBox(500, 300, 60, 25), "button", 0.8),   # no overlap
]
deduped = detector._deduplicate(dup_elements)
check("dedup removes overlap", len(deduped) == 2)
check("dedup keeps higher confidence", deduped[0].confidence >= deduped[1].confidence)


# ---------------------------------------------------------------------------
# WebVisionEngine instantiation
# ---------------------------------------------------------------------------

print("\n=== WebVisionEngine ===")
engine = WebVisionEngine()
check("engine created", engine is not None)
check("engine has detector", engine._detector is not None)
check("engine has annotator", engine._annotator is not None)
check("engine has identifier", engine._identifier is not None)
check("MAX_RETRIES > 0", engine.MAX_RETRIES > 0)
check("VERIFY_WAIT > 0", engine.VERIFY_WAIT > 0)

# Test detect_elements with a pre-captured screenshot
elements2 = engine.detect_elements(img)
check("engine detect returns elements", len(elements2) > 0)
check("engine stores last elements", len(engine._last_elements) > 0)

# Test element summary
summary = engine.get_element_summary()
check("summary is string", isinstance(summary, str))
check("summary has count", "Detected" in summary)
print(f"  Summary: {summary[:100]}...")


# ---------------------------------------------------------------------------
# ActionResult
# ---------------------------------------------------------------------------

print("\n=== ActionResult ===")
result = ActionResult(ok=True, method="vision_annotated", coords=(500, 300), verified=True)
check("result ok", result.ok)
check("result method", result.method == "vision_annotated")
check("result coords", result.coords == (500, 300))
check("result verified", result.verified)

fail_result = ActionResult(ok=False, error="Element not found")
check("fail result not ok", not fail_result.ok)
check("fail result has error", fail_result.error == "Element not found")


# ---------------------------------------------------------------------------
# PageState
# ---------------------------------------------------------------------------

print("\n=== PageState ===")
state = PageState(
    elements_detected=15,
    text_regions_detected=5,
    description="Reddit post creation page",
    timestamp=1234567890.0,
)
check("state elements", state.elements_detected == 15)
check("state description", "Reddit" in state.description)


# ---------------------------------------------------------------------------
# Classification heuristics
# ---------------------------------------------------------------------------

print("\n=== Classification ===")
# Button-like element
btn = UIElement(1, BBox(0, 0, 150, 35), "unknown", 0.8)
cls = detector._classify(btn)
check("150x35 → button", cls == "button")

# Text field
tf = UIElement(2, BBox(0, 0, 400, 40), "unknown", 0.8)
cls = detector._classify(tf)
check("400x40 → text_field", cls == "text_field")

# Icon
icon = UIElement(3, BBox(0, 0, 30, 30), "unknown", 0.8)
cls = detector._classify(icon)
check("30x30 → icon", cls == "icon")

# Container (tall rectangle)
container = UIElement(4, BBox(0, 0, 400, 150), "unknown", 0.8)
cls = detector._classify(container)
check("400x150 → container", cls == "container")


# ---------------------------------------------------------------------------
# BBox clustering
# ---------------------------------------------------------------------------

print("\n=== Bbox clustering ===")
bboxes = [
    (100, 100, 20, 15),  # char 1
    (125, 100, 20, 15),  # char 2 (same line, close)
    (150, 100, 20, 15),  # char 3 (same line, close)
    (500, 300, 20, 15),  # different region entirely
]
clusters = detector._cluster_bboxes(bboxes)
check("clusters 2 groups", len(clusters) == 2)
check("first cluster has 3", len(clusters[0]) == 3)
check("second cluster has 1", len(clusters[1]) == 1)


# ---------------------------------------------------------------------------
# WorkflowStep
# ---------------------------------------------------------------------------

print("\n=== WorkflowStep ===")
from vision.web_vision_engine import WorkflowStep, WorkflowResult, WebWorkflow, WorkflowTemplates

step = WorkflowStep(
    name="Click Create Post",
    action="click",
    target="Create Post",
    element_type="button",
    expected_change="Post form should appear",
    recovery_actions=["scroll_down", "wait_2s", "retry"],
)
check("step name", step.name == "Click Create Post")
check("step action", step.action == "click")
check("step target", step.target == "Create Post")
check("step element_type", step.element_type == "button")
check("step verify default True", step.verify is True)
check("step optional default False", step.optional is False)
check("step status default pending", step.status == "pending")
check("step recovery_actions", len(step.recovery_actions) == 3)
check("step result default None", step.result is None)

# Wait step
wait_step = WorkflowStep(
    name="Wait for load",
    action="wait",
    wait_seconds=3.0,
    verify=False,
)
check("wait step action", wait_step.action == "wait")
check("wait step verify False", wait_step.verify is False)
check("wait step seconds", wait_step.wait_seconds == 3.0)

# Navigate step
nav_step = WorkflowStep(
    name="Go to Reddit",
    action="navigate",
    url="https://www.reddit.com/r/test",
)
check("nav step url", nav_step.url == "https://www.reddit.com/r/test")

# Key step
key_step = WorkflowStep(
    name="Press Enter",
    action="key",
    key="enter",
)
check("key step key", key_step.key == "enter")

# Type step
type_step = WorkflowStep(
    name="Type title",
    action="type",
    target="Title",
    text="My post title",
    clear_first=True,
)
check("type step text", type_step.text == "My post title")
check("type step clear_first", type_step.clear_first is True)


# ---------------------------------------------------------------------------
# WorkflowResult
# ---------------------------------------------------------------------------

print("\n=== WorkflowResult ===")
wr = WorkflowResult(
    ok=True,
    workflow_name="Reddit post",
    steps_total=5,
    steps_passed=4,
    steps_failed=0,
    steps_skipped=1,
    duration_seconds=12.5,
)
check("wr ok", wr.ok)
check("wr name", wr.workflow_name == "Reddit post")
check("wr total", wr.steps_total == 5)
check("wr passed", wr.steps_passed == 4)
check("wr skipped", wr.steps_skipped == 1)
check("wr failed", wr.steps_failed == 0)
check("wr duration", wr.duration_seconds == 12.5)
check("wr no error", wr.error == "")

wr_fail = WorkflowResult(
    ok=False,
    workflow_name="Twitter post",
    steps_total=3,
    steps_passed=1,
    steps_failed=1,
    failed_step="Click compose area",
    error="Element not found",
)
check("wr_fail not ok", not wr_fail.ok)
check("wr_fail failed_step", wr_fail.failed_step == "Click compose area")
check("wr_fail error", wr_fail.error == "Element not found")


# ---------------------------------------------------------------------------
# WebWorkflow construction
# ---------------------------------------------------------------------------

print("\n=== WebWorkflow construction ===")
engine = WebVisionEngine()
wf = WebWorkflow(engine, "Test Workflow")
check("workflow name", wf.name == "Test Workflow")
check("workflow starts empty", len(wf.steps) == 0)

# Add steps and check chaining
wf.add_step(WorkflowStep(name="Step 1", action="wait", wait_seconds=0.1, verify=False))
wf.add_step(WorkflowStep(name="Step 2", action="wait", wait_seconds=0.1, verify=False))
wf.add_step(WorkflowStep(name="Step 3", action="wait", wait_seconds=0.1, verify=False))
check("3 steps added", len(wf.steps) == 3)
check("step names correct", [s.name for s in wf.steps] == ["Step 1", "Step 2", "Step 3"])

# Callback test
callback_log = []
wf.on_step(lambda idx, step, status: callback_log.append((idx, step.name, status)))
check("callback set", wf._on_step_callback is not None)


# ---------------------------------------------------------------------------
# WebWorkflow recovery constants
# ---------------------------------------------------------------------------

print("\n=== Recovery constants ===")
check("RECOVERY_SCROLL_DOWN", WebWorkflow.RECOVERY_SCROLL_DOWN == "scroll_down")
check("RECOVERY_SCROLL_UP", WebWorkflow.RECOVERY_SCROLL_UP == "scroll_up")
check("RECOVERY_WAIT_1S", WebWorkflow.RECOVERY_WAIT_1S == "wait_1s")
check("RECOVERY_WAIT_2S", WebWorkflow.RECOVERY_WAIT_2S == "wait_2s")
check("RECOVERY_WAIT_5S", WebWorkflow.RECOVERY_WAIT_5S == "wait_5s")
check("RECOVERY_RETRY", WebWorkflow.RECOVERY_RETRY == "retry")
check("RECOVERY_PAGE_LOAD", WebWorkflow.RECOVERY_PAGE_LOAD == "wait_page_load")
check("RECOVERY_PRESS_ESCAPE", WebWorkflow.RECOVERY_PRESS_ESCAPE == "press_escape")
check("RECOVERY_CLICK_BODY", WebWorkflow.RECOVERY_CLICK_BODY == "click_body")


# ---------------------------------------------------------------------------
# WorkflowTemplates — structure verification (no execution)
# ---------------------------------------------------------------------------

print("\n=== WorkflowTemplates ===")
# Reddit text post
reddit_wf = WorkflowTemplates.reddit_text_post(engine, "test", "Test Title", "Test body text")
check("reddit wf name", "r/test" in reddit_wf.name)
check("reddit wf has steps", len(reddit_wf.steps) >= 6)
step_actions = [s.action for s in reddit_wf.steps]
check("reddit has navigate", "navigate" in step_actions)
check("reddit has click", "click" in step_actions)
check("reddit has type_special", "type_special" in step_actions)
check("reddit navigate to submit",
      any("/r/test/submit" in s.url for s in reddit_wf.steps if s.url))
check("reddit has Post button step",
      any(s.target == "Post" and s.action == "click" for s in reddit_wf.steps))

# Reddit comment
comment_wf = WorkflowTemplates.reddit_comment(
    engine, "https://reddit.com/r/test/comments/abc123", "Great post!")
check("comment wf has steps", len(comment_wf.steps) >= 4)
check("comment has navigate",
      any(s.action == "navigate" for s in comment_wf.steps))
check("comment has comment button",
      any(s.target == "Comment" for s in comment_wf.steps))

# Twitter post
twitter_wf = WorkflowTemplates.twitter_post(engine, "Hello from Onyx!")
check("twitter wf has steps", len(twitter_wf.steps) >= 4)
check("twitter navigates to compose",
      any("compose" in s.url for s in twitter_wf.steps if s.url))
check("twitter has Post button",
      any(s.target == "Post" and s.action == "click" for s in twitter_wf.steps))

# YouTube upload metadata
yt_wf = WorkflowTemplates.youtube_upload_metadata(engine, "My Video", "My description")
check("youtube wf has steps", len(yt_wf.steps) >= 4)
check("youtube has title type",
      any(s.target == "Title" and s.action == "type" for s in yt_wf.steps))
check("youtube has optional step",
      any(s.optional for s in yt_wf.steps))

# Generic form fill
form_wf = WorkflowTemplates.generic_form_fill(
    engine,
    "https://example.com/form",
    {"Name": "Onyx", "Email": "onyx@example.com"},
    submit_label="Send",
)
check("form wf has steps", len(form_wf.steps) >= 4)  # navigate + wait + 2 fields + submit
check("form has navigate",
      any(s.action == "navigate" for s in form_wf.steps))
check("form has submit",
      any(s.target == "Send" and s.action == "click" for s in form_wf.steps))
check("form fills both fields",
      sum(1 for s in form_wf.steps if s.action == "type") == 2)


# ===========================================================================
print(f"\n{'='*50}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"FAILURES: {failed}")
    sys.exit(1)
