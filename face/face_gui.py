"""OnyxKraken Face — scalable animated face canvas widget.

A reusable tk.Canvas that renders an animated robot face with:
  - Eyes that blink and look around naturally
  - Mouth that animates phoneme shapes during speech
  - Dark theme with neon cyan accents
  - Idle breathing/pulse animation
  - CRT scan line overlay
  - Scale-factor rendering — works at any canvas size

Usage as widget:
    canvas = FaceCanvas(parent_frame)
    canvas.pack(fill="both", expand=True)
    canvas.speak("Hello world")

Usage standalone:
    python face/face_gui.py
"""

import json
import logging
import math
import os
import random
import time
import threading
import tkinter as tk
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from face.render_backend import PygameRenderer, TkCanvasRenderer

_log = logging.getLogger("face.gui")


# ---------------------------------------------------------------------------
# Load face spec — supports face packs (merged spec) or base fallback
# ---------------------------------------------------------------------------

def _load_face_spec() -> dict:
    """Load the face spec, merging any active face pack overrides."""
    try:
        from core.face_packs import pack_manager
        pack_manager.init()
        return pack_manager.get_merged_spec()
    except Exception:
        # Fallback: load base spec directly
        spec_path = os.path.join(os.path.dirname(__file__), "face_spec.json")
        with open(spec_path, "r", encoding="utf-8") as f:
            return json.load(f)

_SPEC = _load_face_spec()

# ---------------------------------------------------------------------------
# Design reference size (all coordinates authored at this resolution)
# ---------------------------------------------------------------------------

REF_W = _SPEC["reference"]["width"]
REF_H = _SPEC["reference"]["height"]

# ---------------------------------------------------------------------------
# Colors (from spec)
# ---------------------------------------------------------------------------

BG_COLOR = _SPEC["colors"]["bg"]
FACE_COLOR = _SPEC["colors"]["face"]
FACE_BORDER = _SPEC["colors"]["face_border"]
EYE_SCLERA = _SPEC["colors"]["eye_sclera"]
EYE_PUPIL = _SPEC["colors"]["eye_pupil"]
EYE_GLOW_INNER = _SPEC["colors"]["eye_glow_inner"]
EYE_GLOW_OUTER = _SPEC["colors"]["eye_glow_outer"]
EYE_HIGHLIGHT = _SPEC["colors"]["eye_highlight"]
MOUTH_INTERIOR = _SPEC["colors"]["mouth_interior"]
ACCENT_BRIGHT = _SPEC["colors"]["accent_bright"]
ACCENT_MID = _SPEC["colors"]["accent_mid"]
ACCENT_DIM = _SPEC["colors"]["accent_dim"]
ACCENT_VDIM = _SPEC["colors"]["accent_vdim"]

# Emotion-reactive accent color map
_EMOTION_ACCENT: dict[str, str] = _SPEC["emotion_accents"]

# Customization catalogs (from spec)
_THEMES: dict[str, dict] = _SPEC.get("themes", {})
_EYE_STYLES: dict[str, dict] = _SPEC.get("eye_styles", {})
_FACE_SHAPES: dict[str, dict] = _SPEC.get("face_shapes", {})
_ACCESSORIES: dict[str, dict] = _SPEC.get("accessories", {})

FPS = _SPEC["animation"]["fps"]
FRAME_MS = int(1000 / FPS)

# ---------------------------------------------------------------------------
# Design-space constants (at REF_W x REF_H, from spec)
# ---------------------------------------------------------------------------

_EYE_WIDTH = _SPEC["geometry"]["eye_width"]
_EYE_HEIGHT = _SPEC["geometry"]["eye_height"]
_EYE_SPACING = _SPEC["geometry"]["eye_spacing"]
_EYE_Y = _SPEC["geometry"]["eye_y"]
_PUPIL_RADIUS = _SPEC["geometry"]["pupil_radius"]
_PUPIL_MAX_OX = _SPEC["geometry"]["pupil_max_ox"]
_PUPIL_MAX_OY = _SPEC["geometry"]["pupil_max_oy"]
_MOUTH_Y = _SPEC["geometry"]["mouth_y"]
_MOUTH_WIDTH = _SPEC["geometry"]["mouth_width"]
_MOUTH_HEIGHT = _SPEC["geometry"]["mouth_height"]

BLINK_INTERVAL_MIN = _SPEC["animation"]["blink_interval_min"]
BLINK_INTERVAL_MAX = _SPEC["animation"]["blink_interval_max"]
BLINK_DURATION = _SPEC["animation"]["blink_duration"]
DOUBLE_BLINK_CHANCE = _SPEC["animation"]["double_blink_chance"]
GAZE_CHANGE_MIN = _SPEC["animation"]["gaze_change_min"]
GAZE_CHANGE_MAX = _SPEC["animation"]["gaze_change_max"]
GAZE_SPEED = _SPEC["animation"]["gaze_speed"]


# ---------------------------------------------------------------------------
# Phoneme shapes (from spec)
# ---------------------------------------------------------------------------

class Phoneme(Enum):
    """Mouth shapes for speech animation."""
    CLOSED = "closed"
    SMALL = "small"
    MEDIUM = "medium"
    WIDE = "wide"
    ROUND = "round"
    TEETH = "teeth"


_PHONEME_BY_NAME = {p.value: p for p in Phoneme}
_CHAR_TO_PHONEME = {
    ch: _PHONEME_BY_NAME[name]
    for ch, name in _SPEC["phonemes"]["char_map"].items()
}


def text_to_phonemes(text: str, chars_per_sec: float = 12.0) -> list[tuple[float, Phoneme]]:
    """Convert text to a timed phoneme sequence."""
    result = []
    t = 0.0
    dt = 1.0 / chars_per_sec
    for ch in text.lower():
        result.append((t, _CHAR_TO_PHONEME.get(ch, Phoneme.SMALL)))
        t += dt
    result.append((t, Phoneme.CLOSED))
    return result


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,b)):02x}"


def _lerp_color(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )


# ---------------------------------------------------------------------------
# Animation state
# ---------------------------------------------------------------------------

@dataclass
class EyeState:
    gaze_target_x: float = 0.0
    gaze_target_y: float = 0.0
    gaze_x: float = 0.0
    gaze_y: float = 0.0
    blink_progress: float = 0.0
    is_blinking: bool = False
    blink_timer: float = 0.0
    next_blink: float = 3.0
    double_blink_pending: bool = False
    next_gaze_change: float = 1.5
    squint: float = 0.0


@dataclass
class MouthState:
    current_phoneme: Phoneme = Phoneme.CLOSED
    target_phoneme: Phoneme = Phoneme.CLOSED
    open_amount: float = 0.0
    width_factor: float = 1.0
    phoneme_sequence: list = field(default_factory=list)
    speech_start_time: float = 0.0
    is_speaking: bool = False
    phoneme_index: int = 0


@dataclass
class EmotionState:
    """Blendable emotion parameters that drive eye/brow/mouth expression."""
    # Current interpolated values (driven by _update_emotion)
    squint: float = 0.0        # >0 narrows eyes, <0 widens
    brow_raise: float = 0.0    # >0 raises brows (surprise/curious), <0 furrows (angry/confused)
    eye_widen: float = 0.0     # additional eye height multiplier
    mouth_curve: float = 0.0   # >0 smile, <0 frown
    pupil_size: float = 1.0    # pupil scale factor
    gaze_speed: float = 1.0    # how actively eyes move
    blink_rate: float = 1.0    # blink frequency multiplier
    intensity: float = 0.0     # overall expression intensity (0=neutral)
    # Targets (set by set_emotion, interpolated toward)
    _target_squint: float = 0.0
    _target_brow_raise: float = 0.0
    _target_eye_widen: float = 0.0
    _target_mouth_curve: float = 0.0
    _target_pupil_size: float = 1.0
    _target_gaze_speed: float = 1.0
    _target_blink_rate: float = 1.0
    _target_intensity: float = 0.0


# ---------------------------------------------------------------------------
# Emotion presets
# ---------------------------------------------------------------------------

_EMOTION_PRESETS: dict[str, dict] = _SPEC["emotion_presets"]


# ---------------------------------------------------------------------------
# FaceCanvas — the reusable widget
# ---------------------------------------------------------------------------

class FaceCanvas(tk.Canvas):
    """Animated face canvas that scales to any size.

    All drawing is done in a 400x360 design space, then transformed
    via a uniform scale factor + centering offset at render time.
    """

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("bg", BG_COLOR)
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(parent, **kwargs)

        self.eye_state = EyeState()
        self.mouth_state = MouthState()
        self.emotion = EmotionState()
        self._last_time = time.time()
        self._start_time = time.time()
        self._running = True
        self._pulse = 0.0
        self._status_text = ""
        self._current_emotion_name = "neutral"

        # Enhanced face systems
        try:
            from face.enhancements import (
                EmotionTransitionManager,
                EyeTracker,
                AttentionSystem,
                IdleBehaviorEngine,
                GestureSystem,
                ContextualGestureEngine,
            )
            self._transition_mgr = EmotionTransitionManager(transition_duration=0.3)
            self._eye_tracker = EyeTracker()
            self._attention = AttentionSystem()
            self._idle_behavior = IdleBehaviorEngine()
            self._gesture_system = GestureSystem()
            self._context_gestures = ContextualGestureEngine(self._gesture_system)
            self._enhancements_enabled = True
        except ImportError:
            # Enhancements not available, use legacy behavior
            self._enhancements_enabled = False

        # Customization state (overridable colors)
        self._theme_accent_bright = ACCENT_BRIGHT
        self._theme_accent_mid = ACCENT_MID
        self._theme_accent_dim = ACCENT_DIM
        self._theme_accent_vdim = ACCENT_VDIM
        self._theme_eye_pupil = EYE_PUPIL
        self._theme_eye_glow_inner = EYE_GLOW_INNER
        self._theme_eye_glow_outer = EYE_GLOW_OUTER
        self._theme_face_border = FACE_BORDER
        self._eye_style = "default"
        self._face_shape = "default"
        self._accessory = "none"
        self._scan_lines = True
        self._draw_plugins = []  # instance-level plugin list

        # Geometry state (overridable via apply_geometry)
        self._geo_eye_width = _EYE_WIDTH
        self._geo_eye_height = _EYE_HEIGHT
        self._geo_eye_spacing = _EYE_SPACING
        self._geo_eye_y = _EYE_Y
        self._geo_pupil_radius = _PUPIL_RADIUS
        self._geo_pupil_max_ox = _PUPIL_MAX_OX
        self._geo_pupil_max_oy = _PUPIL_MAX_OY
        self._geo_mouth_y = _MOUTH_Y
        self._geo_mouth_width = _MOUTH_WIDTH
        self._geo_mouth_height = _MOUTH_HEIGHT

        # Animation state (overridable via apply_animation)
        self._anim_blink_min = BLINK_INTERVAL_MIN
        self._anim_blink_max = BLINK_INTERVAL_MAX
        self._anim_blink_duration = BLINK_DURATION
        self._anim_double_blink_chance = DOUBLE_BLINK_CHANCE
        self._anim_gaze_change_min = GAZE_CHANGE_MIN
        self._anim_gaze_change_max = GAZE_CHANGE_MAX
        self._anim_gaze_speed = GAZE_SPEED

        # Render backend (Tkinter by default, Pygame when available)
        self._use_pygame = False
        self._r = None
        self._viewport = None

        # Load customization from settings
        self._load_customization()

        # Idle behavior state
        self._idle_active = True           # whether idle behaviors run
        self._idle_micro_timer = 0.0       # countdown to next micro-expression
        self._idle_next_micro = random.uniform(4.0, 10.0)
        self._idle_gaze_drift_timer = 0.0  # slower wide gaze drifts when idle
        self._idle_next_drift = random.uniform(5.0, 12.0)
        self._idle_micro_active = False    # currently showing a micro-expression
        self._idle_micro_revert = 0.0      # when to revert micro-expression

        # Work-state micro-expression state
        self._work_micro_timer = 0.0
        self._work_next_micro = random.uniform(2.0, 5.0)

        # Scale-factor state (recomputed each frame)
        self._s = 1.0
        self._ox = 0.0
        self._oy = 0.0

        self._tick()

    # ------------------------------------------------------------------
    # Scale helpers — convert design coords to canvas coords
    # ------------------------------------------------------------------

    def _sx(self, x: float) -> float:
        return self._ox + x * self._s

    def _sy(self, y: float) -> float:
        return self._oy + y * self._s

    def _ss(self, v: float) -> float:
        return v * self._s

    def _recompute_scale(self):
        if self._use_pygame and self._r:
            cw, ch = self._r.get_size()
        else:
            cw = self.winfo_width()
            ch = self.winfo_height()
        if cw < 2 or ch < 2:
            return
        sx = cw / REF_W
        sy = ch / REF_H
        self._s = min(sx, sy)
        self._ox = (cw - REF_W * self._s) / 2
        self._oy = (ch - REF_H * self._s) / 2

    # ------------------------------------------------------------------
    # Customization
    # ------------------------------------------------------------------

    def _load_customization(self):
        """Load face customization from persistent settings."""
        try:
            from face.settings import load_settings
            s = load_settings()
            self.apply_theme(s.get("face_theme", "cyan"))
            self._eye_style = s.get("eye_style", "default")
            self._face_shape = s.get("face_shape", "default")
            self._accessory = s.get("accessory", "none")
            self._scan_lines = s.get("scan_lines", True)
            # Geometry overrides
            geo = s.get("geometry", {})
            if geo:
                self.apply_geometry(**geo)
            # Animation overrides
            anim = s.get("animation", {})
            if anim:
                self.apply_animation(**anim)
            # Custom accent color (overrides theme accent)
            custom_accent = s.get("custom_accent_color", "")
            if custom_accent and custom_accent.startswith("#") and len(custom_accent) == 7:
                self._theme_accent_bright = custom_accent
        except Exception as e:
            _log.debug(f"Failed to load face customization: {e}")

    def apply_theme(self, theme_key: str):
        """Apply a color theme by key. Safe to call at any time."""
        theme = _THEMES.get(theme_key)
        if not theme:
            return
        self._theme_accent_bright = theme["accent_bright"]
        self._theme_accent_mid = theme["accent_mid"]
        self._theme_accent_dim = theme["accent_dim"]
        self._theme_accent_vdim = theme["accent_vdim"]
        self._theme_eye_pupil = theme["eye_pupil"]
        self._theme_eye_glow_inner = theme["eye_glow_inner"]
        self._theme_eye_glow_outer = theme["eye_glow_outer"]
        self._theme_face_border = theme["face_border"]

    def apply_geometry(self, **kwargs):
        """Apply geometry overrides at runtime.

        Keys: eye_width, eye_height, eye_spacing, eye_y, pupil_radius,
              pupil_max_ox, pupil_max_oy, mouth_y, mouth_width, mouth_height.
        """
        _GEO_MAP = {
            'eye_width': '_geo_eye_width', 'eye_height': '_geo_eye_height',
            'eye_spacing': '_geo_eye_spacing', 'eye_y': '_geo_eye_y',
            'pupil_radius': '_geo_pupil_radius',
            'pupil_max_ox': '_geo_pupil_max_ox', 'pupil_max_oy': '_geo_pupil_max_oy',
            'mouth_y': '_geo_mouth_y', 'mouth_width': '_geo_mouth_width',
            'mouth_height': '_geo_mouth_height',
        }
        for key, attr in _GEO_MAP.items():
            if key in kwargs:
                setattr(self, attr, float(kwargs[key]))

    def apply_animation(self, **kwargs):
        """Apply animation overrides at runtime.

        Keys: blink_min, blink_max, blink_duration, double_blink_chance,
              gaze_change_min, gaze_change_max, gaze_speed.
        """
        _ANIM_MAP = {
            'blink_min': '_anim_blink_min', 'blink_max': '_anim_blink_max',
            'blink_duration': '_anim_blink_duration',
            'double_blink_chance': '_anim_double_blink_chance',
            'gaze_change_min': '_anim_gaze_change_min',
            'gaze_change_max': '_anim_gaze_change_max',
            'gaze_speed': '_anim_gaze_speed',
        }
        for key, attr in _ANIM_MAP.items():
            if key in kwargs:
                setattr(self, attr, float(kwargs[key]))

    def apply_customization(self, theme: str = None, eye_style: str = None,
                            face_shape: str = None, accessory: str = None,
                            scan_lines: bool = None, custom_accent: str = None,
                            geometry: dict = None, animation: dict = None):
        """Apply one or more customization options. Safe to call at any time."""
        if theme is not None:
            self.apply_theme(theme)
        if eye_style is not None and eye_style in _EYE_STYLES:
            self._eye_style = eye_style
        if face_shape is not None and face_shape in _FACE_SHAPES:
            self._face_shape = face_shape
        if accessory is not None and accessory in _ACCESSORIES:
            self._accessory = accessory
        if scan_lines is not None:
            self._scan_lines = scan_lines
        if custom_accent and custom_accent.startswith("#") and len(custom_accent) == 7:
            self._theme_accent_bright = custom_accent
        if geometry:
            self.apply_geometry(**geometry)
        if animation:
            self.apply_animation(**animation)

    # ------------------------------------------------------------------
    # Plugin / modular extension system
    # ------------------------------------------------------------------

    _draw_plugins: list = []  # class-level default; instance gets own copy

    def register_plugin(self, name: str, draw_fn, layer: str = "overlay"):
        """Register a plugin draw function.

        Args:
            name: Unique identifier for this plugin.
            draw_fn: Callable(canvas, cx, pulse) called each frame.
                     canvas = self (FaceCanvas), cx = center x in design coords,
                     pulse = current pulse value (0-1 sine wave).
            layer: When to draw — "background" (before face), "overlay" (after face).
        """
        # Remove any existing plugin with same name
        self._draw_plugins = [p for p in self._draw_plugins if p[0] != name]
        self._draw_plugins.append((name, draw_fn, layer))
        _log.debug(f"Face plugin registered: {name} (layer={layer})")

    def unregister_plugin(self, name: str):
        """Remove a plugin by name."""
        self._draw_plugins = [p for p in self._draw_plugins if p[0] != name]

    def list_plugins(self) -> list[str]:
        """Return names of all registered plugins."""
        return [p[0] for p in self._draw_plugins]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def speak(self, text: str, chars_per_sec: float = 12.0):
        """Trigger mouth animation for given text. Thread-safe."""
        phonemes = text_to_phonemes(text, chars_per_sec)
        self.mouth_state.phoneme_sequence = phonemes
        self.mouth_state.speech_start_time = time.time()
        self.mouth_state.is_speaking = True
        self.mouth_state.phoneme_index = 0

    def set_emotion(self, emotion: str):
        """Set the face emotion. Smoothly interpolates to the target.

        Supported: neutral, thinking, curious, satisfied, confused,
                   determined, amused, surprised, listening, working.
        """
        self._current_emotion_name = emotion
        preset = _EMOTION_PRESETS.get(emotion, _EMOTION_PRESETS["neutral"])

        em = self.emotion
        em._target_squint = preset["squint"]
        em._target_brow_raise = preset["brow_raise"]
        em._target_eye_widen = preset["eye_widen"]
        em._target_mouth_curve = preset["mouth_curve"]
        em._target_pupil_size = preset["pupil_size"]
        em._target_gaze_speed = preset["gaze_speed"]
        em._target_blink_rate = preset["blink_rate"]
        em._target_intensity = preset["intensity"]

    # ------------------------------------------------------------------
    # Gesture API (enhanced face only)
    # ------------------------------------------------------------------

    def trigger_gesture(self, gesture_name: str):
        """Trigger a gesture animation (nod, shake, celebrate, etc.).
        
        Available gestures:
        - nod: Agreement/yes
        - shake: Disagreement/no
        - tilt: Curiosity/confusion
        - shrug: Don't know
        - celebrate: Success!
        - think: Pondering
        """
        if not self._enhancements_enabled:
            return
        
        from face.enhancements.gesture_system import GestureType
        
        gesture_map = {
            "nod": GestureType.NOD,
            "shake": GestureType.SHAKE,
            "tilt": GestureType.TILT,
            "shrug": GestureType.SHRUG,
            "celebrate": GestureType.CELEBRATE,
            "think": GestureType.THINK,
            "lean_forward": GestureType.LEAN_FORWARD,
            "lean_back": GestureType.LEAN_BACK,
        }
        
        gesture_type = gesture_map.get(gesture_name.lower())
        if gesture_type:
            self._gesture_system.trigger_gesture(gesture_type)
    
    def nod(self):
        """Perform a nod gesture (yes/agreement)."""
        self.trigger_gesture("nod")
    
    def shake(self):
        """Perform a head shake gesture (no/disagreement)."""
        self.trigger_gesture("shake")
    
    def celebrate(self):
        """Perform a celebration gesture (success!)."""
        self.trigger_gesture("celebrate")
    
    def shrug(self):
        """Perform a shrug gesture (don't know)."""
        self.trigger_gesture("shrug")
    
    def set_attention_mode(self, mode: str):
        """Set attention mode: idle, tracking, or focused.
        
        - idle: Eyes wander randomly
        - tracking: Eyes follow mouse cursor
        - focused: Eyes look at center (user)
        """
        if not self._enhancements_enabled:
            return
        
        if mode == "idle":
            self._attention.idle(self._eye_tracker)
        elif mode == "tracking":
            self._attention.track_mouse(self._eye_tracker)
        elif mode == "focused":
            self._attention.focus_on_user(self._eye_tracker)
        em = self.emotion
        em._target_squint = preset["squint"]
        em._target_brow_raise = preset["brow_raise"]
        em._target_eye_widen = preset["eye_widen"]
        em._target_mouth_curve = preset["mouth_curve"]
        em._target_pupil_size = preset["pupil_size"]
        em._target_gaze_speed = preset["gaze_speed"]
        em._target_blink_rate = preset["blink_rate"]
        em._target_intensity = preset["intensity"]

    def set_status(self, text: str):
        self._status_text = text

    def set_idle(self, active: bool):
        """Enable or disable idle behaviors (micro-expressions, wide gaze)."""
        self._idle_active = active
        if not active:
            self._idle_micro_active = False

    def stop(self):
        self._running = False

    # ------------------------------------------------------------------
    # Animation loop
    # ------------------------------------------------------------------

    def _tick(self):
        if not self._running:
            return
        now = time.time()
        dt = min(now - self._last_time, 0.1)
        self._last_time = now
        self._pulse = (now - self._start_time) * 0.8

        # Enhanced animation pipeline
        if self._enhancements_enabled:
            self._update_enhanced(dt, now)
        else:
            # Legacy animation pipeline
            self._update_idle(dt, now)
            self._update_work_state(dt)
            self._update_emotion(dt)
            self._update_eyes(dt)
            self._update_mouth(dt)
        
        self._recompute_scale()
        self._draw()

        self.after(FRAME_MS, self._tick)

    # ------------------------------------------------------------------
    # Enhanced animation pipeline (with smooth transitions, eye tracking, gestures)
    # ------------------------------------------------------------------

    def _update_enhanced(self, dt: float, now: float):
        """Enhanced animation pipeline using new enhancement modules."""
        # Get mouse position for eye tracking
        try:
            mouse_x = self.winfo_pointerx() - self.winfo_rootx()
            mouse_y = self.winfo_pointery() - self.winfo_rooty()
            mouse_pos = (mouse_x, mouse_y)
            window_size = (self.winfo_width(), self.winfo_height())
        except:
            mouse_pos = None
            window_size = (800, 600)
        
        # Update eye tracking
        eye_x, eye_y, should_blink = self._eye_tracker.update(dt, mouse_pos, window_size)
        
        # Update attention system
        self._attention.update(dt, self._eye_tracker)
        
        # Update idle behaviors (micro-expressions, breathing)
        idle_mods = self._idle_behavior.update(dt, self._current_emotion_name)
        
        # Update gestures
        gesture_mods = self._gesture_system.update()
        
        # Apply eye tracking to eye state
        self.eye_state.gaze_target_x = eye_x * 2.0  # Scale to match existing range
        self.eye_state.gaze_target_y = eye_y * 2.0
        
        # Trigger blink if needed
        if should_blink and not self.eye_state.is_blinking:
            self.eye_state.blink_timer = 0.0
            self.eye_state.is_blinking = True
        
        # Apply modifiers from idle behaviors
        if idle_mods:
            em = self.emotion
            if "eye_squint" in idle_mods:
                em._target_squint += idle_mods["eye_squint"]
            if "eyebrow_height" in idle_mods:
                em._target_brow_raise += idle_mods["eyebrow_height"]
            if "mouth_curve" in idle_mods:
                em._target_mouth_curve += idle_mods["mouth_curve"]
        
        # Apply modifiers from gestures
        if gesture_mods:
            # Gestures can override emotion temporarily
            if "head_pitch" in gesture_mods:
                # Head nod/shake - could affect eye position
                pass  # Implement head movement if needed
            if "eye_sparkle" in gesture_mods:
                # Celebration sparkle effect
                self.emotion._target_intensity += gesture_mods["eye_sparkle"] * 0.5
        
        # Continue with standard updates
        self._update_emotion(dt)
        self._update_eyes(dt)
        self._update_mouth(dt)

    # ------------------------------------------------------------------
    # Idle behaviors (micro-expressions, wide gaze drifts)
    # ------------------------------------------------------------------

    # Subtle micro-expression presets (small deviations from neutral)
    _MICRO_EXPRESSIONS = [
        {"squint": 0.08, "brow_raise": 0.12, "mouth_curve": 0.25,
         "pupil_size": 1.05, "gaze_speed": 0.8, "intensity": 0.3},   # slight smile
        {"squint": -0.05, "brow_raise": 0.2, "mouth_curve": 0.0,
         "pupil_size": 1.1, "gaze_speed": 1.2, "intensity": 0.3},    # curious glance
        {"squint": 0.12, "brow_raise": -0.1, "mouth_curve": -0.08,
         "pupil_size": 0.95, "gaze_speed": 0.5, "intensity": 0.2},   # pensive
        {"squint": 0.0, "brow_raise": 0.1, "mouth_curve": 0.2,
         "pupil_size": 1.0, "gaze_speed": 0.9, "intensity": 0.15},   # content
        {"squint": -0.08, "brow_raise": 0.25, "mouth_curve": 0.0,
         "pupil_size": 1.15, "gaze_speed": 1.0, "intensity": 0.25},  # alert
        {"squint": 0.15, "brow_raise": 0.15, "mouth_curve": 0.35,
         "pupil_size": 1.02, "gaze_speed": 0.6, "intensity": 0.35},  # warm smile
        {"squint": 0.05, "brow_raise": -0.12, "mouth_curve": -0.1,
         "pupil_size": 0.98, "gaze_speed": 0.4, "intensity": 0.2},   # subtle skeptical
        {"squint": -0.1, "brow_raise": 0.3, "mouth_curve": 0.1,
         "pupil_size": 1.2, "gaze_speed": 1.3, "intensity": 0.3},    # intrigued
    ]

    def _update_idle(self, dt: float, now: float):
        """Update idle behaviors — only runs when face is in neutral/idle state."""
        if not self._idle_active:
            return
        # Only trigger idle behaviors when in neutral state and not speaking
        if self._current_emotion_name not in ("neutral",) or self.mouth_state.is_speaking:
            self._idle_micro_timer = 0.0
            self._idle_gaze_drift_timer = 0.0
            return

        # --- Micro-expression triggers ---
        self._idle_micro_timer += dt
        if self._idle_micro_active and now >= self._idle_micro_revert:
            # Revert to neutral
            self._idle_micro_active = False
            em = self.emotion
            neutral = _EMOTION_PRESETS["neutral"]
            em._target_squint = neutral["squint"]
            em._target_brow_raise = neutral["brow_raise"]
            em._target_mouth_curve = neutral["mouth_curve"]
            em._target_pupil_size = neutral["pupil_size"]
            em._target_gaze_speed = neutral["gaze_speed"]
            em._target_intensity = neutral["intensity"]
            em._target_eye_widen = neutral["eye_widen"]
            em._target_blink_rate = neutral["blink_rate"]

        if not self._idle_micro_active and self._idle_micro_timer >= self._idle_next_micro:
            # Trigger a micro-expression
            micro = random.choice(self._MICRO_EXPRESSIONS)
            em = self.emotion
            em._target_squint = micro["squint"]
            em._target_brow_raise = micro["brow_raise"]
            em._target_mouth_curve = micro["mouth_curve"]
            em._target_pupil_size = micro["pupil_size"]
            em._target_gaze_speed = micro["gaze_speed"]
            em._target_intensity = micro["intensity"]
            self._idle_micro_active = True
            self._idle_micro_revert = now + random.uniform(1.5, 3.5)
            self._idle_micro_timer = 0.0
            self._idle_next_micro = random.uniform(5.0, 12.0)

        # --- Wide gaze drifts (slow, deliberate eye movement) ---
        self._idle_gaze_drift_timer += dt
        if self._idle_gaze_drift_timer >= self._idle_next_drift:
            es = self.eye_state
            # Wider range than normal gaze, slower speed
            es.gaze_target_x = random.uniform(-1.5, 1.5)
            es.gaze_target_y = random.uniform(-0.8, 0.6)
            # Occasionally look directly at the user (center)
            if random.random() < 0.35:
                es.gaze_target_x = random.uniform(-0.15, 0.15)
                es.gaze_target_y = random.uniform(-0.1, 0.1)
            self._idle_gaze_drift_timer = 0.0
            self._idle_next_drift = random.uniform(4.0, 10.0)

    # ------------------------------------------------------------------
    # Work-state micro-expressions (thinking/working/listening)
    # ------------------------------------------------------------------

    # Sub-emotion variants for each work state — small deviations from base
    _WORK_STATE_MICROS = {
        "thinking": [
            # slightly more squinty, pondering
            {"squint": 0.30, "brow_raise": -0.20, "pupil_size": 0.88, "gaze_speed": 0.4},
            # eyes widen briefly — eureka moment
            {"squint": 0.10, "brow_raise": 0.10, "pupil_size": 1.05, "gaze_speed": 0.8},
            # deep thought — brow furrow
            {"squint": 0.35, "brow_raise": -0.25, "pupil_size": 0.85, "gaze_speed": 0.3},
        ],
        "working": [
            # focused, determined
            {"squint": 0.20, "brow_raise": -0.15, "pupil_size": 0.90, "gaze_speed": 0.5},
            # brief satisfaction — something worked
            {"squint": 0.10, "brow_raise": 0.05, "mouth_curve": 0.15, "pupil_size": 1.0, "gaze_speed": 0.6},
            # concentrated — narrow gaze
            {"squint": 0.25, "brow_raise": -0.10, "pupil_size": 0.92, "gaze_speed": 0.4},
        ],
        "listening": [
            # attentive, slightly wider eyes
            {"squint": -0.08, "brow_raise": 0.25, "pupil_size": 1.12, "gaze_speed": 0.3},
            # processing — brief squint
            {"squint": 0.05, "brow_raise": 0.15, "pupil_size": 1.08, "gaze_speed": 0.5},
            # engaged — pupils dilate
            {"squint": -0.05, "brow_raise": 0.20, "pupil_size": 1.18, "gaze_speed": 0.4},
        ],
    }

    def _update_work_state(self, dt: float):
        """Subtle micro-expression shifts during thinking/working/listening states."""
        if self._current_emotion_name not in self._WORK_STATE_MICROS:
            self._work_micro_timer = 0.0
            return

        self._work_micro_timer += dt
        if self._work_micro_timer < self._work_next_micro:
            return

        # Pick a random sub-emotion variant for this work state
        micros = self._WORK_STATE_MICROS[self._current_emotion_name]
        micro = random.choice(micros)
        em = self.emotion

        # Apply micro-deviations as targets (emotion interpolation smooths them)
        for key, val in micro.items():
            target_attr = f"_target_{key}"
            if hasattr(em, target_attr):
                setattr(em, target_attr, val)

        # Also add subtle gaze shifts during work
        es = self.eye_state
        es.gaze_target_x = random.uniform(-0.8, 0.8)
        es.gaze_target_y = random.uniform(-0.4, 0.3)
        # 40% chance to look at user (staying engaged)
        if random.random() < 0.40:
            es.gaze_target_x = random.uniform(-0.1, 0.1)
            es.gaze_target_y = random.uniform(-0.05, 0.05)

        self._work_micro_timer = 0.0
        self._work_next_micro = random.uniform(2.0, 5.0)

    # ------------------------------------------------------------------
    # Emotion interpolation
    # ------------------------------------------------------------------

    def _update_emotion(self, dt: float):
        """Smoothly interpolate emotion parameters toward targets."""
        em = self.emotion
        speed = 3.0 * dt  # ~0.3s transition
        for attr in ("squint", "brow_raise", "eye_widen", "mouth_curve",
                     "pupil_size", "gaze_speed", "blink_rate", "intensity"):
            current = getattr(em, attr)
            target = getattr(em, f"_target_{attr}")
            setattr(em, attr, current + (target - current) * min(speed, 1.0))
        # Sync squint to eye_state for backward compatibility
        self.eye_state.squint = em.squint

    # ------------------------------------------------------------------
    # Eye updates
    # ------------------------------------------------------------------

    def _update_eyes(self, dt: float):
        es = self.eye_state
        em = self.emotion
        es.blink_timer += dt
        blink_mult = max(0.2, em.blink_rate)
        if not es.is_blinking and es.blink_timer >= es.next_blink:
            es.is_blinking = True
            es.blink_progress = 0.0
            es.blink_timer = 0.0
            es.next_blink = random.uniform(self._anim_blink_min, self._anim_blink_max) / blink_mult
            if random.random() < self._anim_double_blink_chance:
                es.double_blink_pending = True
        if es.is_blinking:
            es.blink_progress += dt / self._anim_blink_duration
            if es.blink_progress >= 2.0:
                es.blink_progress = 0.0
                es.is_blinking = False
                if es.double_blink_pending:
                    es.double_blink_pending = False
                    es.next_blink = 0.15
                    es.blink_timer = 0.0
        es.next_gaze_change -= dt
        if es.next_gaze_change <= 0:
            es.gaze_target_x = random.uniform(-1, 1)
            es.gaze_target_y = random.uniform(-0.5, 0.5)
            if random.random() < 0.40:
                es.gaze_target_x = random.uniform(-0.1, 0.1)
                es.gaze_target_y = random.uniform(-0.08, 0.08)
            es.next_gaze_change = random.uniform(self._anim_gaze_change_min, self._anim_gaze_change_max)
        speed = self._anim_gaze_speed * em.gaze_speed * dt
        es.gaze_x += (es.gaze_target_x - es.gaze_x) * min(speed, 1.0)
        es.gaze_y += (es.gaze_target_y - es.gaze_y) * min(speed, 1.0)

    # ------------------------------------------------------------------
    # Mouth updates
    # ------------------------------------------------------------------

    def _update_mouth(self, dt: float):
        ms = self.mouth_state
        if ms.is_speaking and ms.phoneme_sequence:
            elapsed = time.time() - ms.speech_start_time
            while (ms.phoneme_index < len(ms.phoneme_sequence) - 1
                   and ms.phoneme_sequence[ms.phoneme_index + 1][0] <= elapsed):
                ms.phoneme_index += 1
            if ms.phoneme_index >= len(ms.phoneme_sequence):
                ms.is_speaking = False
                ms.target_phoneme = Phoneme.CLOSED
            else:
                ms.target_phoneme = ms.phoneme_sequence[ms.phoneme_index][1]
            if ms.phoneme_sequence and elapsed > ms.phoneme_sequence[-1][0] + 0.3:
                ms.is_speaking = False
                ms.target_phoneme = Phoneme.CLOSED
        else:
            ms.target_phoneme = Phoneme.CLOSED
        targets = {
            Phoneme.CLOSED: (0.0, 1.0), Phoneme.SMALL: (0.3, 0.85),
            Phoneme.MEDIUM: (0.55, 1.0), Phoneme.WIDE: (0.9, 1.2),
            Phoneme.ROUND: (0.65, 0.5), Phoneme.TEETH: (0.25, 1.15),
        }
        to, tw = targets.get(ms.target_phoneme, (0.0, 1.0))
        ls = 14.0 * dt
        ms.open_amount += (to - ms.open_amount) * min(ls, 1.0)
        ms.width_factor += (tw - ms.width_factor) * min(ls, 1.0)

    # ------------------------------------------------------------------
    # Render backend switching & draw dispatch
    # ------------------------------------------------------------------

    def enable_pygame(self, viewport):
        """Switch to Pygame rendering via the given PygameViewport.

        Args:
            viewport: A PygameViewport widget instance.
        """
        if viewport and viewport.available:
            self._use_pygame = True
            self._r = viewport.renderer
            self._viewport = viewport
            _log.info("FaceCanvas: switched to Pygame renderer")
        else:
            _log.warning("FaceCanvas: Pygame not available, staying on Tkinter")

    def disable_pygame(self):
        """Switch back to Tkinter Canvas rendering."""
        self._use_pygame = False
        self._r = None
        self._viewport = None

    @property
    def use_pygame(self) -> bool:
        return self._use_pygame

    def _begin_draw(self):
        if self._use_pygame and self._r:
            self._r.begin_frame(BG_COLOR)
        else:
            self.delete("all")

    def _end_draw(self):
        if self._use_pygame and self._r:
            self._r.end_frame()
            if self._viewport:
                self._viewport.present()

    def _d_oval(self, x0, y0, x1, y1, **kw):
        if self._use_pygame and self._r:
            self._r.draw_oval(x0, y0, x1, y1,
                              fill=kw.get('fill', ''),
                              outline=kw.get('outline', ''),
                              width=kw.get('width', 1),
                              stipple=kw.get('stipple', ''))
        else:
            tk.Canvas.create_oval(self, x0, y0, x1, y1, **kw)

    def _d_rect(self, x0, y0, x1, y1, **kw):
        if self._use_pygame and self._r:
            self._r.draw_rectangle(x0, y0, x1, y1,
                                    fill=kw.get('fill', ''),
                                    outline=kw.get('outline', ''),
                                    width=kw.get('width', 1))
        else:
            tk.Canvas.create_rectangle(self, x0, y0, x1, y1, **kw)

    def _d_line(self, *args, **kw):
        if self._use_pygame and self._r:
            flat = []
            for a in args:
                if isinstance(a, (list, tuple)):
                    flat.extend(a)
                else:
                    flat.append(float(a))
            pts = [(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)]
            self._r.draw_line(pts,
                              color=kw.get('fill', '#ffffff'),
                              width=kw.get('width', 1),
                              smooth=kw.get('smooth', False))
        else:
            tk.Canvas.create_line(self, *args, **kw)

    def _d_polygon(self, *args, **kw):
        if self._use_pygame and self._r:
            flat = []
            for a in args:
                if isinstance(a, (list, tuple)):
                    flat.extend(a)
                else:
                    flat.append(float(a))
            pts = [(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)]
            self._r.draw_polygon(pts,
                                  fill=kw.get('fill', ''),
                                  outline=kw.get('outline', ''),
                                  width=kw.get('width', 1))
        else:
            tk.Canvas.create_polygon(self, *args, **kw)

    def _d_text(self, x, y, **kw):
        if self._use_pygame and self._r:
            font_spec = kw.get('font', ('Consolas', 12))
            family = font_spec[0] if isinstance(font_spec, tuple) else 'Consolas'
            size = font_spec[1] if isinstance(font_spec, tuple) else 12
            self._r.draw_text(x, y,
                              text=kw.get('text', ''),
                              color=kw.get('fill', '#ffffff'),
                              font_family=family,
                              font_size=size)
        else:
            tk.Canvas.create_text(self, x, y, **kw)

    # ------------------------------------------------------------------
    # Drawing (all coords go through _sx/_sy/_ss)
    # ------------------------------------------------------------------

    def _draw(self):
        self._begin_draw()
        s = self._s
        if s < 0.01:
            self._end_draw()
            return

        cx = REF_W / 2
        es = self.eye_state

        # Background plugins (drawn behind the face)
        pulse_val = 0.5 + 0.5 * math.sin(self._pulse)
        for name, fn, layer in self._draw_plugins:
            if layer == "background":
                try:
                    fn(self, cx, pulse_val)
                except Exception:
                    pass

        self._draw_face_plate(cx)

        em = self.emotion
        blink_factor = 1.0
        if es.is_blinking:
            blink_factor = (1.0 - es.blink_progress) if es.blink_progress < 1.0 else (es.blink_progress - 1.0)
        blink_factor = max(0.0, blink_factor - es.squint * 0.5)
        # Eye widen from emotion (surprise opens eyes wider)
        blink_factor = min(1.0, blink_factor * (1.0 + em.eye_widen))

        for side in (-1, 1):
            self._draw_eye(cx + side * (self._geo_eye_spacing / 2), self._geo_eye_y, side, blink_factor)

        # Brow lines (always visible — expressiveness is key)
        self._draw_brows(cx, em.brow_raise, em.intensity)

        # Cheek glow when smiling
        if em.mouth_curve > 0.15:
            self._draw_cheek_glow(cx, em.mouth_curve)

        self._draw_mouth(cx, self._geo_mouth_y)
        self._draw_details(cx)

        # Overlay plugins (drawn on top of everything)
        for name, fn, layer in self._draw_plugins:
            if layer == "overlay":
                try:
                    fn(self, cx, pulse_val)
                except Exception:
                    pass

        # Trial watermark (only shown when not activated)
        self._draw_trial_watermark()

        self._end_draw()

    def _draw_trial_watermark(self):
        """Draw a subtle trial/demo indicator when license is not activated."""
        if not hasattr(self, "_trial_cache_time"):
            self._trial_cache_time = 0
            self._trial_text = ""
            self._trial_show = False

        # Only check trial status every 30 seconds (not every frame)
        now = time.time() if hasattr(time, "time") else 0
        if now - self._trial_cache_time > 30:
            self._trial_cache_time = now
            try:
                # Dev-mode bypass: skip trial watermark when running from source
                _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if os.path.isdir(os.path.join(_proj, "tests")):
                    self._trial_show = False
                    return

                from core.security import get_trial_manager
                trial = get_trial_manager()
                if trial.is_activated():
                    self._trial_show = False
                else:
                    info = trial.trial_info()
                    days = info.get("days_remaining", 0)
                    if days > 0:
                        self._trial_text = f"TRIAL \u2022 {int(days)}d left"
                    else:
                        self._trial_text = "TRIAL EXPIRED"
                    self._trial_show = True
            except Exception:
                self._trial_show = False

        if not self._trial_show:
            return

        # Draw small text in bottom-right corner with low opacity
        x = self._sx(REF_W - 12)
        y = self._sy(REF_H - 8)
        font_size = max(7, int(self._s * 8))
        self.create_text(
            x, y,
            text=self._trial_text,
            fill="#ffffff",
            anchor="se",
            font=("Consolas", font_size),
            stipple="gray25",
            tags=("_frame",),
        )

    def _get_emotion_accent(self) -> str:
        """Get the current emotion-reactive accent color, blended with theme."""
        emotion_color = _EMOTION_ACCENT.get(self._current_emotion_name, self._theme_accent_bright)
        # Blend emotion color toward the theme accent for consistency
        return _lerp_color(emotion_color, self._theme_accent_bright, 0.3)

    def _draw_face_plate(self, cx):
        pad, top_pad, bot_pad = 18, 22, 18
        x0, y0 = pad, top_pad
        x1, y1 = REF_W - pad, REF_H - bot_pad

        pulse = 0.5 + 0.5 * math.sin(self._pulse)
        accent = self._get_emotion_accent()
        accent_dim = _lerp_color(BG_COLOR, accent, 0.25)
        accent_mid = _lerp_color(BG_COLOR, accent, 0.45)

        border_color = _lerp_color(accent_dim, accent_mid, pulse * 0.4)
        glow_color = _lerp_color(BG_COLOR, accent_dim, pulse * 0.3)

        shape = self._face_shape

        if shape == "circle":
            # Circular face plate
            r = min(x1 - x0, y1 - y0) / 2
            ccx_d, ccy_d = (x0 + x1) / 2, (y0 + y1) / 2
            self._d_oval(
                self._sx(ccx_d - r - 3), self._sy(ccy_d - r - 3),
                self._sx(ccx_d + r + 3), self._sy(ccy_d + r + 3),
                outline=glow_color, width=max(1, self._ss(2)))
            self._d_oval(
                self._sx(ccx_d - r), self._sy(ccy_d - r),
                self._sx(ccx_d + r), self._sy(ccy_d + r),
                fill=FACE_COLOR, outline=border_color, width=max(1, self._ss(2)))
        elif shape == "hexagon":
            # Hexagonal face plate
            ccx_d, ccy_d = (x0 + x1) / 2, (y0 + y1) / 2
            hw, hh = (x1 - x0) / 2, (y1 - y0) / 2
            pts_glow = []
            pts_face = []
            for i in range(6):
                angle = math.radians(60 * i - 90)
                pts_glow.extend([self._sx(ccx_d + (hw + 3) * math.cos(angle)),
                                 self._sy(ccy_d + (hh + 3) * math.sin(angle))])
                pts_face.extend([self._sx(ccx_d + hw * math.cos(angle)),
                                 self._sy(ccy_d + hh * math.sin(angle))])
            self._d_polygon(pts_glow, outline=glow_color, fill="", width=max(1, self._ss(2)))
            self._d_polygon(pts_face, fill=FACE_COLOR, outline=border_color, width=max(1, self._ss(2)))
        elif shape == "diamond":
            # Diamond face plate
            ccx_d, ccy_d = (x0 + x1) / 2, (y0 + y1) / 2
            hw, hh = (x1 - x0) / 2, (y1 - y0) / 2
            pts_glow = [self._sx(ccx_d), self._sy(ccy_d - hh - 3),
                        self._sx(ccx_d + hw + 3), self._sy(ccy_d),
                        self._sx(ccx_d), self._sy(ccy_d + hh + 3),
                        self._sx(ccx_d - hw - 3), self._sy(ccy_d)]
            pts_face = [self._sx(ccx_d), self._sy(ccy_d - hh),
                        self._sx(ccx_d + hw), self._sy(ccy_d),
                        self._sx(ccx_d), self._sy(ccy_d + hh),
                        self._sx(ccx_d - hw), self._sy(ccy_d)]
            self._d_polygon(pts_glow, outline=glow_color, fill="", width=max(1, self._ss(2)))
            self._d_polygon(pts_face, fill=FACE_COLOR, outline=border_color, width=max(1, self._ss(2)))
        elif shape == "shield":
            # Shield shape — rounded top, pointed bottom
            ccx_d = (x0 + x1) / 2
            hw = (x1 - x0) / 2
            pts = []
            # Top left arc
            for i in range(9):
                angle = math.radians(180 + 90 * i / 8)
                pts.extend([self._sx(x0 + 16 + 16 * math.cos(angle)),
                            self._sy(y0 + 16 - 16 * math.sin(angle))])
            # Top right arc
            for i in range(9):
                angle = math.radians(270 + 90 * i / 8)
                pts.extend([self._sx(x1 - 16 + 16 * math.cos(angle)),
                            self._sy(y0 + 16 - 16 * math.sin(angle))])
            # Point at bottom
            pts.extend([self._sx(x1), self._sy(y1 - 60)])
            pts.extend([self._sx(ccx_d), self._sy(y1 + 5)])
            pts.extend([self._sx(x0), self._sy(y1 - 60)])
            self._d_polygon(pts, fill=FACE_COLOR, outline=border_color, width=max(1, self._ss(2)))
        else:
            # Default: rounded rectangle
            self._d_rect(
                self._sx(x0 - 3), self._sy(y0 - 3), self._sx(x1 + 3), self._sy(y1 + 3),
                outline=glow_color, width=max(1, self._ss(2)))
            self._rounded_rect(x0, y0, x1, y1, 16, fill=FACE_COLOR, outline=border_color, width=max(1, self._ss(2)))

        # Accent bars (decorative details on face plate)
        bar_c = _lerp_color(accent_mid, accent, pulse * 0.5)
        self._d_rect(
            self._sx(x0 + 30), self._sy(y0 + 1), self._sx(x1 - 30), self._sy(y0 + 4),
            fill=bar_c, outline="")
        self._d_rect(
            self._sx(x0 + 8), self._sy(y0 + 12), self._sx(x1 - 8), self._sy(y0 + 13),
            fill=self._theme_accent_vdim, outline="")
        self._d_rect(
            self._sx(x0 + 50), self._sy(y1 - 4), self._sx(x1 - 50), self._sy(y1 - 1),
            fill=accent_dim, outline="")

    def _draw_eye(self, ex, ey, side, blink_factor):
        es = self.eye_state
        eye_style = self._eye_style
        ew = self._geo_eye_width
        eh = self._geo_eye_height

        # Eye dimensions based on style
        if eye_style == "round":
            hw = eh / 2   # same w and h = circle
            hh = (eh / 2) * max(blink_factor, 0.03)
        elif eye_style == "narrow":
            hw = ew / 2 * 1.2
            hh = (eh / 2 * 0.5) * max(blink_factor, 0.03)
        elif eye_style == "wide":
            hw = ew / 2 * 1.3
            hh = (eh / 2 * 1.15) * max(blink_factor, 0.03)
        else:  # default or angular
            hw = ew / 2
            hh = (eh / 2) * max(blink_factor, 0.03)

        if eye_style == "angular":
            # Hexagonal / angular eye shape
            pts_glow = []
            pts_eye = []
            for i in range(6):
                angle = math.radians(60 * i - 90)
                pts_glow.extend([self._sx(ex + (hw + 3) * math.cos(angle)),
                                 self._sy(ey + (hh + 3) * math.sin(angle))])
                pts_eye.extend([self._sx(ex + hw * math.cos(angle)),
                                self._sy(ey + hh * math.sin(angle))])
            self._d_polygon(pts_glow, fill="", outline=self._theme_accent_dim, width=1)
            self._d_polygon(pts_eye, fill=EYE_SCLERA, outline=self._theme_face_border, width=1)
        else:
            # Oval/round/narrow/wide — all use oval with different hw/hh
            self._d_oval(
                self._sx(ex - hw - 3), self._sy(ey - hh - 3),
                self._sx(ex + hw + 3), self._sy(ey + hh + 3),
                fill="", outline=self._theme_accent_dim, width=1)
            self._d_oval(
                self._sx(ex - hw), self._sy(ey - hh),
                self._sx(ex + hw), self._sy(ey + hh),
                fill=EYE_SCLERA, outline=self._theme_face_border, width=1)

        if blink_factor < 0.15:
            self._d_line(
                self._sx(ex - hw + 4), self._sy(ey), self._sx(ex + hw - 4), self._sy(ey),
                fill=self._theme_accent_dim, width=max(1, self._ss(2)))
            return

        px = ex + es.gaze_x * self._geo_pupil_max_ox
        py = ey + es.gaze_y * self._geo_pupil_max_oy
        pulse = 0.5 + 0.5 * math.sin(self._pulse)
        ps = self.emotion.pupil_size  # emotion-driven pupil scale

        pr_base = self._geo_pupil_radius
        for radius, color in [
            (pr_base + 12, _lerp_color("#001018", self._theme_eye_glow_outer, 0.5 + pulse * 0.3)),
            (pr_base + 6, _lerp_color(self._theme_eye_glow_outer, self._theme_eye_glow_inner, 0.4 + pulse * 0.2)),
        ]:
            r = self._ss(radius * ps)
            self._d_oval(self._sx(px) - r, self._sy(py) - r, self._sx(px) + r, self._sy(py) + r,
                             fill=color, outline="")

        # Iris ring
        ir = self._ss((pr_base + 2) * ps)
        self._d_oval(self._sx(px) - ir, self._sy(py) - ir, self._sx(px) + ir, self._sy(py) + ir,
                         fill="", outline=self._theme_accent_mid, width=max(1, self._ss(2)))

        # Main pupil
        pr = self._ss(pr_base * ps)
        pupil_highlight = _lerp_color(self._theme_eye_pupil, "#ffffff", 0.2)
        pc = _lerp_color(self._theme_eye_pupil, pupil_highlight, pulse * 0.3)
        self._d_oval(self._sx(px) - pr, self._sy(py) - pr, self._sx(px) + pr, self._sy(py) + pr,
                         fill=pc, outline="")

        # Inner dark
        dr = pr * 0.4
        self._d_oval(self._sx(px) - dr, self._sy(py) - dr, self._sx(px) + dr, self._sy(py) + dr,
                         fill="#001520", outline="")

        # Specular highlights
        hx, hy, hr = self._sx(px) - pr * 0.3, self._sy(py) - pr * 0.35, pr * 0.25
        self._d_oval(hx - hr, hy - hr, hx + hr, hy + hr, fill=EYE_HIGHLIGHT, outline="")
        h2x, h2y, h2r = self._sx(px) + pr * 0.25, self._sy(py) + pr * 0.2, pr * 0.12
        self._d_oval(h2x - h2r, h2y - h2r, h2x + h2r, h2y + h2r, fill="#88ccdd", outline="")

    def _draw_brows(self, cx, brow_raise: float, intensity: float = 0.0):
        """Draw expressive brow lines above each eye.

        brow_raise > 0: raised brows (surprised, curious) — arched upward
        brow_raise < 0: furrowed brows (angry, confused) — angled inward/down
        Always visible with at least a subtle neutral arch.
        """
        pulse = 0.5 + 0.5 * math.sin(self._pulse)
        # Brows get brighter with more expression
        brightness = 0.4 + abs(brow_raise) * 0.5 + intensity * 0.2 + pulse * 0.08
        bc = _lerp_color(self._theme_accent_dim, self._theme_accent_mid, min(brightness, 1.0))
        # Brow thickness scales with expression intensity
        base_w = 3.0 + abs(brow_raise) * 1.5 + intensity * 0.5
        bw = max(2, self._ss(base_w))

        for side in (-1, 1):
            ex = cx + side * (self._geo_eye_spacing / 2)
            hw = self._geo_eye_width / 2
            brow_y = self._geo_eye_y - self._geo_eye_height / 2 - 10

            # Vertical offset from raise (dramatic range for visible expression)
            raise_offset = -brow_raise * 22
            # Inner/outer tilt from furrow (dramatic)
            inner_tilt = brow_raise * 12 * side
            outer_tilt = -brow_raise * 7 * side

            pts = []
            for i in range(15):  # more points = smoother curve
                t = i / 14
                x = ex - hw * 0.9 + t * hw * 1.8
                # Natural arch shape — always present, amplified by expression
                base_arch = math.sin(t * math.pi) * 3.0  # subtle neutral arch
                expr_arch = math.sin(t * math.pi) * brow_raise * 12
                arch = base_arch + expr_arch
                # Tilt: blend from inner to outer
                tilt = inner_tilt * (1 - t) + outer_tilt * t
                y = brow_y + raise_offset - arch + tilt
                pts.extend([self._sx(x), self._sy(y)])

            self._d_line(pts, fill=bc, width=bw, smooth=True)

    def _draw_cheek_glow(self, cx, mouth_curve: float):
        """Draw subtle glow indicators under the eyes when smiling."""
        alpha = min(1.0, (mouth_curve - 0.15) * 2.0)  # fade in as smile grows
        accent = self._theme_accent_bright
        glow_color = _lerp_color(BG_COLOR, accent, alpha * 0.20)

        for side in (-1, 1):
            cheek_x = cx + side * (self._geo_eye_spacing / 2)
            cheek_y = self._geo_eye_y + self._geo_eye_height / 2 + 12
            r = self._ss(14 + mouth_curve * 6)
            self._d_oval(
                self._sx(cheek_x) - r, self._sy(cheek_y) - r * 0.5,
                self._sx(cheek_x) + r, self._sy(cheek_y) + r * 0.5,
                fill=glow_color, outline="")

    def _draw_mouth(self, mx, my):
        ms = self.mouth_state
        w = self._geo_mouth_width * ms.width_factor
        h_open = max(self._geo_mouth_height * ms.open_amount * 4.0, 2)
        hw = w / 2

        sp = 0.0
        if ms.is_speaking:
            sp = 0.5 + 0.5 * math.sin(time.time() * 15)

        if ms.open_amount < 0.05:
            pulse = 0.5 + 0.5 * math.sin(self._pulse)
            mc = self.emotion.mouth_curve
            intensity = self.emotion.intensity

            # Mouth width grows slightly when smiling
            smile_w = w * (1.0 + abs(mc) * 0.2)
            smile_hw = smile_w / 2

            # Brighter when more expressive
            smile_boost = max(0, mc) * 0.4
            frown_boost = max(0, -mc) * 0.2
            lc = _lerp_color(self._theme_accent_dim, self._theme_accent_mid, pulse * 0.3 + smile_boost + frown_boost + 0.15)
            # Thicker line for bigger expressions
            lw = max(2, self._ss(2.5 + abs(mc) * 1.5))

            pts = []
            for i in range(25):  # more points = smoother curve
                t = i / 24
                x = mx - smile_hw + t * smile_w

                # --- Smile/frown shape with proper corner curves ---
                # Center arch (sine curve — positive mc pushes center up = smile)
                center_curve = math.sin(t * math.pi) * mc * 16

                # Corner curl: corners turn up for smile, down for frown
                # Uses a parabolic shape that's strongest at edges (t=0, t=1)
                edge_dist = 2.0 * (t - 0.5)  # -1 at left, +1 at right
                corner_curl = (edge_dist ** 2 - 0.25) * mc * 20

                # Subtle natural lip shape — slightly thinner at corners
                natural = math.sin(t * math.pi) * 1.5

                y = my - center_curve - corner_curl - natural
                pts.extend([self._sx(x), self._sy(y)])

            self._d_line(pts, fill=lc, width=lw, smooth=True)

            # Corner accent dots for bigger expressions (smile dimples / frown marks)
            if abs(mc) > 0.15:
                dot_alpha = min(1.0, (abs(mc) - 0.15) * 2.5)
                dot_c = _lerp_color(BG_COLOR, self._theme_accent_dim, dot_alpha * 0.7)
                dot_r = self._ss(2.5 + abs(mc) * 2.0)
                corner_y_offset = -mc * 18  # dots follow the curve direction
                for side_x in [mx - smile_hw + 2, mx + smile_hw - 2]:
                    self._d_oval(
                        self._sx(side_x) - dot_r, self._sy(my + corner_y_offset) - dot_r,
                        self._sx(side_x) + dot_r, self._sy(my + corner_y_offset) + dot_r,
                        fill=dot_c, outline="")
        else:
            top = my - h_open * 0.35
            bot = my + h_open * 0.65
            gp = 4
            gc = _lerp_color("#000510", self._theme_accent_vdim, sp * 0.5)
            self._d_oval(
                self._sx(mx - hw - gp), self._sy(top - gp),
                self._sx(mx + hw + gp), self._sy(bot + gp), fill=gc, outline="")
            mc = _lerp_color(self._theme_accent_mid, self._theme_accent_bright, sp * 0.3)
            self._d_oval(
                self._sx(mx - hw), self._sy(top), self._sx(mx + hw), self._sy(bot),
                fill=MOUTH_INTERIOR, outline=mc, width=max(1, self._ss(2)))
            ins = 4
            self._d_oval(
                self._sx(mx - hw + ins), self._sy(top + ins),
                self._sx(mx + hw - ins), self._sy(bot - ins), fill="#020508", outline="")
            if ms.target_phoneme == Phoneme.TEETH and ms.open_amount > 0.1:
                ty = top + (bot - top) * 0.22
                tw = hw * 0.55
                self._d_rect(
                    self._sx(mx - tw), self._sy(ty),
                    self._sx(mx + tw), self._sy(ty + 3), fill="#223344", outline="")
            if ms.open_amount > 0.6:
                tgy = bot - (bot - top) * 0.3
                tgr = hw * 0.3
                self._d_oval(
                    self._sx(mx - tgr), self._sy(tgy),
                    self._sx(mx + tgr), self._sy(bot - ins), fill="#0a1520", outline="")

    def _draw_details(self, cx):
        pad = 18
        x0, y0 = pad, 22
        x1, y1 = REF_W - pad, REF_H - 18

        for i in range(3):
            ly = y0 + 25 + i * 8
            self._d_line(self._sx(x0 + 6), self._sy(ly), self._sx(x0 + 22), self._sy(ly),
                             fill=self._theme_accent_vdim, width=1)
            self._d_line(self._sx(x1 - 22), self._sy(ly), self._sx(x1 - 6), self._sy(ly),
                             fill=self._theme_accent_vdim, width=1)

        pulse = 0.5 + 0.5 * math.sin(self._pulse * 1.5)
        dc = _lerp_color(self._theme_accent_dim, self._theme_accent_mid, pulse)
        dr = self._ss(3)
        for dx in [x0 + 12, x1 - 12]:
            dy = y1 - 14
            self._d_oval(self._sx(dx) - dr, self._sy(dy) - dr,
                             self._sx(dx) + dr, self._sy(dy) + dr, fill=dc, outline="")

        self._d_line(self._sx(cx - 25), self._sy(_MOUTH_Y + 35),
                         self._sx(cx + 25), self._sy(_MOUTH_Y + 35), fill=self._theme_accent_vdim, width=1)

        ny = _EYE_Y + _EYE_HEIGHT / 2 + 5
        self._d_polygon(
            self._sx(cx - 4), self._sy(ny), self._sx(cx + 4), self._sy(ny),
            self._sx(cx), self._sy(ny + 8), fill=self._theme_accent_vdim, outline="")
        self._d_oval(self._sx(cx - 4), self._sy(y0 + 18),
                         self._sx(cx + 4), self._sy(y0 + 24), fill="", outline=self._theme_accent_dim, width=1)

        # Scan lines (toggleable)
        if self._scan_lines:
            step = max(3, int(3 / max(self._s, 0.3)))
            sy0 = int(self._sy(y0))
            sy1 = int(self._sy(y1))
            sx0 = self._sx(x0)
            sx1 = self._sx(x1)
            for y in range(sy0, sy1, step):
                self._d_line(sx0, y, sx1, y, fill="#000000", stipple="gray12")

        # Accessories
        self._draw_accessory(cx)

        # Status text
        if self._status_text:
            self._d_text(
                self._sx(cx), self._sy(REF_H - 30),
                text=self._status_text, fill=self._theme_accent_mid,
                font=("Consolas", max(8, int(self._ss(10)))),
            )

    # ------------------------------------------------------------------
    # Accessories — optional overlay decorations
    # ------------------------------------------------------------------

    def _draw_accessory(self, cx):
        """Draw the selected accessory overlay on the face."""
        acc = self._accessory
        if acc == "none":
            return

        pulse = 0.5 + 0.5 * math.sin(self._pulse)
        accent = self._theme_accent_bright
        accent_dim = self._theme_accent_dim

        if acc == "antenna":
            # Single antenna on top center
            base_y = 22
            tip_y = -12
            # Antenna stalk
            self._d_line(
                self._sx(cx), self._sy(base_y),
                self._sx(cx), self._sy(tip_y),
                fill=accent_dim, width=max(1, self._ss(2.5)))
            # Glowing tip
            tip_r = self._ss(5 + pulse * 2)
            tip_c = _lerp_color(accent_dim, accent, 0.5 + pulse * 0.5)
            self._d_oval(
                self._sx(cx) - tip_r, self._sy(tip_y) - tip_r,
                self._sx(cx) + tip_r, self._sy(tip_y) + tip_r,
                fill=tip_c, outline="")

        elif acc == "headphones":
            # Headphone band over top + ear cups
            band_y = 18
            ear_y = self._geo_eye_y
            ear_offset = self._geo_eye_spacing / 2 + self._geo_eye_width / 2 + 14
            # Band arc
            pts = []
            for i in range(20):
                t = i / 19
                x = cx - ear_offset + t * ear_offset * 2
                arch = -math.sin(t * math.pi) * 28
                pts.extend([self._sx(x), self._sy(band_y + arch)])
            self._d_line(pts, fill=accent_dim, width=max(2, self._ss(4)), smooth=True)
            # Ear cups
            for side in (-1, 1):
                cup_x = cx + side * ear_offset
                cup_r = self._ss(12)
                self._d_oval(
                    self._sx(cup_x) - cup_r, self._sy(ear_y) - cup_r * 1.3,
                    self._sx(cup_x) + cup_r, self._sy(ear_y) + cup_r * 1.3,
                    fill=accent_dim, outline=_lerp_color(accent_dim, accent, 0.3),
                    width=max(1, self._ss(2)))

        elif acc == "visor":
            # Glowing visor strip across the eyes
            visor_y = self._geo_eye_y
            visor_hw = self._geo_eye_spacing / 2 + self._geo_eye_width / 2 + 8
            visor_hh = self._geo_eye_height / 2 * 0.6
            visor_c = _lerp_color(BG_COLOR, accent, 0.15 + pulse * 0.1)
            self._d_rect(
                self._sx(cx - visor_hw), self._sy(visor_y - visor_hh),
                self._sx(cx + visor_hw), self._sy(visor_y + visor_hh),
                fill=visor_c, outline=accent_dim, width=max(1, self._ss(1)))

        elif acc == "halo":
            # Glowing ring above the face
            halo_y = 10
            halo_rx = 55
            halo_ry = 12
            halo_c = _lerp_color(accent_dim, accent, 0.3 + pulse * 0.3)
            self._d_oval(
                self._sx(cx - halo_rx), self._sy(halo_y - halo_ry),
                self._sx(cx + halo_rx), self._sy(halo_y + halo_ry),
                fill="", outline=halo_c, width=max(2, self._ss(3)))

        elif acc == "horns":
            # Two curved horns from top corners
            for side in (-1, 1):
                base_x = cx + side * 60
                base_y = 30
                pts = []
                for i in range(12):
                    t = i / 11
                    x = base_x + side * t * 30
                    y = base_y - t * 40 + math.sin(t * math.pi) * 15 * side
                    pts.extend([self._sx(x), self._sy(y)])
                horn_c = _lerp_color(accent_dim, accent, 0.4)
                self._d_line(pts, fill=horn_c, width=max(2, self._ss(4 - t * 2)), smooth=True)

    def _rounded_rect(self, x0, y0, x1, y1, radius, **kwargs):
        r = min(radius, (x1 - x0) / 2, (y1 - y0) / 2)
        points = []
        steps = 8
        for ccx, ccy, a_start in [
            (x0 + r, y0 + r, 180), (x1 - r, y0 + r, 270),
            (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90),
        ]:
            for i in range(steps + 1):
                angle = math.radians(a_start + 90 * i / steps)
                points.append(self._sx(ccx + r * math.cos(angle)))
                points.append(self._sy(ccy - r * math.sin(angle)))
        self._d_polygon(points, **kwargs)


# ---------------------------------------------------------------------------
# Standalone entry point (legacy FaceApp wrapper for testing)
# ---------------------------------------------------------------------------

class FaceApp:
    """Standalone floating animated face window — wraps FaceCanvas.

    Args:
        use_pygame: If True (default), attempt hardware-accelerated
            Pygame rendering.  Falls back to Tkinter Canvas if
            pygame-ce is not available.
    """

    def __init__(self, use_pygame: bool = True):
        self.root = tk.Tk()
        self.root.title("OnyxKraken")
        self.root.geometry(f"{REF_W}x{REF_H}")
        self.root.configure(bg=BG_COLOR)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)

        self._drag_x = 0
        self._drag_y = 0
        self.root.bind("<Button-1>", self._on_drag_start)
        self.root.bind("<B1-Motion>", self._on_drag_motion)
        self.root.bind("<Button-3>", lambda e: self.close())
        self.root.bind("<Escape>", lambda e: self.close())

        self.face = FaceCanvas(self.root, width=REF_W, height=REF_H)
        self._viewport = None

        if use_pygame:
            try:
                from face.pygame_viewport import PygameViewport
                self._viewport = PygameViewport(
                    self.root, width=REF_W, height=REF_H)
                self._viewport.pack(fill="both", expand=True)
                self.face.enable_pygame(self._viewport)
                _log.info("FaceApp: Pygame renderer active")
            except Exception as exc:
                _log.warning(f"FaceApp: Pygame init failed ({exc}), "
                             "falling back to Tkinter")
                self._viewport = None
                self.face.pack(fill="both", expand=True)
        else:
            self.face.pack(fill="both", expand=True)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"+{screen_w - REF_W - 30}+{screen_h - REF_H - 60}")

    def speak(self, text: str, chars_per_sec: float = 12.0):
        self.face.speak(text, chars_per_sec)

    def set_emotion(self, emotion: str):
        self.face.set_emotion(emotion)

    def close(self):
        self.face.stop()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def run(self):
        self.root.mainloop()

    def _on_drag_start(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag_motion(self, event):
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")


def main():
    import sys
    use_pygame = "--tk" not in sys.argv
    app = FaceApp(use_pygame=use_pygame)

    def _demo():
        time.sleep(2.5)
        app.speak("Hello! I am OnyxKraken.", chars_per_sec=10)
        time.sleep(3.5)
        app.speak("Your autonomous desktop agent.", chars_per_sec=11)
        time.sleep(4)
        app.speak("I can see your screen and help you with tasks.", chars_per_sec=12)
        time.sleep(5)
        app.speak("Drag me around. Right click or press Escape to close.", chars_per_sec=11)

    threading.Thread(target=_demo, daemon=True).start()
    app.run()


if __name__ == "__main__":
    main()
