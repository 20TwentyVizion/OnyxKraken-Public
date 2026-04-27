"""TeachMe Component — imitation learning via demonstration.

Onyx learns new skills by watching the user do them first.

Workflow:
    1. RECORD  — User says "watch me." Onyx hooks mouse+keyboard,
                 captures screenshots at every meaningful event.
    2. ANALYZE — Vision model studies each (screenshot, action) pair:
                 what was clicked, what changed, what the intent was.
    3. REPLAY  — Onyx replays the learned sequence autonomously.
    4. VERIFY  — User confirms right/wrong per step.
    5. CORRECT — Wrong steps get re-demonstrated or manually fixed.
    6. QUESTION — Onyx asks about ambiguous UI elements it noticed.
                  One answer can resolve multiple queued questions.
    7. STORE   — Learned workflow becomes a reusable Recipe.

Architecture:
    DemoRecorder     — captures input events + screenshots
    DemoAnalyzer     — vision model understands each step
    DemoPlayer       — replays via desktop controller
    VerificationLoop — user confirms / corrects
    QuestionEngine   — asks targeted questions about unclear UI
    RecipeStore      — persists learned workflows as JSON

Each Recipe is essentially a program-specific macro with semantic
understanding. Onyx doesn't just replay coordinates — it understands
"click the Upload button" and can adapt if the button moves.
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

from core.components.base import (
    OnyxComponent, ComponentResult, ComponentStatus, ActionDescriptor,
)

_log = logging.getLogger("components.teach_me")

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
_RECIPE_DIR = os.path.join(_ROOT, "data", "recipes")
_DEMO_DIR = os.path.join(_ROOT, "data", "demos")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class InputEvent:
    """A single mouse or keyboard event during a demonstration."""
    timestamp: float            # absolute time
    event_type: str             # "click", "double_click", "right_click",
                                # "scroll", "key_press", "key_release",
                                # "key_combo", "type_text"
    x: int = 0                  # mouse position
    y: int = 0
    button: str = ""            # "left", "right", "middle"
    key: str = ""               # key name or character
    scroll_delta: int = 0       # scroll amount
    text: str = ""              # for type_text events (accumulated chars)
    modifiers: List[str] = field(default_factory=list)  # ["ctrl", "shift", ...]
    # Screenshot index taken at this event
    screenshot_index: int = -1

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DemoStep:
    """An analyzed step — an InputEvent enriched with vision understanding."""
    index: int
    event: InputEvent
    screenshot_before: str = ""     # path to screenshot taken before action
    screenshot_after: str = ""      # path to screenshot taken after action
    # Vision analysis
    ui_element_description: str = ""  # "the blue Upload button in the top bar"
    action_description: str = ""      # "Clicked the Upload button"
    intent: str = ""                  # "Upload a file to YouTube"
    element_type: str = ""            # "button", "text_field", "menu", "link"
    element_label: str = ""           # OCR/detected label text
    confidence: float = 0.0           # 0-1, how sure vision is about this
    # Verification
    verified: bool = False
    correct: bool = False
    user_correction: str = ""         # user's explanation if wrong
    # Questions the AI has about this step
    questions: List[str] = field(default_factory=list)
    question_answers: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["event"] = self.event.to_dict()
        return d


@dataclass
class Recipe:
    """A learned, reusable workflow for a specific task.

    This is the end product of a TeachMe session. Onyx can replay it
    any time, adapting to UI changes via vision model matching.
    """
    id: str
    name: str                       # "Upload video to YouTube"
    app_name: str = ""              # "YouTube", "Blender", etc.
    description: str = ""
    steps: List[DemoStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = 0.0
    times_executed: int = 0
    success_rate: float = 0.0       # 0-1
    tags: List[str] = field(default_factory=list)
    # Learned adaptations — element_label → alternative strategies
    adaptations: Dict[str, List[str]] = field(default_factory=dict)
    # Questions answered during training
    knowledge: Dict[str, str] = field(default_factory=dict)
    verified: bool = False

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["steps"] = [s.to_dict() if hasattr(s, 'to_dict') else s
                      for s in self.steps]
        return d


@dataclass
class DemoSession:
    """Active recording session state."""
    session_id: str
    app_name: str = ""
    task_description: str = ""
    events: List[InputEvent] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)  # paths
    analyzed_steps: List[DemoStep] = field(default_factory=list)
    started_at: float = 0.0
    stopped_at: float = 0.0
    recording: bool = False


# ---------------------------------------------------------------------------
# Demo Recorder — captures user demonstrations
# ---------------------------------------------------------------------------

class DemoRecorder:
    """Records mouse clicks, keyboard input, and screenshots.

    Uses pynput for global input hooks and mss for screenshots.
    Captures a screenshot at every meaningful event (click, key combo).
    """

    def __init__(self):
        self._session: Optional[DemoSession] = None
        self._mouse_listener = None
        self._keyboard_listener = None
        self._lock = threading.Lock()
        self._pressed_keys: set = set()
        self._text_buffer: str = ""
        self._text_buffer_start: float = 0.0
        self._screenshot_count: int = 0

    @property
    def is_recording(self) -> bool:
        return self._session is not None and self._session.recording

    def start(self, session: DemoSession) -> None:
        """Begin recording input events for a demo session."""
        from pynput import mouse, keyboard

        with self._lock:
            if self._session and self._session.recording:
                raise RuntimeError("Already recording")

            self._session = session
            self._session.recording = True
            self._session.started_at = time.time()
            self._pressed_keys.clear()
            self._text_buffer = ""
            self._screenshot_count = 0

            os.makedirs(_DEMO_DIR, exist_ok=True)
            session_dir = os.path.join(_DEMO_DIR, session.session_id)
            os.makedirs(session_dir, exist_ok=True)

            # Capture initial screenshot
            self._capture_screenshot("initial")

            # Start listeners
            self._mouse_listener = mouse.Listener(
                on_click=self._on_mouse_click,
                on_scroll=self._on_mouse_scroll,
            )
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )
            self._mouse_listener.start()
            self._keyboard_listener.start()

            _log.info("Recording started for session %s", session.session_id)

    def stop(self) -> Optional[DemoSession]:
        """Stop recording and return the completed session."""
        with self._lock:
            if not self._session or not self._session.recording:
                return None

            # Flush any pending text buffer
            self._flush_text_buffer()

            # Stop listeners
            if self._mouse_listener:
                self._mouse_listener.stop()
                self._mouse_listener = None
            if self._keyboard_listener:
                self._keyboard_listener.stop()
                self._keyboard_listener = None

            self._session.recording = False
            self._session.stopped_at = time.time()

            # Capture final screenshot
            self._capture_screenshot("final")

            session = self._session
            _log.info("Recording stopped: %d events, %d screenshots",
                      len(session.events), len(session.screenshots))
            return session

    def _capture_screenshot(self, label: str = "") -> str:
        """Capture and save a screenshot, return its path."""
        try:
            import mss
            from PIL import Image

            session_dir = os.path.join(_DEMO_DIR, self._session.session_id)
            idx = self._screenshot_count
            self._screenshot_count += 1
            name = f"ss_{idx:04d}"
            if label:
                name = f"ss_{idx:04d}_{label}"
            path = os.path.join(session_dir, f"{name}.png")

            with mss.mss() as sct:
                raw = sct.grab(sct.monitors[1])
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                # Downscale for storage efficiency (1280px wide)
                if img.width > 1280:
                    ratio = 1280 / img.width
                    img = img.resize(
                        (1280, int(img.height * ratio)), Image.LANCZOS
                    )
                img.save(path, optimize=True)

            self._session.screenshots.append(path)
            return path
        except Exception as e:
            _log.warning("Screenshot failed: %s", e)
            return ""

    def _add_event(self, event: InputEvent) -> None:
        """Add an event and capture a screenshot."""
        ss_path = self._capture_screenshot()
        event.screenshot_index = len(self._session.screenshots) - 1
        self._session.events.append(event)

    def _flush_text_buffer(self) -> None:
        """Flush accumulated text input as a single type_text event."""
        if self._text_buffer and self._session:
            event = InputEvent(
                timestamp=self._text_buffer_start,
                event_type="type_text",
                text=self._text_buffer,
            )
            self._add_event(event)
            self._text_buffer = ""

    # -- pynput callbacks --

    def _on_mouse_click(self, x, y, button, pressed):
        """Handle mouse click events."""
        if not pressed or not self._session or not self._session.recording:
            return

        # Flush text buffer before recording a click
        self._flush_text_buffer()

        btn_name = str(button).split(".")[-1]  # "left", "right", "middle"
        event = InputEvent(
            timestamp=time.time(),
            event_type="click" if btn_name == "left" else f"{btn_name}_click",
            x=int(x),
            y=int(y),
            button=btn_name,
            modifiers=list(self._pressed_keys),
        )
        self._add_event(event)

    def _on_mouse_scroll(self, x, y, dx, dy):
        """Handle scroll events."""
        if not self._session or not self._session.recording:
            return

        self._flush_text_buffer()
        event = InputEvent(
            timestamp=time.time(),
            event_type="scroll",
            x=int(x),
            y=int(y),
            scroll_delta=int(dy),
        )
        self._add_event(event)

    def _on_key_press(self, key):
        """Handle key press events."""
        if not self._session or not self._session.recording:
            return

        try:
            key_name = key.char if hasattr(key, 'char') and key.char else str(key).split(".")[-1]
        except Exception:
            key_name = str(key)

        # Track modifier keys
        if key_name in ("ctrl_l", "ctrl_r", "shift", "shift_l", "shift_r",
                         "alt_l", "alt_r", "cmd", "cmd_l", "cmd_r"):
            self._pressed_keys.add(key_name.split("_")[0])
            return

        # If modifiers are held, record as key_combo
        if self._pressed_keys:
            self._flush_text_buffer()
            event = InputEvent(
                timestamp=time.time(),
                event_type="key_combo",
                key=key_name,
                modifiers=list(self._pressed_keys),
            )
            self._add_event(event)
            return

        # Special keys (Enter, Tab, Escape, etc.)
        if not hasattr(key, 'char') or key.char is None:
            self._flush_text_buffer()
            event = InputEvent(
                timestamp=time.time(),
                event_type="key_press",
                key=key_name,
            )
            self._add_event(event)
            return

        # Regular character — accumulate into text buffer
        if not self._text_buffer:
            self._text_buffer_start = time.time()
        self._text_buffer += key.char

    def _on_key_release(self, key):
        """Track modifier key releases."""
        try:
            key_name = str(key).split(".")[-1]
        except Exception:
            return
        base = key_name.split("_")[0]
        self._pressed_keys.discard(base)


# ---------------------------------------------------------------------------
# Demo Analyzer — vision model understands what happened
# ---------------------------------------------------------------------------

class DemoAnalyzer:
    """Analyzes a recorded demo session using the vision model.

    For each event, it examines the before/after screenshots to understand:
      - What UI element was interacted with
      - What the intent was
      - What changed as a result
      - What's ambiguous (generates questions)
    """

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

    def analyze_session(self, session: DemoSession) -> List[DemoStep]:
        """Analyze all events in a session, producing enriched DemoSteps."""
        steps = []
        events = session.events

        for i, event in enumerate(events):
            step = DemoStep(
                index=i,
                event=event,
            )

            # Find before/after screenshots
            ss_idx = event.screenshot_index
            if ss_idx >= 0 and ss_idx < len(session.screenshots):
                step.screenshot_after = session.screenshots[ss_idx]
            if ss_idx > 0:
                step.screenshot_before = session.screenshots[ss_idx - 1]
            elif ss_idx == 0 and len(session.screenshots) > 0:
                step.screenshot_before = session.screenshots[0]

            # Vision analysis
            analysis = self._analyze_step(step, session.task_description)
            step.ui_element_description = analysis.get("element", "")
            step.action_description = analysis.get("action", "")
            step.intent = analysis.get("intent", "")
            step.element_type = analysis.get("element_type", "")
            step.element_label = analysis.get("label", "")
            step.confidence = analysis.get("confidence", 0.5)
            step.questions = analysis.get("questions", [])

            steps.append(step)

        session.analyzed_steps = steps
        return steps

    def _analyze_step(self, step: DemoStep, task_desc: str) -> Dict:
        """Use vision model to analyze a single step."""
        router = self._get_router()
        if not router:
            return self._fallback_analysis(step)

        # Build the analysis prompt
        event = step.event
        prompt = (
            f"I'm learning how to: {task_desc}\n\n"
            f"The user just performed this action:\n"
            f"  Type: {event.event_type}\n"
        )
        if event.event_type in ("click", "right_click", "double_click"):
            prompt += f"  Position: ({event.x}, {event.y})\n"
            prompt += f"  Button: {event.button}\n"
        elif event.event_type == "type_text":
            prompt += f"  Text typed: \"{event.text}\"\n"
        elif event.event_type == "key_combo":
            prompt += f"  Keys: {'+'.join(event.modifiers)}+{event.key}\n"
        elif event.event_type == "key_press":
            prompt += f"  Key: {event.key}\n"
        elif event.event_type == "scroll":
            prompt += f"  Scroll: {event.scroll_delta}\n"

        prompt += (
            "\nLooking at the screenshot, answer in JSON:\n"
            "{\n"
            '  "element": "description of the UI element interacted with",\n'
            '  "action": "what the user did (e.g. Clicked the Upload button)",\n'
            '  "intent": "why they did it (e.g. To upload a video file)",\n'
            '  "element_type": "button|text_field|menu|link|icon|tab|checkbox|other",\n'
            '  "label": "visible text label of the element",\n'
            '  "confidence": 0.0-1.0,\n'
            '  "questions": ["any questions about unclear UI elements"]\n'
            "}\n"
        )

        try:
            # Use vision model with the screenshot
            if step.screenshot_before and os.path.exists(step.screenshot_before):
                import base64
                with open(step.screenshot_before, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()

                response = router.query(
                    prompt,
                    images=[img_b64],
                    task="vision",
                    timeout=30,
                )
            else:
                response = router.query(prompt, task="reasoning", timeout=30)

            return self._parse_analysis(response)
        except Exception as e:
            _log.warning("Vision analysis failed for step %d: %s", step.index, e)
            return self._fallback_analysis(step)

    def _parse_analysis(self, response: str) -> Dict:
        """Parse JSON from vision model response."""
        import re
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, AttributeError):
            pass
        return {
            "element": response[:200] if response else "",
            "action": "",
            "intent": "",
            "element_type": "other",
            "label": "",
            "confidence": 0.3,
            "questions": [],
        }

    def _fallback_analysis(self, step: DemoStep) -> Dict:
        """Basic analysis without vision model."""
        event = step.event
        if event.event_type in ("click", "right_click"):
            return {
                "element": f"UI element at ({event.x}, {event.y})",
                "action": f"{event.event_type} at ({event.x}, {event.y})",
                "intent": "interact with element",
                "element_type": "other",
                "label": "",
                "confidence": 0.2,
                "questions": [f"What is the element at position ({event.x}, {event.y})?"],
            }
        elif event.event_type == "type_text":
            return {
                "element": "text input field",
                "action": f"Typed: \"{event.text}\"",
                "intent": "enter text",
                "element_type": "text_field",
                "label": "",
                "confidence": 0.5,
                "questions": [],
            }
        elif event.event_type == "key_combo":
            combo = "+".join(event.modifiers) + "+" + event.key
            return {
                "element": "keyboard shortcut",
                "action": f"Pressed {combo}",
                "intent": f"keyboard shortcut: {combo}",
                "element_type": "other",
                "label": combo,
                "confidence": 0.6,
                "questions": [f"What does {combo} do in this application?"],
            }
        return {
            "element": "unknown",
            "action": event.event_type,
            "intent": "",
            "element_type": "other",
            "label": "",
            "confidence": 0.1,
            "questions": ["What happened in this step?"],
        }


# ---------------------------------------------------------------------------
# Demo Player — replays the learned sequence
# ---------------------------------------------------------------------------

class DemoPlayer:
    """Replays a learned demonstration using the desktop controller.

    Uses two strategies:
      1. Vision-guided: Screenshot → find the element → click it
         (adapts to UI changes)
      2. Coordinate fallback: Use recorded (x,y) if vision can't find element
    """

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

    def replay_recipe(self, recipe: Recipe,
                      on_step: Optional[Callable] = None) -> List[Dict]:
        """Replay all steps of a recipe.

        Args:
            recipe: The recipe to replay.
            on_step: Callback(step_index, step, status) for UI updates.

        Returns:
            List of step results: [{"index": i, "ok": bool, "method": "vision"|"coords"}]
        """
        import pyautogui

        results = []
        for step in recipe.steps:
            if isinstance(step, dict):
                event_data = step.get("event", step)
                event = InputEvent(**{k: v for k, v in event_data.items()
                                      if k in InputEvent.__dataclass_fields__})
                label = step.get("element_label", "")
                desc = step.get("action_description", "")
            else:
                event = step.event
                label = step.element_label
                desc = step.action_description

            step_idx = step["index"] if isinstance(step, dict) else step.index

            if on_step:
                on_step(step_idx, step, "executing")

            ok, method = self._execute_event(event, label)
            results.append({
                "index": step_idx,
                "ok": ok,
                "method": method,
                "description": desc,
            })

            if on_step:
                on_step(step_idx, step, "done" if ok else "failed")

            # Brief pause between actions for UI to respond
            time.sleep(0.3)

        return results

    def _execute_event(self, event: InputEvent, label: str = "") -> tuple:
        """Execute a single event.

        Returns (success: bool, method: str).
        """
        import pyautogui

        try:
            if event.event_type in ("click", "left_click"):
                # TODO: vision-guided click matching using label
                pyautogui.click(event.x, event.y)
                return True, "coords"

            elif event.event_type == "right_click":
                pyautogui.rightClick(event.x, event.y)
                return True, "coords"

            elif event.event_type == "double_click":
                pyautogui.doubleClick(event.x, event.y)
                return True, "coords"

            elif event.event_type == "type_text":
                pyautogui.write(event.text, interval=0.02)
                return True, "replay"

            elif event.event_type == "key_press":
                pyautogui.press(event.key)
                return True, "replay"

            elif event.event_type == "key_combo":
                keys = event.modifiers + [event.key]
                pyautogui.hotkey(*keys)
                return True, "replay"

            elif event.event_type == "scroll":
                pyautogui.scroll(event.scroll_delta, event.x, event.y)
                return True, "replay"

            else:
                _log.warning("Unknown event type: %s", event.event_type)
                return False, "unknown"

        except Exception as e:
            _log.error("Replay failed for %s: %s", event.event_type, e)
            return False, "error"


# ---------------------------------------------------------------------------
# Question Engine — asks smart questions about unclear UI
# ---------------------------------------------------------------------------

class QuestionEngine:
    """Manages Onyx's questions about a UI it's trying to learn.

    Key insight from the user's vision: answering one question might
    resolve multiple other queued questions. The engine tracks question
    dependencies and prunes resolved ones.
    """

    def __init__(self):
        self._questions: List[Dict] = []  # {q, step_idx, category, resolved, answer}
        self._knowledge: Dict[str, str] = {}  # learned facts

    def collect_questions(self, steps: List[DemoStep]) -> List[Dict]:
        """Gather all questions from analyzed steps, deduplicate, prioritize."""
        self._questions.clear()
        seen = set()

        for step in steps:
            qs = step.questions if hasattr(step, 'questions') else []
            if isinstance(step, dict):
                qs = step.get("questions", [])
                step_idx = step.get("index", 0)
                conf = step.get("confidence", 0.5)
            else:
                step_idx = step.index
                conf = step.confidence

            for q in qs:
                q_normalized = q.strip().lower()
                if q_normalized in seen:
                    continue
                seen.add(q_normalized)
                self._questions.append({
                    "question": q,
                    "step_index": step_idx,
                    "category": self._categorize(q),
                    "confidence": conf,
                    "resolved": False,
                    "answer": "",
                })

        # Sort: lowest confidence first (most confused → ask first)
        self._questions.sort(key=lambda x: x["confidence"])
        return self._questions

    def answer_question(self, question_index: int, answer: str) -> List[int]:
        """Record an answer and check if it resolves other questions.

        Returns list of indices of additionally resolved questions.
        """
        if question_index >= len(self._questions):
            return []

        q = self._questions[question_index]
        q["resolved"] = True
        q["answer"] = answer

        # Store as knowledge
        self._knowledge[q["question"]] = answer

        # Check if this answer resolves related questions
        resolved_others = []
        answer_lower = answer.lower()
        q_category = q["category"]

        for i, other in enumerate(self._questions):
            if i == question_index or other["resolved"]:
                continue
            # Same category questions might be resolved
            if other["category"] == q_category:
                other_q_lower = other["question"].lower()
                # If the answer mentions keywords from the other question
                other_keywords = set(other_q_lower.split()) - {
                    "what", "is", "the", "a", "an", "this", "that", "does",
                    "how", "why", "where", "do", "for", "in", "at", "of",
                }
                if any(kw in answer_lower for kw in other_keywords if len(kw) > 3):
                    other["resolved"] = True
                    other["answer"] = f"(Inferred from: {q['question']}) {answer}"
                    resolved_others.append(i)

        return resolved_others

    def get_pending_questions(self) -> List[Dict]:
        """Return unresolved questions."""
        return [q for q in self._questions if not q["resolved"]]

    def get_knowledge(self) -> Dict[str, str]:
        """Return all learned facts from Q&A."""
        return dict(self._knowledge)

    @staticmethod
    def _categorize(question: str) -> str:
        """Categorize a question for dependency tracking."""
        q_lower = question.lower()
        if any(w in q_lower for w in ("button", "click", "icon", "tab")):
            return "ui_element"
        if any(w in q_lower for w in ("shortcut", "key", "combo", "hotkey")):
            return "keyboard"
        if any(w in q_lower for w in ("menu", "dropdown", "option")):
            return "navigation"
        if any(w in q_lower for w in ("field", "input", "text", "type")):
            return "input"
        return "general"


# ---------------------------------------------------------------------------
# Recipe Store — persists learned workflows
# ---------------------------------------------------------------------------

class RecipeStore:
    """Manages saved recipes (learned workflows)."""

    def __init__(self):
        os.makedirs(_RECIPE_DIR, exist_ok=True)

    def save(self, recipe: Recipe) -> str:
        """Save a recipe to disk. Returns the file path."""
        recipe.updated_at = time.time()
        path = os.path.join(_RECIPE_DIR, f"{recipe.id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(recipe.to_dict(), f, indent=2, ensure_ascii=False)
        _log.info("Saved recipe: %s (%s)", recipe.name, recipe.id)
        return path

    def load(self, recipe_id: str) -> Optional[Recipe]:
        """Load a recipe by ID."""
        path = os.path.join(_RECIPE_DIR, f"{recipe_id}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Recipe(**{k: v for k, v in data.items()
                            if k in Recipe.__dataclass_fields__})
        except Exception as e:
            _log.error("Failed to load recipe %s: %s", recipe_id, e)
            return None

    def list_recipes(self, app_name: str = "",
                     tag: str = "") -> List[Dict]:
        """List all saved recipes, optionally filtered."""
        recipes = []
        for fname in os.listdir(_RECIPE_DIR):
            if not fname.endswith(".json"):
                continue
            try:
                path = os.path.join(_RECIPE_DIR, fname)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if app_name and data.get("app_name", "").lower() != app_name.lower():
                    continue
                if tag and tag not in data.get("tags", []):
                    continue
                recipes.append({
                    "id": data.get("id", ""),
                    "name": data.get("name", ""),
                    "app_name": data.get("app_name", ""),
                    "description": data.get("description", ""),
                    "steps": len(data.get("steps", [])),
                    "times_executed": data.get("times_executed", 0),
                    "success_rate": data.get("success_rate", 0.0),
                    "verified": data.get("verified", False),
                    "tags": data.get("tags", []),
                })
            except Exception:
                continue
        return recipes

    def delete(self, recipe_id: str) -> bool:
        """Delete a recipe."""
        path = os.path.join(_RECIPE_DIR, f"{recipe_id}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False


# ---------------------------------------------------------------------------
# TeachMe Component — the unified OnyxComponent interface
# ---------------------------------------------------------------------------

class TeachMeComponent(OnyxComponent):
    """Imitation learning component — Onyx learns by watching you.

    Actions:
        start_recording   — Begin watching user's demonstration
        stop_recording    — Stop recording, analyze the demo
        analyze           — Vision-analyze a recorded session
        replay            — Replay the learned sequence
        verify_step       — User confirms if a step was correct
        ask_questions     — Get Onyx's questions about the UI
        answer_question   — Answer one of Onyx's questions
        save_recipe       — Save the learned workflow
        list_recipes      — List all saved recipes
        load_recipe       — Load a specific recipe
        run_recipe        — Execute a saved recipe
        delete_recipe     — Delete a saved recipe
    """

    @property
    def name(self) -> str:
        return "teach_me"

    @property
    def display_name(self) -> str:
        return "TeachMe"

    @property
    def description(self) -> str:
        return "Learn new skills by watching user demonstrations"

    @property
    def category(self) -> str:
        return "learning"

    def __init__(self):
        super().__init__()
        self._recorder = DemoRecorder()
        self._analyzer = DemoAnalyzer()
        self._player = DemoPlayer()
        self._questions = QuestionEngine()
        self._recipes = RecipeStore()
        self._current_session: Optional[DemoSession] = None
        self._current_recipe: Optional[Recipe] = None

    def get_actions(self) -> List[ActionDescriptor]:
        return [
            ActionDescriptor(
                name="start_recording",
                description="Start watching the user perform a task",
                params=["app_name", "task_description"],
                required_params=["task_description"],
                estimated_duration="seconds",
            ),
            ActionDescriptor(
                name="stop_recording",
                description="Stop recording and analyze the demonstration",
                estimated_duration="seconds",
            ),
            ActionDescriptor(
                name="analyze",
                description="Analyze a recorded session with the vision model",
                estimated_duration="minutes",
            ),
            ActionDescriptor(
                name="replay",
                description="Replay the learned sequence for user verification",
                estimated_duration="minutes",
            ),
            ActionDescriptor(
                name="verify_step",
                description="User confirms if a replayed step was correct",
                params=["step_index", "correct", "correction"],
                required_params=["step_index", "correct"],
            ),
            ActionDescriptor(
                name="ask_questions",
                description="Get Onyx's questions about the UI",
            ),
            ActionDescriptor(
                name="answer_question",
                description="Answer one of Onyx's questions about the UI",
                params=["question_index", "answer"],
                required_params=["question_index", "answer"],
            ),
            ActionDescriptor(
                name="save_recipe",
                description="Save the learned workflow as a reusable recipe",
                params=["name", "tags"],
                required_params=["name"],
            ),
            ActionDescriptor(
                name="list_recipes",
                description="List all saved recipes",
                params=["app_name", "tag"],
            ),
            ActionDescriptor(
                name="load_recipe",
                description="Load a specific recipe by ID",
                params=["recipe_id"],
                required_params=["recipe_id"],
            ),
            ActionDescriptor(
                name="run_recipe",
                description="Execute a saved recipe",
                params=["recipe_id"],
                required_params=["recipe_id"],
            ),
            ActionDescriptor(
                name="delete_recipe",
                description="Delete a saved recipe",
                params=["recipe_id"],
                required_params=["recipe_id"],
            ),
        ]

    def execute(self, action: str, params: Optional[Dict] = None) -> ComponentResult:
        """Execute a TeachMe action."""
        params = params or {}

        if action == "start_recording":
            return self._start_recording(params)
        elif action == "stop_recording":
            return self._stop_recording()
        elif action == "analyze":
            return self._analyze()
        elif action == "replay":
            return self._replay()
        elif action == "verify_step":
            return self._verify_step(params)
        elif action == "ask_questions":
            return self._ask_questions()
        elif action == "answer_question":
            return self._answer_question(params)
        elif action == "save_recipe":
            return self._save_recipe(params)
        elif action == "list_recipes":
            return self._list_recipes(params)
        elif action == "load_recipe":
            return self._load_recipe(params)
        elif action == "run_recipe":
            return self._run_recipe(params)
        elif action == "delete_recipe":
            return self._delete_recipe(params)
        else:
            return ComponentResult(
                status="failed",
                error=f"Unknown action: {action}",
            )

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    def _start_recording(self, params: Dict) -> ComponentResult:
        """Start a new recording session."""
        import hashlib

        if self._recorder.is_recording:
            return ComponentResult(
                status="failed",
                error="Already recording. Stop the current session first.",
            )

        task_desc = params.get("task_description", "")
        if not task_desc:
            return ComponentResult(
                status="failed",
                error="task_description is required",
            )

        session_id = hashlib.md5(
            f"{task_desc}:{time.time()}".encode()
        ).hexdigest()[:12]

        self._current_session = DemoSession(
            session_id=session_id,
            app_name=params.get("app_name", ""),
            task_description=task_desc,
        )

        self._recorder.start(self._current_session)

        return ComponentResult(
            status="done",
            output={
                "session_id": session_id,
                "message": "Recording started. Perform the task now. "
                           "Say 'stop recording' when done.",
            },
            summary=f"I'm watching! Go ahead and show me how to: {task_desc}",
        )

    def _stop_recording(self) -> ComponentResult:
        """Stop recording and return session summary."""
        session = self._recorder.stop()
        if not session:
            return ComponentResult(
                status="failed",
                error="No active recording to stop.",
            )

        self._current_session = session
        duration = session.stopped_at - session.started_at

        return ComponentResult(
            status="done",
            output={
                "session_id": session.session_id,
                "events": len(session.events),
                "screenshots": len(session.screenshots),
                "duration": round(duration, 1),
            },
            summary=(f"Got it! Recorded {len(session.events)} actions "
                     f"in {duration:.0f}s with {len(session.screenshots)} "
                     f"screenshots. Ready to analyze."),
        )

    def _analyze(self) -> ComponentResult:
        """Analyze the current session with vision model."""
        if not self._current_session:
            return ComponentResult(
                status="failed",
                error="No recorded session to analyze. Record first.",
            )

        steps = self._analyzer.analyze_session(self._current_session)

        # Build a preliminary recipe
        import hashlib
        recipe_id = hashlib.md5(
            f"{self._current_session.session_id}:{time.time()}".encode()
        ).hexdigest()[:10]

        self._current_recipe = Recipe(
            id=recipe_id,
            name=self._current_session.task_description,
            app_name=self._current_session.app_name,
            description=f"Learned from demo: {self._current_session.task_description}",
            steps=steps,
        )

        # Collect questions
        questions = self._questions.collect_questions(steps)

        # Build step summaries
        step_summaries = []
        for s in steps:
            step_summaries.append({
                "index": s.index,
                "action": s.action_description,
                "intent": s.intent,
                "element": s.ui_element_description,
                "confidence": s.confidence,
            })

        return ComponentResult(
            status="done",
            output={
                "steps": step_summaries,
                "total_steps": len(steps),
                "questions_count": len(questions),
                "avg_confidence": (sum(s.confidence for s in steps) / len(steps)
                                   if steps else 0),
            },
            summary=(f"Analyzed {len(steps)} steps. I'm {sum(s.confidence for s in steps) / max(len(steps), 1):.0%} "
                     f"confident overall. I have {len(questions)} questions "
                     f"about the UI. Ready to replay or answer questions first."),
        )

    def _replay(self) -> ComponentResult:
        """Replay the current recipe for user verification."""
        if not self._current_recipe:
            return ComponentResult(
                status="failed",
                error="No analyzed demo to replay. Analyze first.",
            )

        results = self._player.replay_recipe(self._current_recipe)
        ok_count = sum(1 for r in results if r["ok"])
        total = len(results)

        return ComponentResult(
            status="done" if ok_count == total else "partial",
            output={
                "steps_executed": total,
                "steps_ok": ok_count,
                "step_results": results,
            },
            summary=(f"Replayed {total} steps. {ok_count}/{total} executed successfully. "
                     f"Did I do it right? Tell me which steps were correct."),
        )

    def _verify_step(self, params: Dict) -> ComponentResult:
        """User confirms if a specific step was correct."""
        step_idx = params.get("step_index", -1)
        correct = params.get("correct", False)
        correction = params.get("correction", "")

        if not self._current_recipe:
            return ComponentResult(status="failed", error="No active recipe")

        steps = self._current_recipe.steps
        if step_idx < 0 or step_idx >= len(steps):
            return ComponentResult(
                status="failed",
                error=f"Invalid step index: {step_idx}",
            )

        step = steps[step_idx]
        if isinstance(step, DemoStep):
            step.verified = True
            step.correct = correct
            step.user_correction = correction
        elif isinstance(step, dict):
            step["verified"] = True
            step["correct"] = correct
            step["user_correction"] = correction

        verified_count = sum(
            1 for s in steps
            if (s.verified if isinstance(s, DemoStep) else s.get("verified", False))
        )
        correct_count = sum(
            1 for s in steps
            if (s.correct if isinstance(s, DemoStep)
                else s.get("correct", False))
        )

        return ComponentResult(
            status="done",
            output={
                "step_index": step_idx,
                "correct": correct,
                "verified_count": verified_count,
                "correct_count": correct_count,
                "total": len(steps),
            },
            summary=(f"Step {step_idx} marked as {'correct' if correct else 'incorrect'}. "
                     f"{verified_count}/{len(steps)} verified, "
                     f"{correct_count} correct so far."),
        )

    def _ask_questions(self) -> ComponentResult:
        """Get Onyx's questions about the UI."""
        pending = self._questions.get_pending_questions()
        if not pending:
            return ComponentResult(
                status="done",
                output={"questions": [], "count": 0},
                summary="I don't have any questions! I think I understand the task.",
            )

        return ComponentResult(
            status="done",
            output={
                "questions": pending,
                "count": len(pending),
            },
            summary=(f"I have {len(pending)} question{'s' if len(pending) != 1 else ''}:\n"
                     + "\n".join(f"  {i+1}. {q['question']}"
                                for i, q in enumerate(pending))),
        )

    def _answer_question(self, params: Dict) -> ComponentResult:
        """Answer one of Onyx's questions."""
        q_idx = params.get("question_index", 0)
        answer = params.get("answer", "")

        if not answer:
            return ComponentResult(status="failed", error="answer is required")

        resolved = self._questions.answer_question(q_idx, answer)
        pending = self._questions.get_pending_questions()

        summary = f"Thanks! That answers question {q_idx + 1}."
        if resolved:
            summary += (f" That also answered {len(resolved)} other "
                        f"question{'s' if len(resolved) != 1 else ''} I had!")
        if pending:
            summary += f" I still have {len(pending)} more."
        else:
            summary += " No more questions — I think I've got it!"

        return ComponentResult(
            status="done",
            output={
                "resolved_additionally": resolved,
                "remaining_questions": len(pending),
                "knowledge": self._questions.get_knowledge(),
            },
            summary=summary,
        )

    def _save_recipe(self, params: Dict) -> ComponentResult:
        """Save the current recipe."""
        if not self._current_recipe:
            return ComponentResult(status="failed", error="No recipe to save")

        name = params.get("name", self._current_recipe.name)
        self._current_recipe.name = name
        self._current_recipe.tags = params.get("tags", [])
        self._current_recipe.knowledge = self._questions.get_knowledge()

        # Check if all steps are verified
        steps = self._current_recipe.steps
        verified = all(
            (s.verified if isinstance(s, DemoStep) else s.get("verified", False))
            for s in steps
        )
        self._current_recipe.verified = verified

        path = self._recipes.save(self._current_recipe)

        return ComponentResult(
            status="done",
            output={
                "recipe_id": self._current_recipe.id,
                "name": name,
                "path": path,
                "verified": verified,
            },
            summary=(f"Recipe '{name}' saved! "
                     f"{'Fully verified.' if verified else 'Some steps not verified yet.'}"),
        )

    def _list_recipes(self, params: Dict) -> ComponentResult:
        """List saved recipes."""
        app_name = params.get("app_name", "")
        tag = params.get("tag", "")
        recipes = self._recipes.list_recipes(app_name, tag)

        return ComponentResult(
            status="done",
            output={"recipes": recipes, "count": len(recipes)},
            summary=(f"I know {len(recipes)} recipe{'s' if len(recipes) != 1 else ''}."
                     if recipes else "No recipes saved yet."),
        )

    def _load_recipe(self, params: Dict) -> ComponentResult:
        """Load a recipe by ID."""
        recipe_id = params.get("recipe_id", "")
        recipe = self._recipes.load(recipe_id)
        if not recipe:
            return ComponentResult(
                status="failed",
                error=f"Recipe '{recipe_id}' not found",
            )

        self._current_recipe = recipe
        return ComponentResult(
            status="done",
            output={
                "recipe_id": recipe.id,
                "name": recipe.name,
                "steps": len(recipe.steps),
                "verified": recipe.verified,
            },
            summary=f"Loaded recipe '{recipe.name}' ({len(recipe.steps)} steps).",
        )

    def _run_recipe(self, params: Dict) -> ComponentResult:
        """Execute a saved recipe."""
        recipe_id = params.get("recipe_id", "")
        recipe = self._recipes.load(recipe_id)
        if not recipe:
            return ComponentResult(
                status="failed",
                error=f"Recipe '{recipe_id}' not found",
            )

        results = self._player.replay_recipe(recipe)
        ok_count = sum(1 for r in results if r["ok"])
        total = len(results)

        # Update stats
        recipe.times_executed += 1
        total_runs = recipe.times_executed
        prev_rate = recipe.success_rate
        recipe.success_rate = (
            (prev_rate * (total_runs - 1) + (ok_count / max(total, 1))) / total_runs
        )
        self._recipes.save(recipe)

        return ComponentResult(
            status="done" if ok_count == total else "partial",
            output={
                "steps_executed": total,
                "steps_ok": ok_count,
                "step_results": results,
                "total_runs": total_runs,
                "success_rate": recipe.success_rate,
            },
            summary=(f"Executed recipe '{recipe.name}': {ok_count}/{total} steps OK. "
                     f"Lifetime success rate: {recipe.success_rate:.0%}"),
        )

    def _delete_recipe(self, params: Dict) -> ComponentResult:
        """Delete a recipe."""
        recipe_id = params.get("recipe_id", "")
        if self._recipes.delete(recipe_id):
            return ComponentResult(
                status="done",
                summary=f"Recipe '{recipe_id}' deleted.",
            )
        return ComponentResult(
            status="failed",
            error=f"Recipe '{recipe_id}' not found",
        )
