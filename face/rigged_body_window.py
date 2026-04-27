"""Rigged Body Window — transparent overlay with procedural RobotBody.

Replaces the old image-based BodyWindow with a live, animated procedural
robot body drawn via character_body_v2.RobotBody.  The body is rendered
on a tk.Canvas inside a borderless Toplevel with chroma-key transparency
(Windows ``-transparentcolor``).

The window tracks the parent face window position, stays behind it in
z-order, and runs a ~30 fps render loop for breathing, idle sway, BPM
head-nod, and pose transitions.

Features:
  - Full procedural robot: torso, arms, legs, hands, feet, neck, joints
  - Emotion → pose mapping (happy → excited, thinking → arm raised, etc.)
  - BPM head-nod sync (for DJ mode)
  - Sleep/wake with pose transitions + sound effects
  - Power button click region on the chest
  - Identical public API to the old BodyWindow (drop-in replacement)

Usage:
    body = RiggedBodyWindow(root, face_canvas=face)
    body.attach()
"""

import logging
import math
import sys as _sys
import threading
import time
import tkinter as tk
from typing import Callable, Optional

_log = logging.getLogger("face.rigged_body")

# Win32 transparent overlay APIs — Windows only
_HAS_WIN32 = _sys.platform == "win32"
if _HAS_WIN32:
    import ctypes
    import ctypes.wintypes as wt
else:
    ctypes = None  # type: ignore
    wt = None      # type: ignore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POLL_MS = 33          # ~30 fps position tracking
_RENDER_MS = 33        # ~30 fps body animation
_DEFAULT_NECK_OVERLAP = 60

# Chroma key — this exact color becomes transparent.
# Using a very specific off-color that won't appear in the robot design.
_CHROMA_KEY = "#010301"

_IS_WINDOWS = _sys.platform == "win32"

# Power button hit-box (fractions of the canvas area)
_POWER_BTN_X0 = 0.35
_POWER_BTN_X1 = 0.65
_POWER_BTN_Y0 = 0.15
_POWER_BTN_Y1 = 0.45

# ---------------------------------------------------------------------------
# Win32 helpers (same as body_window.py)
# ---------------------------------------------------------------------------

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
SWP_NOACTIVATE = 0x0010
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001

if _IS_WINDOWS:
    user32 = ctypes.windll.user32
    user32.SetWindowPos.argtypes = [
        wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wt.UINT,
    ]
    user32.SetWindowPos.restype = wt.BOOL
    user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wt.BOOL
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
    user32.GetCursorPos.restype = wt.BOOL
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short

# ---------------------------------------------------------------------------
# Sound effects (winsound.Beep — zero dependency)
# ---------------------------------------------------------------------------

def _play_sfx(notes):
    if not _IS_WINDOWS:
        return
    def _worker():
        import winsound
        try:
            for freq, dur in notes:
                winsound.Beep(freq, dur)
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()

def _sfx_power_down():
    _play_sfx([(800, 60), (600, 70), (400, 80), (250, 120), (150, 180)])

def _sfx_power_up():
    _play_sfx([(200, 80), (350, 60), (500, 60), (700, 60), (900, 50), (1200, 80)])

# ---------------------------------------------------------------------------
# Onyx theme colors for the body
# ---------------------------------------------------------------------------

_ONYX_BODY_COLORS = {
    "primary": "#00d4ff",
    "secondary": "#0088aa",
    "dark": "#004455",
}

# Sleep colors — dimmed version
_SLEEP_BODY_COLORS = {
    "primary": "#004466",
    "secondary": "#002233",
    "dark": "#001122",
}


# ---------------------------------------------------------------------------
# RiggedBodyWindow
# ---------------------------------------------------------------------------

class RiggedBodyWindow:
    """Transparent overlay window with a live procedural robot body.

    Drop-in replacement for BodyWindow — same public API.

    Args:
        parent: The tk root whose position we track.
        face_canvas: Optional FaceCanvas for triggering sleep/wake emotions.
        neck_overlap: Pixels to overlap with the parent bottom edge.
        body_style: RobotBody body style (standard, slim, angular, etc.).
        on_sleep: Optional callback when Onyx enters sleep.
        on_wake: Optional callback when Onyx wakes up.
    """

    def __init__(
        self,
        parent: tk.Tk,
        face_canvas=None,
        neck_overlap: int = _DEFAULT_NECK_OVERLAP,
        body_style: str = "standard",
        on_sleep: Optional[Callable] = None,
        on_wake: Optional[Callable] = None,
        # Legacy compat — ignored (no image files needed)
        image_path: str = "",
        sleep_image_path: str = "",
    ):
        self._parent = parent
        self._face = face_canvas
        self._neck_overlap = neck_overlap
        self._body_style = body_style
        self._on_sleep = on_sleep
        self._on_wake = on_wake

        self._win: Optional[tk.Toplevel] = None
        self._canvas: Optional[tk.Canvas] = None
        self._body = None  # RobotBody instance

        self._attached = False
        self._visible = True
        self._sleeping = False
        self._click_cooldown = 0.0

        # Window tracking
        self._hwnd = None
        self._parent_hwnd = None
        self._poll_id: Optional[str] = None
        self._render_id: Optional[str] = None
        self._last_parent_geo = ""
        self._last_render_time = time.time()

        # Body position on screen
        self._body_x = 0
        self._body_y = 0
        self._canvas_w = 300
        self._canvas_h = 400

        # Adjustable scale and offset
        self._scale = 1.0
        self._offset_x = 0
        self._offset_y = 0

    # ------------------------------------------------------------------
    # Window creation
    # ------------------------------------------------------------------

    def _create_window(self):
        if self._win is not None:
            return

        self._win = tk.Toplevel(self._parent)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", False)

        # Chroma-key transparency (Windows)
        if _IS_WINDOWS:
            self._win.attributes("-transparentcolor", _CHROMA_KEY)

        # No taskbar icon
        self._win.wm_attributes("-toolwindow", True)

        # Create canvas
        self._canvas = tk.Canvas(
            self._win,
            bg=_CHROMA_KEY,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(fill="both", expand=True)

        # Create the RobotBody
        from face.stage.character_body_v2 import RobotBody
        self._body = RobotBody(
            self._canvas,
            _ONYX_BODY_COLORS.copy(),
            body_style=self._body_style,
        )

        # Get window handle for z-ordering
        self._win.update_idletasks()
        self._hwnd = int(self._win.wm_frame(), 16)
        if not self._hwnd:
            frame_id = self._win.winfo_id()
            self._hwnd = user32.GetParent(frame_id) or frame_id

        parent_frame = self._parent.winfo_id()
        self._parent_hwnd = user32.GetParent(parent_frame) or parent_frame

        # Remove WS_EX_TOPMOST, add WS_EX_TOOLWINDOW
        if _IS_WINDOWS:
            style = user32.GetWindowLongW(wt.HWND(self._hwnd), GWL_EXSTYLE)
            style |= WS_EX_TOOLWINDOW
            user32.SetWindowLongW(wt.HWND(self._hwnd), GWL_EXSTYLE, style)

        _log.info("Rigged body window created (HWND=%#x)", self._hwnd)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self):
        """Clear and redraw the body on the canvas."""
        if not self._attached or self._canvas is None or self._body is None:
            return

        now = time.time()
        dt = now - self._last_render_time
        self._last_render_time = now

        # Animate
        self._body.animate_breathing(dt)
        self._body.animate_idle(dt)
        self._body.update_animation(dt)

        # Clear previous frame
        self._canvas.delete("body")

        # Calculate draw position and scale
        # Body center is at middle-X; neck starts at top of canvas
        # so it overlaps into the face window's bottom edge
        cx = self._canvas_w // 2
        cy = int(self._canvas_h * 0.18)  # torso center near top (neck overlaps face)
        body_scale = self._canvas_w / 300.0  # normalize to ~300px reference

        self._body.draw(cx, cy, scale=body_scale, facing="front")

        # Schedule next frame
        self._render_id = self._parent.after(_RENDER_MS, self._render)

    # ------------------------------------------------------------------
    # Position tracking
    # ------------------------------------------------------------------

    def _push_behind_parent(self):
        if _IS_WINDOWS and self._hwnd and self._parent_hwnd:
            user32.SetWindowPos(
                wt.HWND(self._hwnd),
                wt.HWND(self._parent_hwnd),
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )

    def _poll_position(self):
        if not self._attached or self._hwnd is None:
            return

        try:
            if not self._parent.winfo_exists():
                self.detach()
                return

            try:
                state = self._parent.state()
            except tk.TclError:
                state = "normal"

            # Hide when minimized or maximized
            if state in ("zoomed", "iconic"):
                if self._visible:
                    if _IS_WINDOWS:
                        user32.ShowWindow(wt.HWND(self._hwnd), 0)
                    self._visible = False
                self._poll_id = self._parent.after(_POLL_MS, self._poll_position)
                return

            if not self._visible and state == "normal":
                if _IS_WINDOWS:
                    user32.ShowWindow(wt.HWND(self._hwnd), 8)
                self._visible = True
                self._last_parent_geo = ""

            px = self._parent.winfo_rootx()
            py = self._parent.winfo_rooty()
            pw = self._parent.winfo_width()
            ph = self._parent.winfo_height()

            if pw < 10 or ph < 10:
                self._poll_id = self._parent.after(_POLL_MS, self._poll_position)
                return

            geo = f"{px},{py},{pw},{ph}"

            if geo != self._last_parent_geo:
                self._last_parent_geo = geo

                # Size the body canvas proportional to the parent
                self._canvas_w = max(int(pw * self._scale), 100)
                self._canvas_h = max(int(self._canvas_w * 1.4), 150)

                bx = px + (pw - self._canvas_w) // 2 + self._offset_x
                by = py + ph - self._neck_overlap + self._offset_y
                self._body_x = bx
                self._body_y = by

                self._win.geometry(
                    f"{self._canvas_w}x{self._canvas_h}+{bx}+{by}"
                )

                if _IS_WINDOWS:
                    user32.SetWindowPos(
                        wt.HWND(self._hwnd),
                        wt.HWND(self._parent_hwnd),
                        bx, by,
                        self._canvas_w, self._canvas_h,
                        SWP_NOACTIVATE,
                    )

            self._push_behind_parent()

        except (tk.TclError, OSError) as e:
            _log.debug("Rigged body poll error (will retry): %s", e)

        self._poll_id = self._parent.after(_POLL_MS, self._poll_position)

    # ------------------------------------------------------------------
    # Click detection
    # ------------------------------------------------------------------

    def _check_click(self):
        if not self._attached or not _IS_WINDOWS:
            return

        VK_LBUTTON = 0x01
        state = user32.GetAsyncKeyState(VK_LBUTTON)
        if state & 1:
            now = time.time()
            if now - self._click_cooldown < 0.4:
                self._parent.after(50, self._check_click)
                return
            pt = wt.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            mx, my = pt.x, pt.y

            bx, by = self._body_x, self._body_y
            bw, bh = self._canvas_w, self._canvas_h
            if bx <= mx < bx + bw and by <= my < by + bh:
                rx = (mx - bx) / max(bw, 1)
                ry = (my - by) / max(bh, 1)

                if self._sleeping:
                    self._click_cooldown = now
                    self._wake()
                else:
                    if (_POWER_BTN_X0 <= rx <= _POWER_BTN_X1 and
                            _POWER_BTN_Y0 <= ry <= _POWER_BTN_Y1):
                        self._click_cooldown = now
                        self._sleep()

                self._push_behind_parent()

        self._parent.after(50, self._check_click)

    # ------------------------------------------------------------------
    # Sleep / Wake
    # ------------------------------------------------------------------

    def _sleep(self):
        if self._sleeping:
            return
        self._sleeping = True
        _log.info("Onyx entering sleep mode (rigged body)")

        _sfx_power_down()

        if self._face:
            self._face.set_emotion("sleep")
            self._face.set_idle(False)

        # Dim the body colors and set relaxed pose
        if self._body:
            self._body.colors = _SLEEP_BODY_COLORS.copy()
            self._body.set_pose("relaxed", smooth=True)

        if self._on_sleep:
            self._on_sleep()

    def _wake(self):
        if not self._sleeping:
            return
        self._sleeping = False
        _log.info("Onyx waking up (rigged body)")

        _sfx_power_up()

        if self._face:
            self._face.set_emotion("neutral")
            self._face.set_idle(True)

        # Restore body colors and neutral pose
        if self._body:
            self._body.colors = _ONYX_BODY_COLORS.copy()
            self._body.set_pose("neutral", smooth=True)

        if self._on_wake:
            self._on_wake()

    # ------------------------------------------------------------------
    # Public API (matches BodyWindow interface)
    # ------------------------------------------------------------------

    def attach(self):
        """Create the window and start tracking + rendering."""
        if self._attached:
            return

        self._create_window()
        self._parent.update_idletasks()

        pw = self._parent.winfo_width()
        if pw < 50:
            pw = 400

        self._canvas_w = max(int(pw * self._scale), 100)
        self._canvas_h = max(int(self._canvas_w * 1.4), 150)

        # Initial position
        px = self._parent.winfo_rootx()
        py = self._parent.winfo_rooty()
        ph = self._parent.winfo_height()
        bx = px + (pw - self._canvas_w) // 2 + self._offset_x
        by = py + ph - self._neck_overlap + self._offset_y
        self._body_x = bx
        self._body_y = by

        self._win.geometry(f"{self._canvas_w}x{self._canvas_h}+{bx}+{by}")

        if _IS_WINDOWS:
            user32.SetWindowPos(
                wt.HWND(self._hwnd),
                wt.HWND(self._parent_hwnd),
                bx, by,
                self._canvas_w, self._canvas_h,
                SWP_NOACTIVATE,
            )
            user32.ShowWindow(wt.HWND(self._hwnd), 8)

        self._attached = True
        self._visible = True
        self._last_parent_geo = ""
        self._last_render_time = time.time()

        self._poll_position()
        self._render()
        self._check_click()
        _log.info("Rigged body window attached (behind parent)")

    def detach(self):
        self._attached = False
        for aid in (self._poll_id, self._render_id):
            if aid and self._parent.winfo_exists():
                try:
                    self._parent.after_cancel(aid)
                except Exception:
                    pass
        self._poll_id = None
        self._render_id = None

        if self._win is not None:
            try:
                self._win.destroy()
            except tk.TclError:
                pass
            self._win = None
            self._canvas = None
            self._body = None
            self._hwnd = None
        _log.info("Rigged body window detached")

    def set_visible(self, visible: bool):
        if not _IS_WINDOWS or self._hwnd is None:
            return
        if visible and not self._visible:
            user32.ShowWindow(wt.HWND(self._hwnd), 8)
            self._visible = True
        elif not visible and self._visible:
            user32.ShowWindow(wt.HWND(self._hwnd), 0)
            self._visible = False

    def set_scale(self, scale: float):
        self._scale = max(0.3, min(2.0, scale))
        self._last_parent_geo = ""

    def set_offset(self, dx: int = 0, dy: int = 0):
        self._offset_x = dx
        self._offset_y = dy
        self._last_parent_geo = ""

    def adjust_scale(self, delta: float):
        self.set_scale(self._scale + delta)

    def adjust_offset(self, ddx: int = 0, ddy: int = 0):
        self.set_offset(self._offset_x + ddx, self._offset_y + ddy)

    @property
    def scale(self) -> float:
        return self._scale

    @property
    def offset(self) -> tuple:
        return (self._offset_x, self._offset_y)

    @property
    def is_attached(self) -> bool:
        return self._attached

    @property
    def is_visible(self) -> bool:
        return self._visible

    @property
    def is_sleeping(self) -> bool:
        return self._sleeping

    # ------------------------------------------------------------------
    # Extended API (rigged body specific)
    # ------------------------------------------------------------------

    def set_emotion(self, emotion: str):
        """Set body pose from an emotion name."""
        if self._body:
            self._body.set_emotion(emotion)

    def set_bpm(self, bpm: float, nod_amount: float = 8.0):
        """Enable BPM head-nod sync."""
        if self._body:
            self._body.set_bpm(bpm, nod_amount)

    def set_pose(self, pose: str, smooth: bool = True):
        """Set a named pose (neutral, confident, thinking, excited, dj)."""
        if self._body:
            self._body.set_pose(pose, smooth=smooth)

    def set_body_style(self, style: str):
        """Change body style (standard, slim, angular, elegant, etc.)."""
        if self._body:
            from face.stage.character_body_v2 import RobotBody
            props = RobotBody.BODY_STYLES.get(style)
            if props:
                self._body._props = props
                self._body.body_style = style
                self._body_style = style

    @property
    def robot_body(self) -> Optional[object]:
        """Direct access to the underlying RobotBody for advanced control."""
        return self._body
