"""Robot Body Window — transparent overlay that attaches below the Face GUI.

Creates a borderless window displaying the robot body image positioned just
below the head/face window.  Tracks the parent window position in real-time
and hides when the parent is maximized.

Features:
  - Per-pixel alpha via Win32 ``UpdateLayeredWindow``.
  - Z-order: body always stays **behind** the face window.
  - Power button: clicking the chest icon triggers sleep mode.
  - Cross-fade between awake and sleep body images.
  - Click anywhere on the sleeping body to wake Onyx up.

Usage:
    body = BodyWindow(root, face_canvas=face)
    body.attach()
"""

import logging
import os
import sys as _sys
import threading
import time
import tkinter as tk
from typing import Callable, Optional

_log = logging.getLogger("face.body")

# Win32 transparent overlay APIs — Windows only
_HAS_WIN32 = _sys.platform == "win32"
if _HAS_WIN32:
    import ctypes
    import ctypes.wintypes as wt
else:
    ctypes = None  # type: ignore
    wt = None      # type: ignore

# How many pixels of overlap between the bottom of the head window and the
# top of the body image (so the neck seam is hidden).
_DEFAULT_NECK_OVERLAP = 30

# Poll interval in ms for tracking the parent window position.
_POLL_MS = 33  # ~30 fps

# Cross-fade duration in seconds
_FADE_DURATION = 1.0
_FADE_FPS = 30

# ---------------------------------------------------------------------------
# Sound effects (winsound.Beep — zero dependency)
# ---------------------------------------------------------------------------
_IS_WINDOWS = _sys.platform == "win32"

def _play_sfx(notes):
    """Play a sequence of (freq_hz, duration_ms) beeps in a background thread."""
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
    """Descending power-down sweep."""
    _play_sfx([(800, 60), (600, 70), (400, 80), (250, 120), (150, 180)])

def _sfx_power_up():
    """Ascending power-up sweep with bright finish."""
    _play_sfx([(200, 80), (350, 60), (500, 60), (700, 60), (900, 50), (1200, 80)])

# Power button hit-box (fractions of the cropped body image).
# Covers the circular power icon in the center-upper chest.
_POWER_BTN_X0 = 0.38
_POWER_BTN_X1 = 0.62
_POWER_BTN_Y0 = 0.12
_POWER_BTN_Y1 = 0.42

# ---------------------------------------------------------------------------
# Win32 constants & structures
# ---------------------------------------------------------------------------
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
ULW_ALPHA = 0x02
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
SWP_NOACTIVATE = 0x0010
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
HWND_TOPMOST = wt.HWND(-1)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

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
user32.GetDC.argtypes = [wt.HWND]
user32.GetDC.restype = wt.HDC
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.ReleaseDC.restype = ctypes.c_int
user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
user32.GetCursorPos.restype = wt.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short

# GDI32 function signatures (prevent ctypes overflow on 64-bit)
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateDIBSection.argtypes = [
    wt.HDC, ctypes.c_void_p, wt.UINT,
    ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD,
]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteObject.restype = wt.BOOL
gdi32.DeleteDC.argtypes = [wt.HDC]
gdi32.DeleteDC.restype = wt.BOOL

user32.UpdateLayeredWindow.argtypes = [
    wt.HWND, wt.HDC, ctypes.c_void_p, ctypes.c_void_p,
    wt.HDC, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p, wt.DWORD,
]
user32.UpdateLayeredWindow.restype = wt.BOOL


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


class _SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


# ---------------------------------------------------------------------------
# Helper: crop whitespace from an RGBA image
# ---------------------------------------------------------------------------

def _crop_content(img):
    """Crop transparent / white whitespace from a PIL RGBA image."""
    import numpy as np
    arr = np.array(img)
    opaque = arr[:, :, 3] > 64
    not_white = (arr[:, :, 0] < 240) | (arr[:, :, 1] < 240) | (arr[:, :, 2] < 240)
    content = opaque & not_white
    rows = np.any(content, axis=1)
    cols = np.any(content, axis=0)
    if not rows.any():
        return img
    h, w = arr.shape[:2]
    top = max(0, int(np.argmax(rows)) - 4)
    bot = min(h, int(h - np.argmax(rows[::-1])) + 4)
    left = max(0, int(np.argmax(cols)) - 4)
    right = min(w, int(w - np.argmax(cols[::-1])) + 4)
    return img.crop((left, top, right, bot))


# ---------------------------------------------------------------------------
# Helper: RGBA PIL image → premultiplied BGRA bytes (bottom-up DIB)
# ---------------------------------------------------------------------------

def _rgba_to_bgra_bytes(img):
    """Convert a PIL RGBA image to premultiplied-alpha BGRA byte buffer."""
    import numpy as np
    arr = np.array(img)
    h, w = arr.shape[:2]
    alpha = arr[:, :, 3].astype(np.float32) / 255.0
    bgra = np.empty((h, w, 4), dtype=np.uint8)
    bgra[:, :, 0] = (arr[:, :, 2] * alpha).astype(np.uint8)
    bgra[:, :, 1] = (arr[:, :, 1] * alpha).astype(np.uint8)
    bgra[:, :, 2] = (arr[:, :, 0] * alpha).astype(np.uint8)
    bgra[:, :, 3] = arr[:, :, 3]
    bgra = bgra[::-1].copy()  # flip for bottom-up DIB
    return bgra.tobytes(), w, h


# ---------------------------------------------------------------------------
# BodyWindow
# ---------------------------------------------------------------------------

class BodyWindow:
    """Transparent companion window showing the robot body below the face.

    Args:
        parent: The tk root (or Toplevel) whose position we track.
        face_canvas: Optional FaceCanvas for triggering sleep/wake emotions.
        image_path: Awake body PNG path.  Defaults to ``data/body.png``.
        sleep_image_path: Sleep body PNG.  Defaults to ``data/body_sleep.png``.
        neck_overlap: Pixels to overlap with the parent bottom edge.
        on_sleep: Optional callback when Onyx enters sleep.
        on_wake: Optional callback when Onyx wakes up.
    """

    def __init__(
        self,
        parent: tk.Tk,
        face_canvas=None,
        image_path: str = "",
        sleep_image_path: str = "",
        neck_overlap: int = _DEFAULT_NECK_OVERLAP,
        on_sleep: Optional[Callable] = None,
        on_wake: Optional[Callable] = None,
    ):
        self._parent = parent
        self._face = face_canvas
        self._neck_overlap = neck_overlap
        self._on_sleep = on_sleep
        self._on_wake = on_wake
        self._hwnd = None
        self._parent_hwnd = None
        self._attached = False
        self._poll_id: Optional[str] = None
        self._visible = True
        self._user_hidden = False
        self._last_parent_geo = ""
        self._rendered_w = 0
        self._rendered_h = 0
        self._body_x = 0  # screen coords of body top-left
        self._body_y = 0

        # Adjustable scale and offset (for settings panel)
        self._scale = 1.0       # body width = parent_width * scale
        self._offset_x = 0      # horizontal pixel offset
        self._offset_y = 0      # vertical pixel offset

        self._win: Optional[tk.Toplevel] = None

        # Sleep state
        self._sleeping = False
        self._fading = False
        self._click_cooldown = 0.0

        # Resolve paths
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data",
        )
        self._image_path = image_path or os.path.join(data_dir, "body.png")
        self._sleep_image_path = sleep_image_path or os.path.join(data_dir, "body_sleep.png")

        # PIL images (loaded lazily)
        self._img_awake = None   # cropped RGBA
        self._img_sleep = None   # cropped RGBA (resized to match awake)
        self._img_current = None # what's currently displayed
        self._img_w = 0
        self._img_h = 0

    # ------------------------------------------------------------------
    # Image loading
    # ------------------------------------------------------------------

    def _load_images(self):
        """Load awake and sleep body PNGs."""
        try:
            from PIL import Image
        except ImportError:
            _log.error("Pillow not installed — body window disabled")
            return False

        if not os.path.isfile(self._image_path):
            _log.warning("Body image not found: %s", self._image_path)
            return False

        self._img_awake = _crop_content(Image.open(self._image_path).convert("RGBA"))
        self._img_w, self._img_h = self._img_awake.size
        self._img_current = self._img_awake

        # Load sleep image (optional — graceful fallback)
        if os.path.isfile(self._sleep_image_path):
            raw = _crop_content(Image.open(self._sleep_image_path).convert("RGBA"))
            self._img_sleep = raw.resize((self._img_w, self._img_h), Image.LANCZOS)
            _log.info("Sleep body image loaded")
        else:
            _log.warning("Sleep body image not found: %s", self._sleep_image_path)
            self._img_sleep = self._img_awake  # fallback

        _log.info("Body images loaded: %dx%d", self._img_w, self._img_h)
        return True

    # ------------------------------------------------------------------
    # Window creation
    # ------------------------------------------------------------------

    def _create_window(self):
        if self._win is not None:
            return

        self._win = tk.Toplevel(self._parent)
        self._win.overrideredirect(True)
        self._win.geometry("1x1+0+0")
        self._win.update_idletasks()

        # Get HWNDs
        self._hwnd = int(self._win.wm_frame(), 16)
        if not self._hwnd:
            frame_id = self._win.winfo_id()
            self._hwnd = user32.GetParent(frame_id) or frame_id

        # Get parent HWND for z-ordering
        parent_frame = self._parent.winfo_id()
        self._parent_hwnd = user32.GetParent(parent_frame) or parent_frame

        # Set layered + tool window (no taskbar icon)
        style = user32.GetWindowLongW(wt.HWND(self._hwnd), GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW
        user32.SetWindowLongW(wt.HWND(self._hwnd), GWL_EXSTYLE, style)

        _log.info("Body window created (HWND=%#x, parent HWND=%#x)",
                  self._hwnd, self._parent_hwnd)

    # ------------------------------------------------------------------
    # Rendering via UpdateLayeredWindow
    # ------------------------------------------------------------------

    def _paint_image(self, pil_rgba, target_width: int):
        """Scale and paint an RGBA image via UpdateLayeredWindow."""
        if pil_rgba is None or self._hwnd is None:
            return

        from PIL import Image

        aspect = self._img_h / max(self._img_w, 1)
        tw = max(target_width, 50)
        th = max(int(tw * aspect), 50)

        scaled = pil_rgba.resize((tw, th), Image.LANCZOS)
        bits, bw, bh = _rgba_to_bgra_bytes(scaled)

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = bw
        bmi.biHeight = bh
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0
        bmi.biSizeImage = len(bits)

        hdc_screen = user32.GetDC(wt.HWND(0))
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)

        ppvBits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(
            hdc_mem, ctypes.byref(bmi), 0,
            ctypes.byref(ppvBits), None, 0,
        )
        if not hbmp:
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(wt.HWND(0), hdc_screen)
            return

        ctypes.memmove(ppvBits, bits, len(bits))
        old_bmp = gdi32.SelectObject(hdc_mem, hbmp)

        sz = _SIZE(tw, th)
        pt_src = _POINT(0, 0)
        blend = _BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)

        user32.UpdateLayeredWindow(
            wt.HWND(self._hwnd), hdc_screen, None,
            ctypes.byref(sz), hdc_mem, ctypes.byref(pt_src),
            0, ctypes.byref(blend), ULW_ALPHA,
        )

        gdi32.SelectObject(hdc_mem, old_bmp)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(wt.HWND(0), hdc_screen)

        self._rendered_w = tw
        self._rendered_h = th

    def _render_current(self, target_width: int):
        """Render the current body image."""
        self._paint_image(self._img_current, target_width)

    # ------------------------------------------------------------------
    # Cross-fade between awake ↔ sleep
    # ------------------------------------------------------------------

    def _crossfade(self, from_img, to_img, on_done=None):
        """Run a smooth cross-fade in a background thread."""
        if self._fading:
            return
        self._fading = True

        def _fade():
            from PIL import Image
            steps = int(_FADE_DURATION * _FADE_FPS)
            for i in range(steps + 1):
                if not self._attached:
                    break
                t = i / max(steps, 1)
                blended = Image.blend(from_img, to_img, t)
                self._img_current = blended
                # Schedule paint on main thread
                try:
                    self._parent.after(0, lambda img=blended: self._paint_image(img, self._rendered_w))
                except tk.TclError:
                    break
                time.sleep(1.0 / _FADE_FPS)

            self._img_current = to_img
            self._fading = False
            if on_done:
                try:
                    self._parent.after(0, on_done)
                except tk.TclError:
                    pass

        threading.Thread(target=_fade, daemon=True).start()

    # ------------------------------------------------------------------
    # Click detection (polled — works even with UpdateLayeredWindow)
    # ------------------------------------------------------------------

    def _check_click(self):
        """Check if LMB was pressed inside the body window bounds."""
        if not self._attached or self._hwnd is None:
            return
        if self._fading:
            self._parent.after(100, self._check_click)
            return

        VK_LBUTTON = 0x01
        state = user32.GetAsyncKeyState(VK_LBUTTON)
        # Bit 0 = pressed since last query
        if state & 1:
            now = time.time()
            if now - self._click_cooldown < 0.4:
                self._parent.after(50, self._check_click)
                return
            pt = wt.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            mx, my = pt.x, pt.y

            # Check if inside body window
            bx, by = self._body_x, self._body_y
            bw, bh = self._rendered_w, self._rendered_h
            if bx <= mx < bx + bw and by <= my < by + bh:
                # Relative coords (0-1)
                rx = (mx - bx) / max(bw, 1)
                ry = (my - by) / max(bh, 1)

                if self._sleeping:
                    # Any click wakes up
                    self._click_cooldown = now
                    self._wake()
                else:
                    # Check power button region
                    if (_POWER_BTN_X0 <= rx <= _POWER_BTN_X1 and
                            _POWER_BTN_Y0 <= ry <= _POWER_BTN_Y1):
                        self._click_cooldown = now
                        self._sleep()

                # Always re-assert z-order: body behind parent after any click
                self._push_behind_parent()

        self._parent.after(50, self._check_click)

    # ------------------------------------------------------------------
    # Sleep / Wake
    # ------------------------------------------------------------------

    def _push_behind_parent(self):
        """Force body window behind the parent in z-order."""
        if self._hwnd and self._parent_hwnd:
            user32.SetWindowPos(
                wt.HWND(self._hwnd),
                wt.HWND(self._parent_hwnd),
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )

    def _sleep(self):
        """Power off: face → sleep, body → sleep image."""
        if self._sleeping or self._fading:
            return
        self._sleeping = True
        _log.info("Onyx entering sleep mode")

        _sfx_power_down()

        # Face sleep transition
        if self._face:
            self._face.set_emotion("sleep")
            self._face.set_idle(False)

        # Cross-fade body to sleep image
        self._crossfade(self._img_awake, self._img_sleep)

        if self._on_sleep:
            self._on_sleep()

    def _wake(self):
        """Wake up: face → neutral, body → awake image."""
        if not self._sleeping or self._fading:
            return
        self._sleeping = False
        _log.info("Onyx waking up")

        _sfx_power_up()

        # Face wake transition
        if self._face:
            self._face.set_emotion("neutral")
            self._face.set_idle(True)

        # Cross-fade body back to awake
        self._crossfade(self._img_sleep, self._img_awake)

        if self._on_wake:
            self._on_wake()

    # ------------------------------------------------------------------
    # Position tracking
    # ------------------------------------------------------------------

    def _poll_position(self):
        if not self._attached or self._hwnd is None:
            return

        try:
            if not self._parent.winfo_exists():
                self.detach()
                return

            # Detect window state
            try:
                state = self._parent.state()
            except tk.TclError:
                state = "normal"

            # Hide when minimized or maximized
            if state in ("zoomed", "iconic"):
                if self._visible:
                    user32.ShowWindow(wt.HWND(self._hwnd), 0)  # SW_HIDE
                    self._visible = False
                self._poll_id = self._parent.after(_POLL_MS, self._poll_position)
                return

            # Restore visibility when parent comes back to normal
            # (only if not explicitly hidden by user via "Show Body" toggle)
            if not self._visible and state == "normal" and not self._user_hidden:
                user32.ShowWindow(wt.HWND(self._hwnd), 8)  # SW_SHOWNA
                self._visible = True
                self._last_parent_geo = ""  # force full reposition

            px = self._parent.winfo_rootx()
            py = self._parent.winfo_rooty()
            pw = self._parent.winfo_width()
            ph = self._parent.winfo_height()

            # Skip if parent reports garbage geometry (during transitions)
            if pw < 10 or ph < 10:
                self._poll_id = self._parent.after(_POLL_MS, self._poll_position)
                return

            geo = f"{px},{py},{pw},{ph}"

            if geo != self._last_parent_geo:
                self._last_parent_geo = geo

                # Re-render at new width if resized
                scaled_w = int(pw * self._scale)
                if self._rendered_w != scaled_w and scaled_w > 50:
                    self._render_current(scaled_w)

                bx = px + (pw - self._rendered_w) // 2 + self._offset_x
                by = py + ph - self._neck_overlap + self._offset_y
                self._body_x = bx
                self._body_y = by

                # Position body BEHIND the parent window.
                user32.SetWindowPos(
                    wt.HWND(self._hwnd),
                    wt.HWND(self._parent_hwnd),
                    bx, by,
                    self._rendered_w, self._rendered_h,
                    SWP_NOACTIVATE,
                )

            # Always re-assert z-order on every tick (handles clicks
            # that may have brought the body in front of parent).
            self._push_behind_parent()

        except (tk.TclError, OSError) as e:
            # Don't detach — just skip this tick and keep polling
            _log.debug("Body poll error (will retry): %s", e)

        self._poll_id = self._parent.after(_POLL_MS, self._poll_position)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def attach(self):
        """Load images, create window, and start tracking the parent."""
        if self._attached:
            return

        if self._img_awake is None:
            if not self._load_images():
                return

        self._create_window()
        self._parent.update_idletasks()

        pw = self._parent.winfo_width()
        if pw < 50:
            pw = 400
        scaled_w = int(pw * self._scale)
        self._render_current(scaled_w)

        # Initial position behind parent
        px = self._parent.winfo_rootx()
        py = self._parent.winfo_rooty()
        ph = self._parent.winfo_height()
        bx = px + (pw - self._rendered_w) // 2 + self._offset_x
        by = py + ph - self._neck_overlap + self._offset_y
        self._body_x = bx
        self._body_y = by

        user32.SetWindowPos(
            wt.HWND(self._hwnd),
            wt.HWND(self._parent_hwnd),
            bx, by,
            self._rendered_w, self._rendered_h,
            SWP_NOACTIVATE,
        )
        user32.ShowWindow(wt.HWND(self._hwnd), 8)

        self._attached = True
        self._visible = True
        self._user_hidden = False
        self._last_parent_geo = ""
        self._poll_position()
        self._check_click()  # start click detection
        _log.info("Body window attached (behind parent)")

    def detach(self):
        self._attached = False
        if self._poll_id and self._parent.winfo_exists():
            try:
                self._parent.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None

        if self._win is not None:
            try:
                self._win.destroy()
            except tk.TclError:
                pass
            self._win = None
            self._hwnd = None
        _log.info("Body window detached")

    def set_visible(self, visible: bool):
        if self._hwnd is None:
            return
        self._user_hidden = not visible
        if visible and not self._visible:
            user32.ShowWindow(wt.HWND(self._hwnd), 8)
            self._visible = True
        elif not visible and self._visible:
            user32.ShowWindow(wt.HWND(self._hwnd), 0)
            self._visible = False

    # ------------------------------------------------------------------
    # Real-time adjustment
    # ------------------------------------------------------------------

    def set_scale(self, scale: float):
        """Set body scale (1.0 = same width as parent)."""
        self._scale = max(0.3, min(2.0, scale))
        self._last_parent_geo = ""  # force re-render next tick

    def set_offset(self, dx: int = 0, dy: int = 0):
        """Set pixel offset from default centered-below position."""
        self._offset_x = dx
        self._offset_y = dy
        self._last_parent_geo = ""

    def adjust_scale(self, delta: float):
        """Incrementally adjust scale."""
        self.set_scale(self._scale + delta)

    def adjust_offset(self, ddx: int = 0, ddy: int = 0):
        """Incrementally adjust offset."""
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
