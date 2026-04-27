"""WebVisionEngine — reliable web UI interaction via vision + OpenCV.

Replaces the fragile "LLM guesses pixel coordinates" approach with a
structured detection → identification → action → verification pipeline.

Architecture:
    1. DETECT  — OpenCV finds all rectangular UI elements (buttons, fields, links)
    2. ANNOTATE — Draw numbered labels on each detected element
    3. IDENTIFY — Vision model matches target label to a numbered element
    4. ACT     — Click/type at the precise center of the identified element
    5. VERIFY  — Screenshot comparison confirms the action succeeded
    6. RETRY   — If verification fails, re-detect and try again

This replaces coordinate guessing with precise bounding-box targeting.
The LLM's job becomes identification (easy) instead of estimation (hard).

Usage:
    engine = WebVisionEngine()
    result = engine.find_and_click("Create Post", element_type="button")
    result = engine.find_and_type("Title", "My post title")
    state = engine.get_page_state()
"""

import io
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import mss
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage.metrics import structural_similarity as ssim

_log = logging.getLogger("vision.web_engine")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class BBox:
    """A bounding box on screen."""
    x: int      # left
    y: int      # top
    w: int      # width
    h: int      # height

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)

    @property
    def area(self) -> int:
        return self.w * self.h

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h

    def overlaps(self, other: "BBox") -> bool:
        return not (self.x + self.w <= other.x or other.x + other.w <= self.x or
                    self.y + self.h <= other.y or other.y + other.h <= self.y)

    def overlap_area(self, other: "BBox") -> int:
        dx = max(0, min(self.x + self.w, other.x + other.w) - max(self.x, other.x))
        dy = max(0, min(self.y + self.h, other.y + other.h) - max(self.y, other.y))
        return dx * dy


@dataclass
class UIElement:
    """A detected UI element on screen."""
    index: int              # numbered label for identification
    bbox: BBox
    element_class: str      # "button", "text_field", "link", "icon", "tab", "unknown"
    confidence: float       # 0-1 detection confidence
    # Set by vision model after identification
    label: str = ""         # e.g. "Create Post", "Title field"
    matched: bool = False   # True if this was identified as the target


@dataclass
class ActionResult:
    """Result of a find-and-act operation."""
    ok: bool
    method: str = ""        # "vision_ocr", "vision_annotated", "region_match", "fallback"
    element: Optional[UIElement] = None
    coords: Tuple[int, int] = (0, 0)
    verified: bool = False  # True if post-action verification confirmed success
    retries: int = 0
    error: str = ""
    details: str = ""


@dataclass
class PageState:
    """Summary of what's currently on screen."""
    screenshot_path: str = ""
    elements_detected: int = 0
    text_regions_detected: int = 0
    description: str = ""   # LLM-generated description of the page
    timestamp: float = 0.0


# ---------------------------------------------------------------------------
# OpenCV-based UI element detection
# ---------------------------------------------------------------------------

class ElementDetector:
    """Detects UI elements (buttons, text fields, links) using OpenCV.

    Uses multiple strategies:
    - Contour detection for rectangular elements
    - MSER for text regions
    - Edge detection for bordered elements
    - Color segmentation for colored buttons
    """

    # Size constraints for UI elements (in pixels)
    MIN_ELEMENT_W = 30
    MIN_ELEMENT_H = 15
    MAX_ELEMENT_W = 800
    MAX_ELEMENT_H = 200
    MIN_ELEMENT_AREA = 600
    MAX_ELEMENT_AREA = 120_000

    # Element classification heuristics
    BUTTON_ASPECT_RANGE = (1.5, 8.0)   # width/height ratio for buttons
    FIELD_ASPECT_RANGE = (3.0, 30.0)   # text fields are wider
    FIELD_MIN_W = 150                   # text fields are at least this wide
    ICON_MAX_SIZE = 50                  # icons are small

    def detect(self, screenshot: np.ndarray,
               region: Optional[BBox] = None) -> List[UIElement]:
        """Detect all UI elements in a screenshot.

        Args:
            screenshot: BGR numpy array (OpenCV format).
            region: Optional sub-region to search within.

        Returns:
            List of detected UIElements, sorted top-to-bottom, left-to-right.
        """
        if region:
            crop = screenshot[region.y:region.y + region.h,
                              region.x:region.x + region.w]
            offset_x, offset_y = region.x, region.y
        else:
            crop = screenshot
            offset_x, offset_y = 0, 0

        # Run multiple detection strategies and merge results
        elements = []
        elements.extend(self._detect_contours(crop, offset_x, offset_y))
        elements.extend(self._detect_mser_regions(crop, offset_x, offset_y))

        # Deduplicate overlapping detections
        elements = self._deduplicate(elements)

        # Classify each element
        for el in elements:
            el.element_class = self._classify(el)

        # Sort top-to-bottom, left-to-right and assign indices
        elements.sort(key=lambda e: (e.bbox.y // 30, e.bbox.x))
        for i, el in enumerate(elements):
            el.index = i + 1

        return elements

    def _detect_contours(self, img: np.ndarray,
                         ox: int, oy: int) -> List[UIElement]:
        """Find rectangular UI elements via contour detection."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Adaptive threshold to handle varying backgrounds
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 15, 4,
        )

        # Morphological close to connect nearby edges into solid rectangles
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(
            closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )

        elements = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if not self._valid_size(w, h):
                continue

            # Check rectangularity — UI elements are mostly rectangular
            area = cv2.contourArea(cnt)
            rect_area = w * h
            if rect_area == 0:
                continue
            rectangularity = area / rect_area
            if rectangularity < 0.4:
                continue

            confidence = min(1.0, rectangularity * 0.8 + 0.2)
            elements.append(UIElement(
                index=0,
                bbox=BBox(x + ox, y + oy, w, h),
                element_class="unknown",
                confidence=confidence,
            ))

        return elements

    def _detect_mser_regions(self, img: np.ndarray,
                             ox: int, oy: int) -> List[UIElement]:
        """Find text-like regions via MSER (Maximally Stable Extremal Regions).

        MSER is good at finding text regions without actual OCR.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mser = cv2.MSER_create()
        mser.setMinArea(200)
        mser.setMaxArea(20000)

        regions, _ = mser.detectRegions(gray)

        # Group nearby MSER regions into text blocks
        bboxes = []
        for region in regions:
            x, y, w, h = cv2.boundingRect(region)
            if w < 10 or h < 8 or w > self.MAX_ELEMENT_W or h > 60:
                continue
            bboxes.append((x, y, w, h))

        if not bboxes:
            return []

        # Cluster nearby bboxes into text lines/blocks
        clusters = self._cluster_bboxes(bboxes)

        elements = []
        for cluster in clusters:
            x_min = min(b[0] for b in cluster)
            y_min = min(b[1] for b in cluster)
            x_max = max(b[0] + b[2] for b in cluster)
            y_max = max(b[1] + b[3] for b in cluster)
            w = x_max - x_min
            h = y_max - y_min

            if not self._valid_size(w, h):
                continue

            # Pad slightly for click targets
            pad = 4
            elements.append(UIElement(
                index=0,
                bbox=BBox(max(0, x_min - pad + ox),
                          max(0, y_min - pad + oy),
                          w + pad * 2, h + pad * 2),
                element_class="unknown",
                confidence=0.5,
            ))

        return elements

    def _cluster_bboxes(self, bboxes: List[Tuple],
                        x_gap: int = 15, y_gap: int = 8) -> List[List[Tuple]]:
        """Cluster nearby bounding boxes into text blocks."""
        if not bboxes:
            return []

        # Sort by y then x
        sorted_boxes = sorted(bboxes, key=lambda b: (b[1], b[0]))
        clusters = [[sorted_boxes[0]]]

        for box in sorted_boxes[1:]:
            merged = False
            for cluster in clusters:
                # Check if this box is close to any box in the cluster
                for cb in cluster:
                    # Same line (y overlap) and close horizontally
                    y_overlap = (min(box[1] + box[3], cb[1] + cb[3]) -
                                 max(box[1], cb[1]))
                    x_dist = abs(box[0] - (cb[0] + cb[2]))
                    if y_overlap > 0 and x_dist < x_gap:
                        cluster.append(box)
                        merged = True
                        break
                    # Vertically close and x overlap
                    y_dist = abs(box[1] - (cb[1] + cb[3]))
                    x_overlap = (min(box[0] + box[2], cb[0] + cb[2]) -
                                 max(box[0], cb[0]))
                    if y_dist < y_gap and x_overlap > 0:
                        cluster.append(box)
                        merged = True
                        break
                if merged:
                    break
            if not merged:
                clusters.append([box])

        return clusters

    def _valid_size(self, w: int, h: int) -> bool:
        """Check if dimensions are valid for a UI element."""
        return (self.MIN_ELEMENT_W <= w <= self.MAX_ELEMENT_W and
                self.MIN_ELEMENT_H <= h <= self.MAX_ELEMENT_H and
                self.MIN_ELEMENT_AREA <= w * h <= self.MAX_ELEMENT_AREA)

    def _classify(self, el: UIElement) -> str:
        """Classify an element based on size and aspect ratio."""
        w, h = el.bbox.w, el.bbox.h
        if w == 0 or h == 0:
            return "unknown"
        aspect = w / h

        # Small square-ish → icon or checkbox
        if max(w, h) <= self.ICON_MAX_SIZE:
            return "icon"

        # Medium rectangle → button (check BEFORE text_field to avoid overlap)
        if self.BUTTON_ASPECT_RANGE[0] <= aspect <= self.BUTTON_ASPECT_RANGE[1]:
            if 20 <= h <= 55 and 60 <= w <= 300:
                return "button"

        # Wide + tall enough for text → text field (wider than buttons)
        if (self.FIELD_ASPECT_RANGE[0] <= aspect <= self.FIELD_ASPECT_RANGE[1]
                and w >= self.FIELD_MIN_W and 25 <= h <= 60):
            return "text_field"

        # Wide but short → tab or link
        if aspect > 2.0 and h < 30:
            return "link"

        # Tall-ish rectangle → could be a card or container (skip)
        if h > 80:
            return "container"

        return "unknown"

    def _deduplicate(self, elements: List[UIElement],
                     overlap_thresh: float = 0.6) -> List[UIElement]:
        """Remove overlapping detections, keeping higher confidence."""
        if not elements:
            return []

        elements.sort(key=lambda e: -e.confidence)
        kept = []
        for el in elements:
            is_duplicate = False
            for k in kept:
                overlap = el.bbox.overlap_area(k.bbox)
                smaller_area = min(el.bbox.area, k.bbox.area)
                if smaller_area > 0 and overlap / smaller_area > overlap_thresh:
                    is_duplicate = True
                    break
            if not is_duplicate:
                kept.append(el)
        return kept


# ---------------------------------------------------------------------------
# Screenshot annotator
# ---------------------------------------------------------------------------

class ScreenAnnotator:
    """Draws numbered labels on detected UI elements for vision model identification."""

    # Colors for different element types
    COLORS = {
        "button": (0, 180, 0),       # green
        "text_field": (0, 120, 255),  # orange
        "link": (255, 100, 0),        # blue
        "icon": (180, 0, 180),        # purple
        "tab": (0, 200, 200),         # cyan
        "container": (128, 128, 128), # gray
        "unknown": (200, 200, 0),     # yellow
    }

    @staticmethod
    def annotate(screenshot: np.ndarray,
                 elements: List[UIElement]) -> np.ndarray:
        """Draw numbered bounding boxes on the screenshot.

        Args:
            screenshot: BGR numpy array.
            elements: Detected UI elements with indices.

        Returns:
            Annotated screenshot (copy).
        """
        annotated = screenshot.copy()

        for el in elements:
            color = ScreenAnnotator.COLORS.get(el.element_class, (200, 200, 0))
            bbox = el.bbox

            # Draw bounding box
            cv2.rectangle(
                annotated,
                (bbox.x, bbox.y),
                (bbox.x + bbox.w, bbox.y + bbox.h),
                color, 2,
            )

            # Draw numbered label with background
            label = str(el.index)
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)

            # Label background
            label_x = bbox.x
            label_y = max(0, bbox.y - 2)
            cv2.rectangle(
                annotated,
                (label_x, label_y - th - 4),
                (label_x + tw + 6, label_y),
                color, -1,  # filled
            )

            # Label text
            cv2.putText(
                annotated, label,
                (label_x + 3, label_y - 3),
                font, font_scale, (255, 255, 255), thickness,
            )

        return annotated

    @staticmethod
    def annotate_pil(screenshot: Image.Image,
                     elements: List[UIElement]) -> Image.Image:
        """PIL version of annotate for compatibility."""
        cv_img = np.array(screenshot)[:, :, ::-1]  # RGB → BGR
        annotated = ScreenAnnotator.annotate(cv_img, elements)
        return Image.fromarray(annotated[:, :, ::-1])  # BGR → RGB


# ---------------------------------------------------------------------------
# Vision model integration
# ---------------------------------------------------------------------------

class VisionIdentifier:
    """Uses the vision model to identify which detected element matches a target."""

    def __init__(self):
        self._router = None

    def _get_router(self):
        if self._router is None:
            try:
                from agent.model_router import router
                self._router = router
            except ImportError:
                pass
        return self._router

    def identify_element(self, annotated_screenshot: np.ndarray,
                         elements: List[UIElement],
                         target_label: str,
                         element_type: str = "",
                         context: str = "") -> Optional[UIElement]:
        """Ask the vision model which numbered element matches the target.

        Args:
            annotated_screenshot: Screenshot with numbered bounding boxes.
            elements: List of detected UIElements.
            target_label: What we're looking for (e.g. "Create Post", "Title field").
            element_type: Optional type hint ("button", "text_field", etc.).
            context: Optional context about the page.

        Returns:
            The matched UIElement, or None if not found.
        """
        router = self._get_router()
        if not router:
            _log.warning("No vision model available for element identification")
            return None

        # Convert annotated screenshot to base64
        import base64
        _, buf = cv2.imencode(".png", annotated_screenshot)
        img_b64 = base64.b64encode(buf).decode()

        # Build concise prompt
        type_hint = f" (it should be a {element_type})" if element_type else ""
        element_summary = ", ".join(
            f"{el.index}={el.element_class}" for el in elements[:40]
        )

        prompt = (
            f"I need to find the UI element labeled \"{target_label}\"{type_hint} "
            f"in this screenshot.\n\n"
            f"The screenshot has numbered boxes around detected UI elements. "
            f"Each box has a number label.\n"
            f"Detected elements: [{element_summary}]\n\n"
        )
        if context:
            prompt += f"Page context: {context}\n\n"
        prompt += (
            f"Which numbered box contains or is closest to \"{target_label}\"?\n"
            f"Reply with ONLY a JSON object: {{\"box\": <number>, \"confidence\": 0.0-1.0, "
            f"\"reason\": \"brief reason\"}}\n"
            f"If the element is not visible on screen, reply: {{\"box\": 0, \"confidence\": 0.0, "
            f"\"reason\": \"not found\"}}"
        )

        try:
            response = router.chat(
                task_type="vision",
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": [img_b64],
                }],
            )
            text = response.get("message", {}).get("content", "")
            return self._parse_identification(text, elements)

        except Exception as e:
            _log.error("Vision identification failed: %s", e)
            return None

    def describe_page(self, screenshot: np.ndarray) -> str:
        """Get a brief description of what's on screen."""
        router = self._get_router()
        if not router:
            return ""

        import base64
        _, buf = cv2.imencode(".png", screenshot)
        img_b64 = base64.b64encode(buf).decode()

        try:
            response = router.chat(
                task_type="vision",
                messages=[{
                    "role": "user",
                    "content": (
                        "Briefly describe this web page screenshot in 2-3 sentences. "
                        "What app/site is this? What page/section is visible? "
                        "What are the main interactive elements?"
                    ),
                    "images": [img_b64],
                }],
            )
            return response.get("message", {}).get("content", "").strip()
        except Exception:
            return ""

    def verify_action_result(self, before: np.ndarray, after: np.ndarray,
                             expected_change: str) -> Tuple[bool, str]:
        """Ask the vision model if an action succeeded by comparing before/after.

        Args:
            before: Screenshot before the action.
            after: Screenshot after the action.
            expected_change: What should have changed (e.g. "a text field should now be focused").

        Returns:
            (success: bool, explanation: str)
        """
        router = self._get_router()
        if not router:
            # Fall back to SSIM comparison
            return self._ssim_verify(before, after), "SSIM comparison only"

        import base64
        _, buf_b = cv2.imencode(".png", before)
        _, buf_a = cv2.imencode(".png", after)
        b64_before = base64.b64encode(buf_b).decode()
        b64_after = base64.b64encode(buf_a).decode()

        try:
            response = router.chat(
                task_type="vision",
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"I performed an action and expected: {expected_change}\n\n"
                            f"Image 1 is BEFORE the action. Image 2 is AFTER.\n"
                            f"Did the expected change happen?\n"
                            f"Reply with ONLY: {{\"success\": true/false, \"explanation\": \"...\"}}"
                        ),
                        "images": [b64_before, b64_after],
                    },
                ],
            )
            text = response.get("message", {}).get("content", "")
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return data.get("success", False), data.get("explanation", "")
        except Exception as e:
            _log.warning("Vision verify failed: %s", e)

        return self._ssim_verify(before, after), "SSIM fallback"

    @staticmethod
    def _ssim_verify(before: np.ndarray, after: np.ndarray) -> bool:
        """Basic verification: did the screen change at all?"""
        gray_b = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY)
        gray_a = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY)
        # Resize to same dimensions if needed
        if gray_b.shape != gray_a.shape:
            h = min(gray_b.shape[0], gray_a.shape[0])
            w = min(gray_b.shape[1], gray_a.shape[1])
            gray_b = gray_b[:h, :w]
            gray_a = gray_a[:h, :w]
        score = ssim(gray_b, gray_a)
        # If SSIM < 0.95, something changed — action likely had an effect
        return score < 0.95

    def _parse_identification(self, text: str,
                              elements: List[UIElement]) -> Optional[UIElement]:
        """Parse the vision model's identification response."""
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                box_num = int(data.get("box", 0))
                confidence = float(data.get("confidence", 0.0))

                if box_num > 0 and confidence > 0.2:
                    for el in elements:
                        if el.index == box_num:
                            el.matched = True
                            el.confidence = confidence
                            el.label = data.get("reason", "")
                            return el

            # Fallback: try to find a bare number in the response
            numbers = re.findall(r'\b(\d{1,3})\b', text)
            for num_str in numbers:
                num = int(num_str)
                for el in elements:
                    if el.index == num:
                        el.matched = True
                        el.confidence = 0.4
                        return el

        except (json.JSONDecodeError, ValueError) as e:
            _log.warning("Failed to parse identification: %s", e)

        return None


# ---------------------------------------------------------------------------
# WebVisionEngine — the main API
# ---------------------------------------------------------------------------

class WebVisionEngine:
    """Enhanced web UI interaction engine.

    Provides reliable find-and-interact methods that use:
    1. OpenCV element detection (precise bounding boxes)
    2. Vision model identification (match target to detected element)
    3. Post-action verification (confirm the action worked)
    4. Smart retry (re-detect and retry on failure)

    Usage:
        engine = WebVisionEngine()
        result = engine.find_and_click("Create Post", element_type="button")
        result = engine.find_and_type("Title", "My awesome post")
    """

    MAX_RETRIES = 3
    VERIFY_WAIT = 0.8       # seconds to wait before verification screenshot
    RETRY_WAIT = 1.0        # seconds between retries
    PAGE_LOAD_TIMEOUT = 15  # max seconds to wait for page load

    def __init__(self, use_playwright_fallback: bool = True):
        self._detector = ElementDetector()
        self._annotator = ScreenAnnotator()
        self._identifier = VisionIdentifier()
        self._last_screenshot: Optional[np.ndarray] = None
        self._last_elements: List[UIElement] = []
        self._use_playwright = use_playwright_fallback
        self._playwright_browser = None  # lazy loaded

    def _get_playwright(self):
        """Lazy-load Playwright fallback browser."""
        if self._playwright_browser is None and self._use_playwright:
            try:
                from vision.playwright_fallback import PlaywrightBrowser
                self._playwright_browser = PlaywrightBrowser(headless=False)
                _log.info("Playwright fallback browser available")
            except Exception as e:
                _log.debug("Playwright fallback not available: %s", e)
                self._use_playwright = False
        return self._playwright_browser

    # ------------------------------------------------------------------
    # Core: capture + detect
    # ------------------------------------------------------------------

    def capture(self, region: Optional[BBox] = None) -> np.ndarray:
        """Capture the screen as an OpenCV BGR array."""
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            if region:
                monitor = {
                    "left": region.x, "top": region.y,
                    "width": region.w, "height": region.h,
                }
            raw = sct.grab(monitor)
            img = np.array(raw)[:, :, :3]  # Drop alpha, keep BGR
        self._last_screenshot = img
        return img

    def detect_elements(self, screenshot: Optional[np.ndarray] = None,
                        region: Optional[BBox] = None) -> List[UIElement]:
        """Detect all UI elements in the current screenshot."""
        if screenshot is None:
            screenshot = self.capture()
        elements = self._detector.detect(screenshot, region)
        self._last_elements = elements
        _log.info("Detected %d UI elements", len(elements))
        return elements

    def annotate(self, screenshot: np.ndarray,
                 elements: List[UIElement]) -> np.ndarray:
        """Create an annotated screenshot with numbered elements."""
        return self._annotator.annotate(screenshot, elements)

    # ------------------------------------------------------------------
    # Find — locate an element by its visual label
    # ------------------------------------------------------------------

    def find_element(self, target_label: str,
                     element_type: str = "",
                     region: Optional[BBox] = None,
                     context: str = "") -> Optional[UIElement]:
        """Find a UI element by its visible label.

        Args:
            target_label: Text label to find (e.g. "Create Post", "Submit").
            element_type: Optional type hint ("button", "text_field", etc.).
            region: Optional sub-region to search within.
            context: Optional page context for the vision model.

        Returns:
            The matched UIElement, or None if not found.
        """
        # Step 1: Capture and detect
        screenshot = self.capture(region)
        elements = self.detect_elements(screenshot, region)

        if not elements:
            _log.warning("No UI elements detected on screen")
            return None

        # Step 2: Annotate
        annotated = self.annotate(screenshot, elements)

        # Step 3: Vision model identifies the target
        matched = self._identifier.identify_element(
            annotated, elements, target_label,
            element_type=element_type, context=context,
        )

        if matched:
            _log.info("Found '%s' at box #%d (%d,%d) conf=%.2f",
                      target_label, matched.index,
                      matched.bbox.center[0], matched.bbox.center[1],
                      matched.confidence)
        else:
            _log.warning("Could not find '%s' among %d elements",
                         target_label, len(elements))

        return matched

    # ------------------------------------------------------------------
    # Find and interact
    # ------------------------------------------------------------------

    def find_and_click(self, target_label: str,
                       element_type: str = "",
                       verify: bool = True,
                       expected_change: str = "",
                       region: Optional[BBox] = None,
                       context: str = "") -> ActionResult:
        """Find an element and click it, with verification.

        Args:
            target_label: Text label of the element to click.
            element_type: Optional type hint.
            verify: Whether to verify the click succeeded.
            expected_change: What should change after clicking.
            region: Optional sub-region to search within.
            context: Optional page context.

        Returns:
            ActionResult with success status and details.
        """
        import pyautogui

        for attempt in range(self.MAX_RETRIES):
            # Capture before screenshot for verification
            before_ss = self.capture() if verify else None

            # Find the element
            element = self.find_element(
                target_label, element_type, region, context,
            )

            if not element:
                if attempt < self.MAX_RETRIES - 1:
                    _log.info("Retry %d: element '%s' not found, waiting...",
                              attempt + 1, target_label)
                    time.sleep(self.RETRY_WAIT)
                    continue
                return ActionResult(
                    ok=False,
                    method="vision_annotated",
                    error=f"Element '{target_label}' not found after {self.MAX_RETRIES} attempts",
                    retries=attempt,
                )

            # Click the center of the detected element
            cx, cy = element.bbox.center
            _log.info("Clicking '%s' at (%d, %d)", target_label, cx, cy)
            pyautogui.click(cx, cy)

            # Verify the click succeeded
            if verify:
                time.sleep(self.VERIFY_WAIT)
                after_ss = self.capture()

                if not expected_change:
                    expected_change = f"the screen should change after clicking '{target_label}'"

                success, explanation = self._identifier.verify_action_result(
                    before_ss, after_ss, expected_change,
                )

                if success:
                    return ActionResult(
                        ok=True,
                        method="vision_annotated",
                        element=element,
                        coords=(cx, cy),
                        verified=True,
                        retries=attempt,
                        details=explanation,
                    )
                else:
                    _log.warning("Click verification failed (attempt %d): %s",
                                 attempt + 1, explanation)
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RETRY_WAIT)
                        continue
                    # Return success=True but verified=False — the click happened
                    # but we couldn't confirm the expected change
                    return ActionResult(
                        ok=True,
                        method="vision_annotated",
                        element=element,
                        coords=(cx, cy),
                        verified=False,
                        retries=attempt,
                        details=f"Clicked but verification uncertain: {explanation}",
                    )

            # No verification requested
            return ActionResult(
                ok=True,
                method="vision_annotated",
                element=element,
                coords=(cx, cy),
                verified=False,
                retries=attempt,
            )

        # ------ Playwright fallback: DOM-level click when vision fails ------
        pw = self._get_playwright()
        if pw:
            _log.info("Vision failed for '%s'. Trying Playwright DOM fallback...",
                      target_label)
            try:
                pw_result = pw.click_by_text(target_label, element_type=element_type)
                if pw_result.ok:
                    _log.info("Playwright fallback succeeded for '%s'", target_label)
                    return ActionResult(
                        ok=True,
                        method="playwright_fallback",
                        coords=(0, 0),
                        verified=False,
                        retries=self.MAX_RETRIES,
                        details=f"Playwright clicked '{target_label}' via {pw_result.selector}",
                    )
                _log.info("Playwright fallback also failed: %s", pw_result.error)
            except Exception as e:
                _log.warning("Playwright fallback error: %s", e)

        return ActionResult(
            ok=False,
            error=f"Failed to click '{target_label}' after {self.MAX_RETRIES} vision retries + Playwright fallback",
            retries=self.MAX_RETRIES,
        )

    def find_and_type(self, field_label: str, text: str,
                      clear_first: bool = True,
                      verify: bool = True,
                      region: Optional[BBox] = None,
                      context: str = "") -> ActionResult:
        """Find a text field, click it to focus, and type text.

        Args:
            field_label: Label of the text field to find.
            text: Text to type into the field.
            clear_first: Whether to select-all and delete before typing.
            verify: Whether to verify the typing succeeded.
            region: Optional sub-region to search.
            context: Optional page context.

        Returns:
            ActionResult with success status.
        """
        import pyautogui

        # First, find and click the field
        click_result = self.find_and_click(
            field_label,
            element_type="text_field",
            verify=True,
            expected_change=f"the '{field_label}' text field should be focused/highlighted",
            region=region,
            context=context,
        )

        if not click_result.ok:
            # Playwright fallback for find-and-type as a single operation
            pw = self._get_playwright()
            if pw:
                _log.info("Vision find_and_type failed for '%s'. Trying Playwright...",
                          field_label)
                try:
                    pw_result = pw.type_into(field_label, text, clear_first=clear_first)
                    if pw_result.ok:
                        return ActionResult(
                            ok=True,
                            method="playwright_fallback",
                            verified=False,
                            details=f"Playwright typed into '{field_label}' via {pw_result.selector}",
                        )
                except Exception as e:
                    _log.warning("Playwright type fallback error: %s", e)
            return ActionResult(
                ok=False,
                error=f"Could not find/click field '{field_label}': {click_result.error}",
            )

        # If click was via Playwright, use Playwright for typing too
        if click_result.method == "playwright_fallback":
            pw = self._get_playwright()
            if pw:
                try:
                    pw_result = pw.type_into(field_label, text, clear_first=clear_first)
                    if pw_result.ok:
                        return ActionResult(
                            ok=True,
                            method="playwright_fallback",
                            verified=False,
                            details=f"Playwright typed into '{field_label}'",
                        )
                except Exception as e:
                    _log.warning("Playwright type after click error: %s", e)

        # Small delay for focus to register
        time.sleep(0.3)

        # Clear existing content if requested
        if clear_first:
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            pyautogui.press("delete")
            time.sleep(0.1)

        # Type the text with human-like speed
        before_ss = self.capture() if verify else None
        pyautogui.write(text, interval=0.03)

        if verify:
            time.sleep(self.VERIFY_WAIT)
            after_ss = self.capture()
            success, explanation = self._identifier.verify_action_result(
                before_ss, after_ss,
                f"the text \"{text[:30]}...\" should now appear in the field",
            )
            return ActionResult(
                ok=True,
                method="vision_annotated",
                element=click_result.element,
                coords=click_result.coords,
                verified=success,
                details=explanation,
            )

        return ActionResult(
            ok=True,
            method="vision_annotated",
            element=click_result.element,
            coords=click_result.coords,
        )

    def type_special(self, text: str):
        """Type text that may contain special characters (Unicode, etc.).

        Uses clipboard paste instead of pyautogui.write() which only handles ASCII.
        """
        import pyautogui
        import subprocess

        # Copy to clipboard
        process = subprocess.Popen(
            ["clip.exe"], stdin=subprocess.PIPE, shell=True,
        )
        process.communicate(text.encode("utf-16-le"))

        # Paste
        pyautogui.hotkey("ctrl", "v")

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def navigate_to_url(self, url: str) -> ActionResult:
        """Navigate to a URL in the browser (Ctrl+L → type → Enter)."""
        import pyautogui

        before_ss = self.capture()

        # Focus address bar
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.5)

        # Type URL
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.write(url, interval=0.02)
        time.sleep(0.3)

        # Navigate
        pyautogui.press("enter")

        # Wait for page load
        loaded = self.wait_for_page_load()

        after_ss = self.capture()
        changed = self._identifier._ssim_verify(before_ss, after_ss)

        return ActionResult(
            ok=changed,
            method="navigation",
            verified=loaded,
            details=f"Navigated to {url}" if changed else f"Page may not have loaded: {url}",
        )

    def scroll_page(self, direction: str = "down", amount: int = 3) -> ActionResult:
        """Scroll the page."""
        import pyautogui

        before_ss = self.capture()
        clicks = -amount if direction == "down" else amount
        pyautogui.scroll(clicks)
        time.sleep(0.5)
        after_ss = self.capture()

        changed = self._identifier._ssim_verify(before_ss, after_ss)
        return ActionResult(
            ok=True,
            method="scroll",
            verified=changed,
            details=f"Scrolled {direction} by {amount}",
        )

    # ------------------------------------------------------------------
    # Verification and waiting
    # ------------------------------------------------------------------

    def wait_for_page_load(self, timeout: Optional[float] = None) -> bool:
        """Wait for the page to stabilize (stop changing).

        Takes screenshots at intervals and uses SSIM to detect when
        the page has finished loading/rendering.
        """
        timeout = timeout or self.PAGE_LOAD_TIMEOUT
        start = time.time()
        stable_count = 0
        required_stable = 2
        prev_ss = self.capture()

        while time.time() - start < timeout:
            time.sleep(1.0)
            curr_ss = self.capture()

            gray_p = cv2.cvtColor(prev_ss, cv2.COLOR_BGR2GRAY)
            gray_c = cv2.cvtColor(curr_ss, cv2.COLOR_BGR2GRAY)
            if gray_p.shape != gray_c.shape:
                prev_ss = curr_ss
                continue

            score = ssim(gray_p, gray_c)
            if score > 0.97:
                stable_count += 1
                if stable_count >= required_stable:
                    _log.info("Page stable (SSIM=%.4f) after %.1fs",
                              score, time.time() - start)
                    return True
            else:
                stable_count = 0

            prev_ss = curr_ss

        _log.warning("Page load timeout after %.0fs", timeout)
        return False

    def wait_for_element(self, target_label: str,
                         element_type: str = "",
                         timeout: float = 10.0,
                         poll_interval: float = 1.0) -> Optional[UIElement]:
        """Wait for a specific element to appear on screen."""
        start = time.time()
        while time.time() - start < timeout:
            element = self.find_element(target_label, element_type)
            if element:
                return element
            time.sleep(poll_interval)
        return None

    # ------------------------------------------------------------------
    # Page state
    # ------------------------------------------------------------------

    def get_page_state(self) -> PageState:
        """Capture and analyze the current page state."""
        screenshot = self.capture()
        elements = self.detect_elements(screenshot)

        # Separate text regions from other elements
        text_count = sum(1 for e in elements
                         if e.element_class in ("link", "text_field"))
        button_count = sum(1 for e in elements
                           if e.element_class == "button")

        # Get page description from vision model
        description = self._identifier.describe_page(screenshot)

        return PageState(
            elements_detected=len(elements),
            text_regions_detected=text_count,
            description=description,
            timestamp=time.time(),
        )

    # ------------------------------------------------------------------
    # Debug / diagnostic helpers
    # ------------------------------------------------------------------

    def save_debug_screenshot(self, name: str = "",
                              annotated: bool = True) -> str:
        """Save a debug screenshot with annotations for troubleshooting."""
        screenshot = self.capture()
        elements = self.detect_elements(screenshot)

        if annotated:
            screenshot = self.annotate(screenshot, elements)

        debug_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "debug_screenshots",
        )
        os.makedirs(debug_dir, exist_ok=True)
        fname = f"wv_{name}_{int(time.time())}.png" if name else f"wv_{int(time.time())}.png"
        path = os.path.join(debug_dir, fname)
        cv2.imwrite(path, screenshot)
        _log.info("Debug screenshot saved: %s (%d elements)", path, len(elements))
        return path

    def get_element_summary(self) -> str:
        """Get a human-readable summary of detected elements."""
        if not self._last_elements:
            return "No elements detected. Call detect_elements() first."

        by_type = {}
        for el in self._last_elements:
            by_type.setdefault(el.element_class, []).append(el)

        lines = [f"Detected {len(self._last_elements)} UI elements:"]
        for etype, els in sorted(by_type.items()):
            lines.append(f"  {etype}: {len(els)}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Workflow step definitions
# ---------------------------------------------------------------------------

@dataclass
class WorkflowStep:
    """A single step in a multi-step web workflow.

    Each step has an action to perform and an expected outcome to verify.
    If verification fails, recovery actions can be attempted.
    """
    name: str                       # human-readable step name
    action: str                     # "click", "type", "navigate", "scroll", "wait", "key"
    target: str = ""                # element label for click/type
    text: str = ""                  # text for type action
    url: str = ""                   # URL for navigate action
    key: str = ""                   # key combo for key action (e.g. "ctrl+a", "enter")
    element_type: str = ""          # type hint for element detection
    direction: str = "down"         # scroll direction
    amount: int = 3                 # scroll amount
    wait_seconds: float = 0.0       # explicit wait duration
    clear_first: bool = True        # clear field before typing
    verify: bool = True             # whether to verify this step
    expected_change: str = ""       # what should change after the action
    # Recovery
    recovery_actions: List[str] = field(default_factory=list)
    # e.g. ["scroll_down", "wait_2s", "retry"]
    optional: bool = False          # if True, workflow continues even if step fails
    # Runtime state
    status: str = "pending"         # "pending", "running", "passed", "failed", "skipped"
    result: Optional[ActionResult] = None
    error: str = ""
    attempts: int = 0


@dataclass
class WorkflowResult:
    """Result of executing a complete workflow."""
    ok: bool
    workflow_name: str = ""
    steps_total: int = 0
    steps_passed: int = 0
    steps_failed: int = 0
    steps_skipped: int = 0
    failed_step: str = ""           # name of the step that failed (if any)
    error: str = ""
    duration_seconds: float = 0.0
    step_results: List[Dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# WebWorkflow — multi-step action chains with verification
# ---------------------------------------------------------------------------

class WebWorkflow:
    """Executes a sequence of web UI steps with verification between each.

    This is the key abstraction that makes multi-step web interaction reliable.
    Instead of chaining raw clicks and hoping, each step:
    1. Executes the action (click, type, navigate, etc.)
    2. Verifies the expected outcome occurred
    3. If verification fails, attempts recovery actions
    4. Only proceeds to the next step if verification passes

    Usage:
        engine = WebVisionEngine()
        workflow = WebWorkflow(engine, "Post on Reddit")
        workflow.add_step(WorkflowStep(
            name="Navigate to subreddit",
            action="navigate",
            url="https://www.reddit.com/r/test",
            expected_change="Reddit page for r/test should be visible",
        ))
        workflow.add_step(WorkflowStep(
            name="Click Create Post",
            action="click",
            target="Create Post",
            element_type="button",
            expected_change="Post creation form should appear",
        ))
        workflow.add_step(WorkflowStep(
            name="Type title",
            action="type",
            target="Title",
            text="My post title",
            expected_change="Title field should contain the typed text",
        ))
        result = workflow.execute()
    """

    # Recovery action handlers
    RECOVERY_SCROLL_DOWN = "scroll_down"
    RECOVERY_SCROLL_UP = "scroll_up"
    RECOVERY_WAIT_1S = "wait_1s"
    RECOVERY_WAIT_2S = "wait_2s"
    RECOVERY_WAIT_5S = "wait_5s"
    RECOVERY_RETRY = "retry"
    RECOVERY_PAGE_LOAD = "wait_page_load"
    RECOVERY_PRESS_ESCAPE = "press_escape"
    RECOVERY_CLICK_BODY = "click_body"

    def __init__(self, engine: WebVisionEngine, name: str = ""):
        self._engine = engine
        self.name = name
        self.steps: List[WorkflowStep] = []
        self._on_step_callback = None  # Optional callback for UI updates

    def add_step(self, step: WorkflowStep) -> "WebWorkflow":
        """Add a step to the workflow. Returns self for chaining."""
        self.steps.append(step)
        return self

    def on_step(self, callback) -> "WebWorkflow":
        """Set a callback for step status updates: callback(step_index, step, status)."""
        self._on_step_callback = callback
        return self

    def execute(self) -> WorkflowResult:
        """Execute all workflow steps in sequence with verification.

        Returns:
            WorkflowResult with overall success and per-step details.
        """
        import pyautogui

        start_time = time.time()
        result = WorkflowResult(
            ok=False,
            workflow_name=self.name,
            steps_total=len(self.steps),
        )

        _log.info("[workflow] Starting '%s' with %d steps", self.name, len(self.steps))

        for i, step in enumerate(self.steps):
            step.status = "running"
            step.attempts = 0
            self._notify(i, step, "running")

            _log.info("[workflow] Step %d/%d: %s (%s)",
                      i + 1, len(self.steps), step.name, step.action)

            # Execute the step with retries
            step_ok = self._execute_step(step)

            if step_ok:
                step.status = "passed"
                result.steps_passed += 1
                self._notify(i, step, "passed")
                _log.info("[workflow] Step %d PASSED: %s", i + 1, step.name)
            elif step.optional:
                step.status = "skipped"
                result.steps_skipped += 1
                self._notify(i, step, "skipped")
                _log.warning("[workflow] Step %d SKIPPED (optional): %s — %s",
                             i + 1, step.name, step.error)
            else:
                step.status = "failed"
                result.steps_failed += 1
                result.failed_step = step.name
                result.error = step.error
                self._notify(i, step, "failed")
                _log.error("[workflow] Step %d FAILED: %s — %s",
                           i + 1, step.name, step.error)

                # Record partial results and stop
                result.step_results = self._collect_step_results()
                result.duration_seconds = time.time() - start_time
                return result

            result.step_results = self._collect_step_results()

        result.ok = True
        result.duration_seconds = time.time() - start_time
        _log.info("[workflow] '%s' completed in %.1fs: %d passed, %d skipped",
                  self.name, result.duration_seconds,
                  result.steps_passed, result.steps_skipped)
        return result

    def _execute_step(self, step: WorkflowStep) -> bool:
        """Execute a single step, with recovery on failure."""
        import pyautogui

        # First attempt
        step.attempts += 1
        action_result = self._run_action(step)
        step.result = action_result

        if action_result.ok and (not step.verify or action_result.verified):
            return True

        # If action succeeded but verification failed, try recovery
        if action_result.ok and step.verify and not action_result.verified:
            _log.info("[workflow] Action succeeded but verification failed, trying recovery")
            for recovery in (step.recovery_actions or [self.RECOVERY_WAIT_2S, self.RECOVERY_RETRY]):
                recovered = self._try_recovery(step, recovery)
                if recovered:
                    return True

        # If action itself failed, try recovery
        if not action_result.ok:
            step.error = action_result.error
            for recovery in (step.recovery_actions or [
                self.RECOVERY_SCROLL_DOWN, self.RECOVERY_WAIT_2S, self.RECOVERY_RETRY
            ]):
                recovered = self._try_recovery(step, recovery)
                if recovered:
                    return True

        step.error = step.error or action_result.error or "Step failed after recovery attempts"
        return False

    def _run_action(self, step: WorkflowStep) -> ActionResult:
        """Execute the actual action for a step."""
        import pyautogui

        try:
            if step.action == "click":
                return self._engine.find_and_click(
                    step.target,
                    element_type=step.element_type,
                    verify=step.verify,
                    expected_change=step.expected_change,
                )
            elif step.action == "type":
                return self._engine.find_and_type(
                    step.target,
                    step.text,
                    clear_first=step.clear_first,
                    verify=step.verify,
                )
            elif step.action == "navigate":
                return self._engine.navigate_to_url(step.url)
            elif step.action == "scroll":
                return self._engine.scroll_page(step.direction, step.amount)
            elif step.action == "wait":
                time.sleep(step.wait_seconds or 2.0)
                return ActionResult(ok=True, method="wait",
                                    details=f"Waited {step.wait_seconds}s")
            elif step.action == "key":
                keys = step.key.split("+")
                if len(keys) > 1:
                    pyautogui.hotkey(*keys)
                else:
                    pyautogui.press(keys[0])
                time.sleep(0.3)
                return ActionResult(ok=True, method="key_press",
                                    details=f"Pressed {step.key}")
            elif step.action == "wait_for_element":
                element = self._engine.wait_for_element(
                    step.target,
                    element_type=step.element_type,
                    timeout=step.wait_seconds or 10.0,
                )
                if element:
                    return ActionResult(ok=True, method="wait_for_element",
                                        element=element,
                                        details=f"Found '{step.target}'")
                return ActionResult(ok=False,
                                    error=f"Element '{step.target}' not found within timeout")
            elif step.action == "type_special":
                # For unicode/special text, use clipboard paste
                self._engine.type_special(step.text)
                return ActionResult(ok=True, method="type_special",
                                    details=f"Typed special text via clipboard")
            else:
                return ActionResult(ok=False, error=f"Unknown action: {step.action}")

        except Exception as e:
            _log.error("[workflow] Action '%s' raised exception: %s", step.action, e)
            return ActionResult(ok=False, error=str(e))

    def _try_recovery(self, step: WorkflowStep, recovery: str) -> bool:
        """Attempt a recovery action, then retry the original step.

        Returns True if recovery + retry succeeded.
        """
        import pyautogui

        _log.info("[workflow] Recovery: %s", recovery)

        if recovery == self.RECOVERY_SCROLL_DOWN:
            pyautogui.scroll(-3)
            time.sleep(0.5)
        elif recovery == self.RECOVERY_SCROLL_UP:
            pyautogui.scroll(3)
            time.sleep(0.5)
        elif recovery == self.RECOVERY_WAIT_1S:
            time.sleep(1.0)
        elif recovery == self.RECOVERY_WAIT_2S:
            time.sleep(2.0)
        elif recovery == self.RECOVERY_WAIT_5S:
            time.sleep(5.0)
        elif recovery == self.RECOVERY_PAGE_LOAD:
            self._engine.wait_for_page_load()
        elif recovery == self.RECOVERY_PRESS_ESCAPE:
            pyautogui.press("escape")
            time.sleep(0.5)
        elif recovery == self.RECOVERY_CLICK_BODY:
            # Click center of screen to dismiss overlays
            import mss
            with mss.mss() as sct:
                m = sct.monitors[1]
                pyautogui.click(m["width"] // 2, m["height"] // 2)
            time.sleep(0.5)
        elif recovery == self.RECOVERY_RETRY:
            step.attempts += 1
            if step.attempts > 3:
                return False
            action_result = self._run_action(step)
            step.result = action_result
            if action_result.ok and (not step.verify or action_result.verified):
                return True
            return False
        else:
            _log.warning("Unknown recovery action: %s", recovery)

        return False  # Recovery actions other than RETRY don't directly succeed

    def _notify(self, step_index: int, step: WorkflowStep, status: str):
        """Notify the callback about step status changes."""
        if self._on_step_callback:
            try:
                self._on_step_callback(step_index, step, status)
            except Exception:
                pass

    def _collect_step_results(self) -> List[Dict]:
        """Collect results from all steps for the WorkflowResult."""
        results = []
        for step in self.steps:
            results.append({
                "name": step.name,
                "action": step.action,
                "status": step.status,
                "attempts": step.attempts,
                "error": step.error,
                "verified": step.result.verified if step.result else False,
            })
        return results


# ---------------------------------------------------------------------------
# Pre-built workflow templates
# ---------------------------------------------------------------------------

class WorkflowTemplates:
    """Pre-built workflow templates for common social platform actions.

    These encode the step-by-step UI navigation knowledge that the LLM
    currently fails to execute reliably via coordinate guessing.
    """

    @staticmethod
    def reddit_text_post(engine: WebVisionEngine,
                         subreddit: str,
                         title: str,
                         body: str) -> WebWorkflow:
        """Create a workflow for posting a text post on Reddit.

        Args:
            engine: WebVisionEngine instance.
            subreddit: Target subreddit (e.g. "test", "LocalLLaMA").
            title: Post title.
            body: Post body text.

        Returns:
            Configured WebWorkflow ready to execute.
        """
        wf = WebWorkflow(engine, f"Reddit post to r/{subreddit}")

        wf.add_step(WorkflowStep(
            name="Navigate to subreddit",
            action="navigate",
            url=f"https://www.reddit.com/r/{subreddit}/submit",
            expected_change=f"Reddit submit page for r/{subreddit}",
        ))

        wf.add_step(WorkflowStep(
            name="Wait for page load",
            action="wait",
            wait_seconds=3.0,
            verify=False,
        ))

        wf.add_step(WorkflowStep(
            name="Click title field",
            action="click",
            target="Title",
            element_type="text_field",
            expected_change="Title input field should be focused",
            recovery_actions=["wait_2s", "scroll_down", "retry"],
        ))

        wf.add_step(WorkflowStep(
            name="Type title",
            action="type",
            target="Title",
            text=title,
            expected_change="Title field should contain the typed text",
        ))

        wf.add_step(WorkflowStep(
            name="Click body field",
            action="click",
            target="Text",
            element_type="text_field",
            expected_change="Body text area should be focused",
            recovery_actions=["scroll_down", "wait_2s", "retry"],
        ))

        wf.add_step(WorkflowStep(
            name="Type body",
            action="type_special",
            text=body,
            verify=False,
        ))

        wf.add_step(WorkflowStep(
            name="Click Post button",
            action="click",
            target="Post",
            element_type="button",
            expected_change="Post should be submitted, page should navigate to the new post",
            recovery_actions=["scroll_down", "wait_2s", "retry"],
        ))

        wf.add_step(WorkflowStep(
            name="Verify post submitted",
            action="wait",
            wait_seconds=3.0,
            verify=False,
        ))

        return wf

    @staticmethod
    def reddit_comment(engine: WebVisionEngine,
                       post_url: str,
                       comment_text: str) -> WebWorkflow:
        """Create a workflow for commenting on a Reddit post."""
        wf = WebWorkflow(engine, "Reddit comment")

        wf.add_step(WorkflowStep(
            name="Navigate to post",
            action="navigate",
            url=post_url,
            expected_change="Reddit post page should load",
        ))

        wf.add_step(WorkflowStep(
            name="Wait for page load",
            action="wait",
            wait_seconds=3.0,
            verify=False,
        ))

        wf.add_step(WorkflowStep(
            name="Click comment field",
            action="click",
            target="Add a comment",
            element_type="text_field",
            expected_change="Comment input should be focused",
            recovery_actions=["scroll_down", "wait_2s", "retry"],
        ))

        wf.add_step(WorkflowStep(
            name="Type comment",
            action="type_special",
            text=comment_text,
            verify=False,
        ))

        wf.add_step(WorkflowStep(
            name="Submit comment",
            action="click",
            target="Comment",
            element_type="button",
            expected_change="Comment should be submitted and visible below",
            recovery_actions=["wait_2s", "retry"],
        ))

        return wf

    @staticmethod
    def twitter_post(engine: WebVisionEngine,
                     tweet_text: str) -> WebWorkflow:
        """Create a workflow for posting a tweet on Twitter/X."""
        wf = WebWorkflow(engine, "Twitter post")

        wf.add_step(WorkflowStep(
            name="Navigate to Twitter",
            action="navigate",
            url="https://x.com/compose/post",
            expected_change="Twitter compose page should load",
        ))

        wf.add_step(WorkflowStep(
            name="Wait for page load",
            action="wait",
            wait_seconds=3.0,
            verify=False,
        ))

        wf.add_step(WorkflowStep(
            name="Click compose area",
            action="click",
            target="What is happening",
            element_type="text_field",
            expected_change="Tweet compose area should be focused",
            recovery_actions=["wait_2s", "click_body", "retry"],
        ))

        wf.add_step(WorkflowStep(
            name="Type tweet",
            action="type_special",
            text=tweet_text,
            verify=False,
        ))

        wf.add_step(WorkflowStep(
            name="Click Post button",
            action="click",
            target="Post",
            element_type="button",
            expected_change="Tweet should be posted, compose area should close",
            recovery_actions=["wait_2s", "retry"],
        ))

        return wf

    @staticmethod
    def youtube_upload_metadata(engine: WebVisionEngine,
                                title: str,
                                description: str) -> WebWorkflow:
        """Create a workflow for filling YouTube upload metadata.

        Note: This assumes a video has already been selected for upload
        and the metadata form is visible.
        """
        wf = WebWorkflow(engine, "YouTube upload metadata")

        wf.add_step(WorkflowStep(
            name="Click title field",
            action="click",
            target="Title",
            element_type="text_field",
            expected_change="Title field should be focused",
        ))

        wf.add_step(WorkflowStep(
            name="Clear and type title",
            action="type",
            target="Title",
            text=title,
            clear_first=True,
            expected_change="Title field should contain the new title",
        ))

        wf.add_step(WorkflowStep(
            name="Click description field",
            action="click",
            target="Description",
            element_type="text_field",
            expected_change="Description field should be focused",
            recovery_actions=["scroll_down", "wait_2s", "retry"],
        ))

        wf.add_step(WorkflowStep(
            name="Type description",
            action="type_special",
            text=description,
            verify=False,
        ))

        wf.add_step(WorkflowStep(
            name="Set not made for kids",
            action="click",
            target="No, it's not made for kids",
            expected_change="Not made for kids option should be selected",
            recovery_actions=["scroll_down", "retry"],
            optional=True,
        ))

        return wf

    @staticmethod
    def generic_form_fill(engine: WebVisionEngine,
                          url: str,
                          fields: Dict[str, str],
                          submit_label: str = "Submit") -> WebWorkflow:
        """Create a workflow for filling out a generic web form.

        Args:
            engine: WebVisionEngine instance.
            url: URL of the form page.
            fields: Dict of field_label → text_to_type.
            submit_label: Label of the submit button.
        """
        wf = WebWorkflow(engine, f"Form fill: {url}")

        wf.add_step(WorkflowStep(
            name="Navigate to form",
            action="navigate",
            url=url,
        ))

        wf.add_step(WorkflowStep(
            name="Wait for page load",
            action="wait",
            wait_seconds=2.0,
            verify=False,
        ))

        for field_label, text in fields.items():
            wf.add_step(WorkflowStep(
                name=f"Fill '{field_label}'",
                action="type",
                target=field_label,
                text=text,
                element_type="text_field",
                recovery_actions=["scroll_down", "wait_2s", "retry"],
            ))

        wf.add_step(WorkflowStep(
            name="Submit form",
            action="click",
            target=submit_label,
            element_type="button",
            expected_change="Form should be submitted",
        ))

        return wf
