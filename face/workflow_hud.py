"""Workflow HUD — floating progress panels that appear around Onyx during chain workflows.

Displays step-by-step progress, service status, narration, and timing
in translucent panels positioned to the LEFT and RIGHT of the face window,
never overlapping Onyx himself.

Architecture:
    ┌─────────────┐          ┌─────────────┐
    │  STEPS       │  [ONYX]  │  ACTIVITY    │
    │  ✓ Record    │          │  Recording.. │
    │  ▶ Music     │          │  00:32       │
    │  ○ Assemble  │          │  ████░░ 40%  │
    │  ○ Export    │          │              │
    └─────────────┘          └─────────────┘

Usage:
    hud = WorkflowHUD(root_window)
    hud.start_workflow(workflow)        # show panels + populate steps
    hud.set_step_active(1)             # highlight step index
    hud.set_step_done(0, success=True) # mark step as complete
    hud.set_activity("Generating...")  # update right panel text
    hud.set_progress(2, 5)            # update progress bar
    hud.finish(success=True)           # flash result + auto-dismiss
"""

import logging
import math
import threading
import time
import tkinter as tk
from typing import Optional

_log = logging.getLogger("face.workflow_hud")

# ---------------------------------------------------------------------------
# Theme — matches Onyx dark palette
# ---------------------------------------------------------------------------

HUD_BG = "#060a10"
HUD_BG_PANEL = "#080e18"
HUD_BORDER = "#0e2a3d"
HUD_ACCENT = "#00e5ff"
HUD_ACCENT_DIM = "#005566"
HUD_TEXT = "#c0d0e0"
HUD_TEXT_DIM = "#5a6a7a"
HUD_TEXT_VDIM = "#3a4a5a"
HUD_SUCCESS = "#00e676"
HUD_ERROR = "#ff5252"
HUD_WARNING = "#ffab40"
HUD_STEP_ACTIVE_BG = "#0a1e30"
HUD_STEP_DONE_BG = "#081a14"
HUD_STEP_FAIL_BG = "#1a0a0a"
HUD_PROGRESS_BG = "#0c1220"
HUD_PROGRESS_FG = "#00e5ff"
HUD_GLOW = "#00e5ff"

# Panel dimensions
PANEL_W = 220
PANEL_MIN_H = 180
PANEL_GAP = 16          # gap between panel edge and Onyx window
PANEL_PAD = 12          # internal padding
PANEL_CORNER = 8
TITLE_FONT = ("Consolas", 10, "bold")
STEP_FONT = ("Consolas", 9)
STEP_FONT_SMALL = ("Consolas", 8)
ACTIVITY_FONT = ("Consolas", 9)
TIMER_FONT = ("Consolas", 18, "bold")
PROGRESS_H = 6


# ---------------------------------------------------------------------------
# Step status icons
# ---------------------------------------------------------------------------

ICON_PENDING = "○"
ICON_ACTIVE = "▶"
ICON_DONE = "✓"
ICON_FAIL = "✗"
ICON_SKIP = "–"


# ---------------------------------------------------------------------------
# WorkflowHUD
# ---------------------------------------------------------------------------

class WorkflowHUD:
    """Floating HUD panels that orbit Onyx during chain workflow execution."""

    def __init__(self, root: tk.Tk):
        self._root = root
        self._left_win: Optional[tk.Toplevel] = None
        self._right_win: Optional[tk.Toplevel] = None
        self._visible = False
        self._workflow_id = ""
        self._steps: list[dict] = []       # {name, id, status, label_widget, icon_widget}
        self._active_index = -1
        self._start_time = 0.0
        self._timer_id = None
        self._pulse_id = None
        self._pulse_phase = 0
        self._progress_cur = 0
        self._progress_total = 0
        self._finished = False

        # Widget refs (right panel)
        self._activity_label: Optional[tk.Label] = None
        self._timer_label: Optional[tk.Label] = None
        self._progress_canvas: Optional[tk.Canvas] = None
        self._narration_label: Optional[tk.Label] = None
        self._status_label: Optional[tk.Label] = None
        self._service_labels: dict[str, tk.Label] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_workflow(self, workflow_id: str, step_names: list[str],
                       step_ids: list[str] | None = None):
        """Show HUD panels and populate with workflow steps."""
        if self._visible:
            self.dismiss()

        self._workflow_id = workflow_id
        self._start_time = time.time()
        self._finished = False
        self._active_index = -1
        self._progress_cur = 0
        self._progress_total = len(step_names)

        self._steps = []
        for i, name in enumerate(step_names):
            self._steps.append({
                "name": name,
                "id": step_ids[i] if step_ids else f"step_{i}",
                "status": "pending",
                "icon_widget": None,
                "name_widget": None,
                "time_widget": None,
            })

        self._root.after(0, self._build_panels)

    def set_step_active(self, index: int):
        """Highlight a step as currently running."""
        if not self._visible or index < 0 or index >= len(self._steps):
            return
        self._active_index = index
        self._root.after(0, lambda: self._update_step_display(index, "active"))

    def set_step_done(self, index: int, success: bool = True, duration: float = 0):
        """Mark a step as completed or failed."""
        if not self._visible or index < 0 or index >= len(self._steps):
            return
        status = "done" if success else "fail"
        self._root.after(0, lambda: self._update_step_display(
            index, status, duration=duration))

    def set_step_skipped(self, index: int):
        """Mark a step as skipped."""
        if not self._visible or index < 0 or index >= len(self._steps):
            return
        self._root.after(0, lambda: self._update_step_display(index, "skip"))

    def set_activity(self, text: str):
        """Update the activity text on the right panel."""
        if self._activity_label:
            self._root.after(0, lambda t=text: self._safe_config(
                self._activity_label, text=t[:60]))

    def set_narration(self, text: str):
        """Update the narration text on the right panel."""
        if self._narration_label:
            self._root.after(0, lambda t=text: self._safe_config(
                self._narration_label, text=f'"{t[:80]}"'))

    def set_progress(self, current: int, total: int):
        """Update the progress bar."""
        self._progress_cur = current
        self._progress_total = total
        self._root.after(0, self._draw_progress)

    def set_service_status(self, name: str, running: bool):
        """Update a service status indicator."""
        lbl = self._service_labels.get(name)
        if lbl:
            color = HUD_SUCCESS if running else HUD_TEXT_DIM
            icon = "●" if running else "○"
            self._root.after(0, lambda: self._safe_config(
                lbl, text=f" {icon} {name}", fg=color))

    def finish(self, success: bool = True, message: str = ""):
        """Flash success/failure and auto-dismiss after delay."""
        self._finished = True
        if self._pulse_id:
            self._root.after_cancel(self._pulse_id)
            self._pulse_id = None

        color = HUD_SUCCESS if success else HUD_ERROR
        icon = "✓" if success else "✗"
        msg = message or ("Workflow complete" if success else "Workflow failed")

        if self._status_label:
            self._root.after(0, lambda: self._safe_config(
                self._status_label, text=f" {icon} {msg}", fg=color))

        # Flash the panels
        self._root.after(0, lambda: self._flash_panels(color))

        # Auto-dismiss after 8 seconds
        self._root.after(8000, self.dismiss)

    def dismiss(self):
        """Close all HUD panels."""
        if self._timer_id:
            self._root.after_cancel(self._timer_id)
            self._timer_id = None
        if self._pulse_id:
            self._root.after_cancel(self._pulse_id)
            self._pulse_id = None

        for win in (self._left_win, self._right_win):
            if win:
                try:
                    win.destroy()
                except Exception:
                    pass
        self._left_win = None
        self._right_win = None
        self._visible = False
        self._steps = []
        self._service_labels = {}

    @property
    def is_visible(self) -> bool:
        return self._visible

    # ------------------------------------------------------------------
    # Panel construction
    # ------------------------------------------------------------------

    def _build_panels(self):
        """Create the left (steps) and right (activity) Toplevel windows."""
        # Get face window geometry for positioning
        try:
            fx = self._root.winfo_rootx()
            fy = self._root.winfo_rooty()
            fw = self._root.winfo_width()
            fh = self._root.winfo_height()
        except Exception:
            fx, fy, fw, fh = 400, 200, 400, 386

        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()

        # Calculate panel heights based on step count
        step_count = len(self._steps)
        left_h = max(PANEL_MIN_H, 60 + step_count * 28 + 20)
        right_h = max(PANEL_MIN_H, 260)

        # Position: left panel to the left of Onyx, right panel to the right
        left_x = max(0, fx - PANEL_W - PANEL_GAP)
        right_x = min(screen_w - PANEL_W, fx + fw + PANEL_GAP)

        # Vertically center panels relative to face
        left_y = max(0, fy + (fh - left_h) // 2)
        right_y = max(0, fy + (fh - right_h) // 2)

        # Clamp to screen
        left_y = min(left_y, screen_h - left_h - 40)
        right_y = min(right_y, screen_h - right_h - 40)

        # Build left panel (steps list)
        self._left_win = self._make_panel(left_x, left_y, PANEL_W, left_h)
        self._build_steps_panel(self._left_win)

        # Build right panel (activity / details)
        self._right_win = self._make_panel(right_x, right_y, PANEL_W, right_h)
        self._build_activity_panel(self._right_win)

        self._visible = True

        # Start timer
        self._tick_timer()

        # Start glow pulse animation
        self._pulse_phase = 0
        self._pulse_glow()

    def _make_panel(self, x: int, y: int, w: int, h: int) -> tk.Toplevel:
        """Create a borderless, always-on-top Toplevel panel."""
        win = tk.Toplevel(self._root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=HUD_BG)
        win.geometry(f"{w}x{h}+{x}+{y}")

        # Attempt transparency (Windows)
        try:
            win.attributes("-alpha", 0.92)
        except Exception:
            pass

        # Border frame
        border = tk.Frame(win, bg=HUD_BORDER, padx=1, pady=1)
        border.pack(fill="both", expand=True)
        inner = tk.Frame(border, bg=HUD_BG)
        inner.pack(fill="both", expand=True)
        win._inner = inner

        return win

    def _build_steps_panel(self, win: tk.Toplevel):
        """Build the left panel showing workflow steps."""
        inner = win._inner

        # Title
        title_frame = tk.Frame(inner, bg=HUD_BG)
        title_frame.pack(fill="x", padx=PANEL_PAD, pady=(PANEL_PAD, 4))

        tk.Label(
            title_frame, text="⚡ WORKFLOW", bg=HUD_BG, fg=HUD_ACCENT,
            font=TITLE_FONT, anchor="w",
        ).pack(side="left")

        # Workflow ID subtitle
        tk.Label(
            title_frame, text=self._workflow_id.replace("_", " ").upper(),
            bg=HUD_BG, fg=HUD_TEXT_DIM, font=STEP_FONT_SMALL, anchor="e",
        ).pack(side="right")

        # Separator
        tk.Frame(inner, bg=HUD_BORDER, height=1).pack(fill="x", padx=PANEL_PAD, pady=2)

        # Steps list
        for i, step_info in enumerate(self._steps):
            row = tk.Frame(inner, bg=HUD_BG)
            row.pack(fill="x", padx=PANEL_PAD, pady=1)

            icon_lbl = tk.Label(
                row, text=ICON_PENDING, bg=HUD_BG, fg=HUD_TEXT_DIM,
                font=STEP_FONT, width=2, anchor="center",
            )
            icon_lbl.pack(side="left")

            name_lbl = tk.Label(
                row, text=step_info["name"], bg=HUD_BG, fg=HUD_TEXT_DIM,
                font=STEP_FONT, anchor="w",
            )
            name_lbl.pack(side="left", fill="x", expand=True)

            time_lbl = tk.Label(
                row, text="", bg=HUD_BG, fg=HUD_TEXT_VDIM,
                font=STEP_FONT_SMALL, anchor="e",
            )
            time_lbl.pack(side="right")

            step_info["icon_widget"] = icon_lbl
            step_info["name_widget"] = name_lbl
            step_info["time_widget"] = time_lbl
            step_info["row_widget"] = row

        # Bottom padding
        tk.Frame(inner, bg=HUD_BG, height=PANEL_PAD).pack()

    def _build_activity_panel(self, win: tk.Toplevel):
        """Build the right panel showing current activity + timer + progress."""
        inner = win._inner

        # Title
        title_frame = tk.Frame(inner, bg=HUD_BG)
        title_frame.pack(fill="x", padx=PANEL_PAD, pady=(PANEL_PAD, 4))

        tk.Label(
            title_frame, text="📊 ACTIVITY", bg=HUD_BG, fg=HUD_ACCENT,
            font=TITLE_FONT, anchor="w",
        ).pack(side="left")

        # Separator
        tk.Frame(inner, bg=HUD_BORDER, height=1).pack(fill="x", padx=PANEL_PAD, pady=2)

        # Timer (big centered digits)
        self._timer_label = tk.Label(
            inner, text="00:00", bg=HUD_BG, fg=HUD_ACCENT,
            font=TIMER_FONT, anchor="center",
        )
        self._timer_label.pack(fill="x", padx=PANEL_PAD, pady=(8, 4))

        # Progress bar
        prog_frame = tk.Frame(inner, bg=HUD_BG, height=PROGRESS_H + 4)
        prog_frame.pack(fill="x", padx=PANEL_PAD, pady=4)
        prog_frame.pack_propagate(False)

        self._progress_canvas = tk.Canvas(
            prog_frame, bg=HUD_PROGRESS_BG, highlightthickness=0,
            height=PROGRESS_H,
        )
        self._progress_canvas.pack(fill="x", expand=True)
        self._draw_progress()

        # Progress text
        self._progress_text_label = tk.Label(
            inner, text="0 / 0 steps", bg=HUD_BG, fg=HUD_TEXT_DIM,
            font=STEP_FONT_SMALL, anchor="center",
        )
        self._progress_text_label.pack(fill="x", padx=PANEL_PAD)

        # Separator
        tk.Frame(inner, bg=HUD_BORDER, height=1).pack(fill="x", padx=PANEL_PAD, pady=6)

        # Activity label (what's happening now)
        self._activity_label = tk.Label(
            inner, text="Initializing...", bg=HUD_BG, fg=HUD_TEXT,
            font=ACTIVITY_FONT, anchor="w", wraplength=PANEL_W - 2 * PANEL_PAD,
        )
        self._activity_label.pack(fill="x", padx=PANEL_PAD, pady=2)

        # Narration label (what Onyx is saying)
        self._narration_label = tk.Label(
            inner, text="", bg=HUD_BG, fg=HUD_ACCENT_DIM,
            font=STEP_FONT_SMALL, anchor="w", wraplength=PANEL_W - 2 * PANEL_PAD,
        )
        self._narration_label.pack(fill="x", padx=PANEL_PAD, pady=2)

        # Separator
        tk.Frame(inner, bg=HUD_BORDER, height=1).pack(fill="x", padx=PANEL_PAD, pady=6)

        # Status line (bottom)
        self._status_label = tk.Label(
            inner, text=" ● Running", bg=HUD_BG, fg=HUD_ACCENT,
            font=STEP_FONT, anchor="w",
        )
        self._status_label.pack(fill="x", padx=PANEL_PAD, pady=(2, PANEL_PAD))

    # ------------------------------------------------------------------
    # Step display updates
    # ------------------------------------------------------------------

    def _update_step_display(self, index: int, status: str, duration: float = 0):
        """Update a step row's icon, color, and background."""
        if index < 0 or index >= len(self._steps):
            return
        step = self._steps[index]
        step["status"] = status

        icon_w = step.get("icon_widget")
        name_w = step.get("name_widget")
        time_w = step.get("time_widget")
        row_w = step.get("row_widget")

        if not icon_w or not name_w:
            return

        if status == "active":
            self._safe_config(icon_w, text=ICON_ACTIVE, fg=HUD_ACCENT)
            self._safe_config(name_w, fg=HUD_TEXT)
            if row_w:
                self._safe_config(row_w, bg=HUD_STEP_ACTIVE_BG)
                self._safe_config(icon_w, bg=HUD_STEP_ACTIVE_BG)
                self._safe_config(name_w, bg=HUD_STEP_ACTIVE_BG)
                if time_w:
                    self._safe_config(time_w, bg=HUD_STEP_ACTIVE_BG)

        elif status == "done":
            self._safe_config(icon_w, text=ICON_DONE, fg=HUD_SUCCESS)
            self._safe_config(name_w, fg=HUD_SUCCESS)
            if row_w:
                self._safe_config(row_w, bg=HUD_STEP_DONE_BG)
                self._safe_config(icon_w, bg=HUD_STEP_DONE_BG)
                self._safe_config(name_w, bg=HUD_STEP_DONE_BG)
                if time_w:
                    self._safe_config(time_w, bg=HUD_STEP_DONE_BG)
            if time_w and duration > 0:
                self._safe_config(time_w, text=f"{duration:.0f}s", fg=HUD_TEXT_DIM)

        elif status == "fail":
            self._safe_config(icon_w, text=ICON_FAIL, fg=HUD_ERROR)
            self._safe_config(name_w, fg=HUD_ERROR)
            if row_w:
                self._safe_config(row_w, bg=HUD_STEP_FAIL_BG)
                self._safe_config(icon_w, bg=HUD_STEP_FAIL_BG)
                self._safe_config(name_w, bg=HUD_STEP_FAIL_BG)
                if time_w:
                    self._safe_config(time_w, bg=HUD_STEP_FAIL_BG)

        elif status == "skip":
            self._safe_config(icon_w, text=ICON_SKIP, fg=HUD_TEXT_VDIM)
            self._safe_config(name_w, fg=HUD_TEXT_VDIM)

    # ------------------------------------------------------------------
    # Progress bar
    # ------------------------------------------------------------------

    def _draw_progress(self):
        """Redraw the progress bar canvas."""
        c = self._progress_canvas
        if not c:
            return
        try:
            c.delete("all")
            w = c.winfo_width()
            if w < 2:
                w = PANEL_W - 2 * PANEL_PAD
            h = PROGRESS_H

            # Background track
            c.create_rectangle(0, 0, w, h, fill=HUD_PROGRESS_BG, outline="")

            # Filled portion
            if self._progress_total > 0:
                frac = self._progress_cur / self._progress_total
                fill_w = max(2, int(w * frac))
                c.create_rectangle(0, 0, fill_w, h, fill=HUD_PROGRESS_FG, outline="")

                # Glow at the leading edge
                if frac < 1.0 and fill_w > 4:
                    c.create_rectangle(
                        fill_w - 4, 0, fill_w, h,
                        fill="#40f0ff", outline="",
                    )

            # Update text
            if hasattr(self, "_progress_text_label") and self._progress_text_label:
                self._safe_config(
                    self._progress_text_label,
                    text=f"{self._progress_cur} / {self._progress_total} steps",
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Timer tick
    # ------------------------------------------------------------------

    def _tick_timer(self):
        """Update the elapsed timer every second."""
        if not self._visible or self._finished:
            return
        elapsed = time.time() - self._start_time
        mins = int(elapsed) // 60
        secs = int(elapsed) % 60
        if self._timer_label:
            self._safe_config(self._timer_label, text=f"{mins:02d}:{secs:02d}")
        self._timer_id = self._root.after(1000, self._tick_timer)

    # ------------------------------------------------------------------
    # Glow pulse animation
    # ------------------------------------------------------------------

    def _pulse_glow(self):
        """Subtle pulsing border glow on the active step."""
        if not self._visible or self._finished:
            return
        self._pulse_phase = (self._pulse_phase + 1) % 40

        # Modulate brightness
        t = self._pulse_phase / 40.0
        brightness = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(t * 2 * math.pi))

        # Apply to active step row
        if 0 <= self._active_index < len(self._steps):
            step = self._steps[self._active_index]
            icon_w = step.get("icon_widget")
            if icon_w and step["status"] == "active":
                r = int(0x00 + (0x00) * brightness)
                g = int(0x88 + (0xe5 - 0x88) * brightness)
                b = int(0xaa + (0xff - 0xaa) * brightness)
                color = f"#{r:02x}{g:02x}{b:02x}"
                self._safe_config(icon_w, fg=color)

        self._pulse_id = self._root.after(50, self._pulse_glow)

    # ------------------------------------------------------------------
    # Flash effect on finish
    # ------------------------------------------------------------------

    def _flash_panels(self, color: str, count: int = 3):
        """Flash panel borders on workflow completion."""
        if count <= 0:
            return
        for win in (self._left_win, self._right_win):
            if win:
                try:
                    border = win.winfo_children()[0] if win.winfo_children() else None
                    if border:
                        border.configure(bg=color)
                        self._root.after(200, lambda b=border: self._safe_config(
                            b, bg=HUD_BORDER))
                except Exception:
                    pass
        self._root.after(400, lambda: self._flash_panels(color, count - 1))

    # ------------------------------------------------------------------
    # Reposition (call if face window moves)
    # ------------------------------------------------------------------

    def reposition(self):
        """Reposition panels relative to current face window location."""
        if not self._visible:
            return
        try:
            fx = self._root.winfo_rootx()
            fy = self._root.winfo_rooty()
            fw = self._root.winfo_width()
            fh = self._root.winfo_height()
            screen_w = self._root.winfo_screenwidth()
            screen_h = self._root.winfo_screenheight()

            if self._left_win:
                lw = self._left_win.winfo_width()
                lh = self._left_win.winfo_height()
                lx = max(0, fx - lw - PANEL_GAP)
                ly = max(0, fy + (fh - lh) // 2)
                ly = min(ly, screen_h - lh - 40)
                self._left_win.geometry(f"+{lx}+{ly}")

            if self._right_win:
                rw = self._right_win.winfo_width()
                rh = self._right_win.winfo_height()
                rx = min(screen_w - rw, fx + fw + PANEL_GAP)
                ry = max(0, fy + (fh - rh) // 2)
                ry = min(ry, screen_h - rh - 40)
                self._right_win.geometry(f"+{rx}+{ry}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_config(widget, **kwargs):
        """Configure a widget, ignoring errors if it's been destroyed."""
        try:
            widget.configure(**kwargs)
        except Exception:
            pass
