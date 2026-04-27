"""OnyxKraken App — main GUI combining animated face + retractable chat + voice.

Layout:
  ┌──────────────┬────────────────────┐
  │              │  Chat history       │
  │   FACE       │  ──────────────     │
  │  (animated)  │  > User: ...        │
  │              │  < Onyx: ...        │
  │              │                     │
  │   [◀ toggle] │  [input] [🎤] [⚡]  │
  └──────────────┴────────────────────┘

Features:
  - Resizable window (face scales proportionally)
  - Retractable chat panel (slides from right)
  - Text input + send
  - Mic button (push-to-talk STT)
  - Hands-free toggle (continuous listen)
  - TTS responses synced with mouth animation
  - Draggable title bar
  - Always on top (drops during task execution)

Usage:
    python -m face.app
    python main.py face
"""

import json
import logging
import os
import threading
import time

_log = logging.getLogger("face.app")
import tkinter as tk
from datetime import datetime
# REMOVED (unused): from tkinter import font as tkfont

import sys as _sys
from face.face_gui import FaceCanvas, BG_COLOR, ACCENT_BRIGHT, ACCENT_MID, ACCENT_DIM, ACCENT_VDIM, FACE_COLOR, REF_W, REF_H
if _sys.platform == "win32":
    from face.rigged_body_window import RiggedBodyWindow as BodyWindow
else:
    BodyWindow = None  # Body overlay requires Win32 DWM APIs
from face.backend import BackendBridge
from face.app_catalog import APP_TEMPLATES, CATEGORIES, CATEGORY_ICONS, get_template, get_templates_by_category
from face import settings as onyx_settings


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

FACE_MIN_W = 280
FACE_MIN_H = 250
CHAT_WIDTH = 320
APPS_WIDTH = 340
EXT_WIDTH = 300
CTRL_STRIP_H = 26
MIN_W = FACE_MIN_W
MIN_H = FACE_MIN_H + CTRL_STRIP_H

# Colors
APPS_BG = "#060a12"
APPS_CARD_BG = "#0a1220"
APPS_CARD_BORDER = "#0e2a3d"
APPS_DRAFT_FG = "#ff8844"
APPS_VERIFIED_FG = "#44ff88"
APPS_PREFERRED_FG = "#00d4ff"
EXT_BG = "#060a12"
EXT_CARD_BG = "#0a1220"
EXT_CARD_BORDER = "#0e2a3d"
CHAT_BG = "#080c14"
CHAT_INPUT_BG = "#0c1220"
CHAT_INPUT_FG = "#c0d0e0"
CHAT_BORDER = "#0e2a3d"
USER_MSG_COLOR = "#00d4ff"
BOT_MSG_COLOR = "#8899aa"
SYSTEM_MSG_COLOR = "#445566"
BTN_BG = "#0c1825"
BTN_FG = "#00d4ff"
BTN_ACTIVE_BG = "#0a2535"
BTN_RECORDING = "#ff4444"
BTN_HANDSFREE = "#00ff88"
USER_BUBBLE_BG = "#0a2838"
BOT_BUBBLE_BG = "#0c1525"
TIMESTAMP_COLOR = "#334455"


# ---------------------------------------------------------------------------
# OnyxKrakenApp
# ---------------------------------------------------------------------------

class OnyxKrakenApp:
    """Main GUI: animated face + retractable chat panel + voice controls."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("OnyxKraken")
        self.root.configure(bg=BG_COLOR)
        self.root.attributes("-topmost", True)
        self.root.minsize(MIN_W, MIN_H)

        # State
        self._chat_visible = False
        self._chat_float_win = None  # Toplevel when chat is floating
        self._apps_visible = False
        self._ext_visible = False
        self._ext_remotes = {}  # name -> ExtensionRemote window
        self._running = True
        self._demo_runner = None  # lazy init DemoRunner
        self._stage_manager = None  # lazy init StageManager
        self._show_engine = None    # lazy init ShowEngine
        self._is_recording = False
        self._screen_recorder = None
        self._workflow_hud = None  # WorkflowHUD (lazy init)

        # Backend bridge
        self.backend = BackendBridge()

        # Pass window handle for self-screenshot (cross-platform)
        try:
            from core.platform import get_window_handle
            handle = get_window_handle(self.root)
            if handle:
                self.backend._self_window_handle = handle
        except Exception:
            pass

        # Build UI
        self._build_apps_panel()  # hidden initially (must be before main_area for left packing)
        self._build_main_area()
        self._build_control_strip()
        self._build_extensions_panel()  # hidden initially (right side, before chat)
        self._build_chat_panel()  # hidden initially

        # Save docked chat widget refs (for restoring after floating mode)
        self._docked_chat_history = self._chat_history
        self._docked_input_entry = self._input_entry
        self._docked_input_var = self._input_var
        self._docked_chat_header = self._chat_header_label
        self._docked_typing_label = self._typing_label
        self._docked_typing_frame = self._typing_frame
        self._docked_mic_btn = self._mic_btn
        self._docked_hf_btn = self._hf_btn
        self._docked_tts_btn = self._tts_btn

        # Set initial size (face only)
        self.root.geometry(f"{REF_W}x{REF_H + CTRL_STRIP_H}")

        # Position center screen
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        ww = REF_W
        wh = REF_H + CTRL_STRIP_H
        self.root.geometry(f"+{(sw - ww) // 2}+{(sh - wh) // 2}")

        # Bindings
        self.root.bind("<Escape>", lambda e: self.close())
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        # Robot body window (transparent overlay below face)
        # Load saved body settings
        _body_settings = onyx_settings.load_settings()
        _saved_char = _body_settings.get("active_character", "onyx")
        _saved_body_style = "standard"
        try:
            from face.stage.character_library import CHARACTER_TEMPLATES, THEME_COLORS
            _char_tmpl = CHARACTER_TEMPLATES.get(_saved_char)
            if _char_tmpl:
                _saved_body_style = _char_tmpl.body_style
        except Exception:
            pass

        if BodyWindow is not None:
            self._body = BodyWindow(self.root, face_canvas=self.face, body_style=_saved_body_style)
        else:
            self._body = None  # Body overlay unavailable on this platform

        def _safe_attach_body():
            if self._body is None:
                return  # No body overlay on this platform
            try:
                # Apply saved offset, scale, and visibility
                ox = _body_settings.get("body_offset_x", 0)
                oy = _body_settings.get("body_offset_y", 0)
                sc = _body_settings.get("body_scale", 1.0)
                vis = _body_settings.get("body_visible", True)

                self._body.set_offset(ox, oy)
                self._body.set_scale(sc)
                self._body.attach()

                # Apply saved character colors
                try:
                    _char_tmpl = CHARACTER_TEMPLATES.get(_saved_char)
                    if _char_tmpl and self._body._body:
                        colors = THEME_COLORS.get(_char_tmpl.theme, THEME_COLORS.get("cyan", {}))
                        if colors:
                            self._body._body.colors = colors.copy()
                except Exception:
                    pass

                if not vis:
                    self._body.set_visible(False)

                _log.info(f"[Body] attached={self._body.is_attached} visible={self._body.is_visible} "
                          f"char={_saved_char} offset=({ox},{oy}) scale={sc}")
            except Exception as e:
                _log.error(f"[Body] attach FAILED: {e}")
                import traceback; traceback.print_exc()
        self.root.after(500, _safe_attach_body)

        # Body adjustment keyboard shortcuts (Ctrl+Shift+Arrow/+/-)
        self.root.bind("<Control-Shift-Up>", lambda e: self._body.adjust_offset(ddy=-5))
        self.root.bind("<Control-Shift-Down>", lambda e: self._body.adjust_offset(ddy=5))
        self.root.bind("<Control-Shift-Left>", lambda e: self._body.adjust_offset(ddx=-5))
        self.root.bind("<Control-Shift-Right>", lambda e: self._body.adjust_offset(ddx=5))
        self.root.bind("<Control-Shift-equal>", lambda e: self._body.adjust_scale(0.05))
        self.root.bind("<Control-Shift-minus>", lambda e: self._body.adjust_scale(-0.05))

        # Load previous session messages into chat panel
        self._load_chat_history()

        # Start polling backend callbacks
        self._poll_backend()

    # ------------------------------------------------------------------
    # Main area (face canvas + control strip)
    # ------------------------------------------------------------------

    def _build_main_area(self):
        self._main_frame = tk.Frame(self.root, bg=BG_COLOR)
        self._main_frame.pack(fill="both", expand=True, side="left")

        self.face = FaceCanvas(self._main_frame)
        self.face.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Radial menu item definitions
    # ------------------------------------------------------------------
    _RADIAL_ITEMS = [
        ("📱", "Apps",       ACCENT_BRIGHT, "_toggle_apps"),
        ("🧩", "Ext",        ACCENT_MID,    "_toggle_extensions"),
        ("🪞", "Mirror",     "#66bbdd",     "_radial_mirror"),
        ("🎬", "Demo",       "#ff8844",     "_toggle_demo"),
        ("🎭", "Stage",      "#aa66ff",     "_radial_stage"),
        ("❤",  "Duo",        "#ff69b4",     "_toggle_companion"),
        ("⏺",  "Rec",        "#ff3333",     "_toggle_recording"),
        ("🤖", "Body",       "#00d4ff",     "_toggle_body"),
        ("⚙",  "Settings",   "#8899aa",     "_open_settings"),
    ]

    def _build_control_strip(self):
        """Minimal strip: status dot + ≡ radial trigger + chat toggle."""
        strip = tk.Frame(self._main_frame, bg=FACE_COLOR, height=CTRL_STRIP_H)
        strip.pack(fill="x", side="bottom")
        strip.pack_propagate(False)

        # Status dot (left)
        self._status_dot = tk.Label(
            strip, text=" ● ", bg=FACE_COLOR, fg=ACCENT_DIM,
            font=("Consolas", 8),
        )
        self._status_dot.pack(side="left", padx=4)

        # Mode indicator (left, always visible)
        self._mode_label = tk.Label(
            strip, text=" 💬 Chat ", bg=FACE_COLOR, fg=ACCENT_DIM,
            font=("Consolas", 8), cursor="hand2",
        )
        self._mode_label.pack(side="left", padx=2)
        self._mode_label.bind("<Button-1>", lambda e: self._toggle_mode())
        self._mode_label.bind("<Enter>",
                              lambda e: self._mode_label.configure(fg=ACCENT_BRIGHT))
        self._mode_label.bind("<Leave>", lambda e: self._mode_label.configure(
            fg="#ffaa00" if self.backend.mode == "work" else ACCENT_DIM))

        # ≡ Menu button — opens radial arc menu
        self._radial_open = False
        self._radial_overlay = None
        self._radial_canvas_items = []
        self._radial_anim_id = None

        self._menu_btn = tk.Label(
            strip, text=" ≡ ", bg=FACE_COLOR, fg=ACCENT_DIM,
            font=("Consolas", 12, "bold"), cursor="hand2",
        )
        self._menu_btn.pack(side="left", padx=6)
        self._menu_btn.bind("<Button-1>", lambda e: self._toggle_radial_menu())
        self._menu_btn.bind("<Enter>",
                            lambda e: self._menu_btn.configure(fg=ACCENT_BRIGHT))
        self._menu_btn.bind("<Leave>", lambda e: self._menu_btn.configure(
            fg=ACCENT_MID if self._radial_open else ACCENT_DIM))

        # Chat toggle button (right)
        self._toggle_btn = tk.Label(
            strip, text=" ◀ Chat ", bg=FACE_COLOR, fg=ACCENT_DIM,
            font=("Consolas", 9), cursor="hand2",
        )
        self._toggle_btn.pack(side="right", padx=4)
        self._toggle_btn.bind("<Button-1>", lambda e: self._toggle_chat())
        self._toggle_btn.bind("<Enter>",
                              lambda e: self._toggle_btn.configure(fg=ACCENT_BRIGHT))
        self._toggle_btn.bind("<Leave>", lambda e: self._toggle_btn.configure(
            fg=ACCENT_MID if self._chat_visible else ACCENT_DIM))

        # Hidden label refs so existing code that touches these still works
        self._apps_toggle_btn = tk.Label(strip, bg=FACE_COLOR)
        self._ext_toggle_btn = tk.Label(strip, bg=FACE_COLOR)
        self._mirror_btn = tk.Label(strip, bg=FACE_COLOR)
        self._demo_btn = tk.Label(strip, bg=FACE_COLOR)
        self._stage_btn = tk.Label(strip, bg=FACE_COLOR)
        self._companion_btn = tk.Label(strip, bg=FACE_COLOR)
        self._record_btn = tk.Label(strip, bg=FACE_COLOR)
        self._settings_btn = tk.Label(strip, bg=FACE_COLOR)

    # ------------------------------------------------------------------
    # Radial Arc Menu — animated semicircle fan from ≡ button
    # ------------------------------------------------------------------

    def _toggle_radial_menu(self):
        if self._radial_open:
            self._close_radial_menu()
        else:
            self._open_radial_menu()

    def _open_radial_menu(self):
        """Fan menu items in a semicircle above the ≡ button with ease-out."""
        import math
        if self._radial_open:
            return
        self._radial_open = True
        self._menu_btn.configure(fg=ACCENT_MID, text=" ✕ ")

        parent = self._main_frame
        pw = parent.winfo_width()
        ph = parent.winfo_height()

        ov = tk.Canvas(parent, highlightthickness=0, width=pw, height=ph)
        ov.configure(bg=FACE_COLOR)
        ov.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        # Dim backdrop — click to dismiss
        ov.create_rectangle(0, 0, pw, ph, fill="#000000",
                            stipple="gray25", tags="backdrop")
        ov.tag_bind("backdrop", "<Button-1>",
                    lambda e: self._close_radial_menu())

        self._radial_overlay = ov
        self._radial_canvas_items = []

        # Origin: bottom-center of overlay
        ox = pw // 2
        oy = ph - 14

        n = len(self._RADIAL_ITEMS)
        arc_span = 150.0
        arc_start = 185.0
        radius = max(90, min(int(min(pw, ph) * 0.37), 170))

        finals = []
        for i in range(n):
            a = math.radians(arc_start + (arc_span / max(n - 1, 1)) * i)
            finals.append((ox + radius * math.cos(a),
                           oy + radius * math.sin(a)))

        # Create items at origin (they animate outward)
        for i, (icon, label, color, method) in enumerate(self._RADIAL_ITEMS):
            tag = f"ri{i}"
            sz = 20
            glow = ov.create_oval(ox - sz, oy - sz, ox + sz, oy + sz,
                                  fill="#0a1825", outline=color,
                                  width=2, tags=(tag, "ri"))
            ico = ov.create_text(ox, oy - 3, text=icon,
                                 font=("Segoe UI Emoji", 13),
                                 fill="#ffffff", tags=(tag, "ri"))
            lbl = ov.create_text(ox, oy + 15, text=label,
                                 font=("Consolas", 7, "bold"),
                                 fill=color, tags=(tag, "ri"))

            self._radial_canvas_items.append(
                (glow, ico, lbl, tag, i, method, color))

            # Hover / click binds
            def _enter(e, t=tag):
                for it in ov.find_withtag(t):
                    if ov.type(it) == "oval":
                        ov.itemconfig(it, fill="#0e2a3d", width=3)
            def _leave(e, t=tag, c=color):
                for it in ov.find_withtag(t):
                    if ov.type(it) == "oval":
                        ov.itemconfig(it, fill="#0a1825", width=2)
            def _click(e, m=method):
                self._close_radial_menu()
                fn = getattr(self, m, None)
                if fn:
                    fn() if m not in ("_radial_mirror", "_radial_stage") else fn(e)

            ov.tag_bind(tag, "<Enter>", _enter)
            ov.tag_bind(tag, "<Leave>", _leave)
            ov.tag_bind(tag, "<Button-1>", _click)

        # Animate
        self._r_finals = finals
        self._r_origin = (ox, oy)
        self._r_step = 0
        self._r_total = 8
        self._animate_radial()

    def _animate_radial(self):
        """Ease-out animation moving items from origin to final arc positions."""
        if not self._radial_open or not self._radial_overlay:
            return
        ov = self._radial_overlay
        ox, oy = self._r_origin
        t = min(1.0, (self._r_step + 1) / self._r_total)
        ease = 1.0 - (1.0 - t) ** 3  # cubic ease-out

        sz = 20
        for glow, ico, lbl, tag, idx, method, color in self._radial_canvas_items:
            fx, fy = self._r_finals[idx]
            cx = ox + (fx - ox) * ease
            cy = oy + (fy - oy) * ease
            ov.coords(glow, cx - sz, cy - sz, cx + sz, cy + sz)
            ov.coords(ico, cx, cy - 3)
            ov.coords(lbl, cx, cy + 15)

        self._r_step += 1
        if self._r_step <= self._r_total:
            self._radial_anim_id = self.root.after(18, self._animate_radial)
        else:
            self._radial_anim_id = None

    def _close_radial_menu(self):
        """Destroy the radial overlay."""
        self._radial_open = False
        self._menu_btn.configure(fg=ACCENT_DIM, text=" ≡ ")
        if self._radial_anim_id:
            self.root.after_cancel(self._radial_anim_id)
            self._radial_anim_id = None
        if self._radial_overlay:
            self._radial_overlay.destroy()
            self._radial_overlay = None
        self._radial_canvas_items = []

    def _radial_mirror(self, event=None):
        """Mirror sub-menu from radial."""
        menu = tk.Menu(self.root, tearoff=0, bg=BTN_BG, fg=BTN_FG,
                       activebackground=BTN_ACTIVE_BG, activeforeground=BTN_FG,
                       font=("Consolas", 9))
        menu.add_command(label="🪞  Analyze Self",
                         command=lambda: self.backend.analyze_self(
                             tune_expressions=False))
        menu.add_command(label="🎨  Tune Expressions",
                         command=lambda: self.backend.analyze_self(
                             tune_expressions=True))
        try:
            x = self.root.winfo_rootx() + self.root.winfo_width() // 2
            y = self.root.winfo_rooty() + self.root.winfo_height() // 2
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _radial_stage(self, event=None):
        """Stage sub-menu from radial."""
        menu = tk.Menu(self.root, tearoff=0, bg=BTN_BG, fg=BTN_FG,
                       activebackground=BTN_ACTIVE_BG, activeforeground=BTN_FG,
                       font=("Consolas", 9))
        if self._stage_manager and self._stage_manager.is_open:
            menu.add_command(label="🚪  Close Stage",
                             command=self._close_stage)
            menu.add_separator()
            menu.add_command(label="▶  Run Premiere",
                             command=self._run_premiere)
            menu.add_command(label="📺  Episode 1 (Pilot)",
                             command=lambda: self._run_episode(1))
            menu.add_separator()
            menu.add_command(label="🎧  DJ Set (15 min)",
                             command=lambda: self._launch_dj_set(15))
            menu.add_command(label="🎧  DJ Set (30 min)",
                             command=lambda: self._launch_dj_set(30))
        else:
            menu.add_command(label="🎭  Open Stage",
                             command=self._launch_stage)
            menu.add_command(label="▶  Open Stage + Premiere",
                             command=lambda: self._launch_stage(
                                 run_premiere=True))
            menu.add_command(label="📺  Open Stage + Episode 1",
                             command=lambda: self._launch_stage(
                                 run_show="episode1"))
            menu.add_separator()
            menu.add_command(label="🎧  DJ Set (15 min)",
                             command=lambda: self._launch_dj_set(15))
            menu.add_command(label="🎧  DJ Set (30 min)",
                             command=lambda: self._launch_dj_set(30))
            menu.add_command(label="🎧  DJ Set (Custom...)",
                             command=self._launch_dj_set_dialog)
        try:
            x = self.root.winfo_rootx() + self.root.winfo_width() // 2
            y = self.root.winfo_rooty() + self.root.winfo_height() // 2
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    # ------------------------------------------------------------------
    # Apps panel (retractable, left side — desktop-style icon grid)
    # ------------------------------------------------------------------

    _apps_category_filter = "All"

    def _build_apps_panel(self):
        """Build the retractable apps panel with desktop-style icon grid."""
        self._apps_frame = tk.Frame(self.root, bg=APPS_BG, width=APPS_WIDTH)

        # Header
        apps_header = tk.Frame(self._apps_frame, bg=APPS_BG, height=24)
        apps_header.pack(fill="x", padx=8, pady=(8, 2))
        tk.Label(apps_header, text="APPS", bg=APPS_BG, fg=ACCENT_DIM,
                 font=("Consolas", 9, "bold")).pack(side="left")

        # Category filter tabs
        self._cat_frame = tk.Frame(self._apps_frame, bg=APPS_BG)
        self._cat_frame.pack(fill="x", padx=6, pady=(2, 4))
        self._cat_buttons = {}
        for cat_name in ["All"] + CATEGORIES:
            short = cat_name[:4] if cat_name != "Dev Tools" else "Dev"
            if cat_name == "All":
                short = "All"
            icon = CATEGORY_ICONS.get(cat_name, "📦")
            label = f"{icon} {short}" if cat_name != "All" else "All"
            btn = tk.Label(
                self._cat_frame, text=f" {label} ", bg=APPS_BG, fg=ACCENT_DIM,
                font=("Consolas", 7), cursor="hand2",
            )
            btn.pack(side="left", padx=1)
            btn.bind("<Button-1>", lambda e, c=cat_name: self._set_category_filter(c))
            btn.bind("<Enter>", lambda e, b=btn: b.configure(fg=ACCENT_BRIGHT))
            btn.bind("<Leave>", lambda e, b=btn, c=cat_name:
                     b.configure(fg=ACCENT_MID if self._apps_category_filter == c else ACCENT_DIM))
            self._cat_buttons[cat_name] = btn

        # Separator
        tk.Frame(self._apps_frame, bg=APPS_CARD_BORDER, height=1).pack(fill="x", padx=6)

        # Scrollable grid area
        self._apps_canvas = tk.Canvas(
            self._apps_frame, bg=APPS_BG, highlightthickness=0, borderwidth=0,
        )
        self._apps_scrollbar = tk.Scrollbar(
            self._apps_frame, orient="vertical", command=self._apps_canvas.yview,
            bg=APPS_BG, troughcolor=APPS_BG, highlightthickness=0, borderwidth=0,
        )
        self._apps_inner = tk.Frame(self._apps_canvas, bg=APPS_BG)
        self._apps_inner.bind(
            "<Configure>",
            lambda e: self._apps_canvas.configure(scrollregion=self._apps_canvas.bbox("all")),
        )
        self._apps_canvas.create_window((0, 0), window=self._apps_inner, anchor="nw")
        self._apps_canvas.configure(yscrollcommand=self._apps_scrollbar.set)

        self._apps_scrollbar.pack(side="right", fill="y")
        self._apps_canvas.pack(fill="both", expand=True, padx=2, pady=4)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            self._apps_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._apps_canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")

    def _set_category_filter(self, category: str):
        """Set the active category filter and refresh the grid."""
        self._apps_category_filter = category
        for name, btn in self._cat_buttons.items():
            btn.configure(fg=ACCENT_MID if name == category else ACCENT_DIM)
        self._refresh_apps()

    def _toggle_apps(self):
        """Show/hide the apps panel on the left side."""
        if self._apps_visible:
            self._apps_frame.pack_forget()
            self._apps_visible = False
            w = self.root.winfo_width() - APPS_WIDTH
            h = self.root.winfo_height()
            self.root.geometry(f"{max(w, MIN_W)}x{h}")
            self._apps_toggle_btn.configure(fg=ACCENT_DIM)
        else:
            self._apps_frame.pack(fill="both", expand=False, side="left",
                                  before=self._main_frame)
            self._apps_frame.configure(width=APPS_WIDTH)
            self._apps_visible = True
            w = self.root.winfo_width() + APPS_WIDTH
            h = self.root.winfo_height()
            self.root.geometry(f"{w}x{max(h, MIN_H)}")
            self._apps_toggle_btn.configure(fg=ACCENT_MID)
            self._refresh_apps()

    # ------------------------------------------------------------------
    # Extensions Controller (floating window — replaces old docked panel)
    # ------------------------------------------------------------------

    def _build_extensions_panel(self):
        """Stub — the old docked panel is replaced by the floating controller.

        We still create _ext_frame as a hidden dummy so any legacy code
        referencing it doesn't crash, but it's never packed.
        """
        self._ext_frame = tk.Frame(self.root, bg=EXT_BG, width=0)
        self._ext_controller = None  # floating ExtensionsController instance

    def _toggle_extensions(self):
        """Open or focus the floating Onyx Controller window."""
        # If already open, focus it
        if self._ext_controller is not None:
            try:
                self._ext_controller.focus()
                return
            except Exception:
                self._ext_controller = None

        from face.extensions_controller import ExtensionsController

        def _on_close():
            self._ext_controller = None
            self._ext_visible = False

        self._ext_controller = ExtensionsController(
            parent=self.root,
            backend=self.backend,
            on_close=_on_close,
            ext_remotes=self._ext_remotes,
            open_ext_remote_fn=self._open_ext_remote,
        )
        self._ext_visible = True

    def _refresh_extensions(self):
        """Refresh the floating controller if it's open."""
        if self._ext_controller is not None:
            try:
                self._ext_controller._rebuild_content()
            except Exception:
                pass

    def _open_connection_control(self, conn_name: str):
        """Open a connection control window for an external program."""
        # Track open connection windows
        if not hasattr(self, '_conn_windows'):
            self._conn_windows = {}

        if conn_name in self._conn_windows:
            try:
                self._conn_windows[conn_name].win.lift()
                self._conn_windows[conn_name].win.focus_force()
                return
            except Exception:
                del self._conn_windows[conn_name]

        try:
            from face.connections import CONNECTIONS, get_manager
            mgr = get_manager()
            ci = next((c for c in CONNECTIONS if c.name == conn_name), None)
            if ci and ci.control_class:
                def _on_close():
                    self._conn_windows.pop(conn_name, None)
                    if self._ext_visible:
                        self.root.after(100, self._refresh_extensions)
                win = ci.control_class(self.root, ci, mgr, on_close=_on_close)
                self._conn_windows[conn_name] = win
        except Exception as e:
            _log.debug("Connection control error: %s", e)

    def _open_ext_remote(self, ext_name: str):
        """Open (or focus) the remote control window for an extension."""
        # If already open, focus it
        if ext_name in self._ext_remotes:
            remote = self._ext_remotes[ext_name]
            try:
                remote.win.lift()
                remote.win.focus_force()
                return
            except Exception:
                # Window was closed externally
                del self._ext_remotes[ext_name]

        from face.extensions import open_extension_remote

        def _on_close():
            self._ext_remotes.pop(ext_name, None)
            if self._ext_visible:
                self.root.after(100, self._refresh_extensions)

        remote = open_extension_remote(
            self.root, ext_name, backend=self.backend, on_close=_on_close)
        if remote:
            self._ext_remotes[ext_name] = remote
            if self._ext_visible:
                self._refresh_extensions()

    def _refresh_apps(self):
        """Rebuild the desktop icon grid from built tools + catalog templates."""
        for child in self._apps_inner.winfo_children():
            child.destroy()

        # Get built tools
        try:
            from core.toolsmith import list_tools
            built_tools = {t.name.lower(): t for t in list_tools()}
        except ImportError:
            built_tools = {}

        # Merge: built tools first, then unbuilt templates
        cat_filter = self._apps_category_filter
        grid_items = []  # list of (icon, name, display, is_built, status, category, tool_or_template)

        # Built tools
        for tool in built_tools.values():
            # Find matching template for icon, or use default
            tmpl = get_template(tool.name)
            icon = tmpl.icon if tmpl else "📦"
            cat = tmpl.category if tmpl else "Utilities"
            if cat_filter != "All" and cat != cat_filter:
                continue
            status_map = {"draft": "🔨", "verified": "✅", "preferred": "⭐"}
            status_icon = status_map.get(tool.status, "")
            grid_items.append((icon, tool.name, tool.display_name, True,
                               tool.status, cat, tool))

        # Unbuilt templates (not yet in registry)
        for tmpl in APP_TEMPLATES:
            if tmpl.name in built_tools:
                continue
            if cat_filter != "All" and tmpl.category != cat_filter:
                continue
            grid_items.append((tmpl.icon, tmpl.name, tmpl.display_name, False,
                               "available", tmpl.category, tmpl))

        if not grid_items:
            tk.Label(self._apps_inner, text="No apps in this category.",
                     bg=APPS_BG, fg=SYSTEM_MSG_COLOR, font=("Consolas", 9),
                     justify="center").pack(pady=20)
            return

        # Render as icon grid (4 columns)
        COLS = 4
        TILE_W = 72
        TILE_H = 78

        row_frame = None
        for idx, item in enumerate(grid_items):
            icon, name, display, is_built, status, cat, obj = item

            if idx % COLS == 0:
                row_frame = tk.Frame(self._apps_inner, bg=APPS_BG)
                row_frame.pack(fill="x", padx=4, pady=2)

            tile = tk.Frame(row_frame, bg=APPS_BG, width=TILE_W, height=TILE_H,
                            cursor="hand2")
            tile.pack(side="left", padx=4, pady=4)
            tile.pack_propagate(False)

            # Status-based colors
            if is_built:
                if status == "preferred":
                    border_color = APPS_PREFERRED_FG
                    name_fg = APPS_PREFERRED_FG
                elif status == "verified":
                    border_color = APPS_VERIFIED_FG
                    name_fg = APPS_VERIFIED_FG
                else:
                    border_color = APPS_DRAFT_FG
                    name_fg = APPS_DRAFT_FG
                icon_bg = "#0c1828"
            else:
                border_color = "#1a2535"
                name_fg = "#556677"
                icon_bg = "#080e18"

            # Icon circle
            icon_frame = tk.Frame(tile, bg=icon_bg, highlightbackground=border_color,
                                  highlightthickness=1, width=46, height=46)
            icon_frame.pack(pady=(2, 1))
            icon_frame.pack_propagate(False)
            icon_label = tk.Label(icon_frame, text=icon, bg=icon_bg,
                                  font=("Segoe UI Emoji", 16), anchor="center")
            icon_label.pack(expand=True)

            # Name label (truncated)
            short_name = display if len(display) <= 9 else display[:8] + "…"
            name_label = tk.Label(tile, text=short_name, bg=APPS_BG, fg=name_fg,
                                  font=("Consolas", 7), anchor="center")
            name_label.pack()

            # Bind click to open detail popup
            for widget in (tile, icon_frame, icon_label, name_label):
                widget.bind("<Button-1>",
                            lambda e, o=obj, b=is_built: self._open_app_detail(o, b))

            # Hover effect
            def _hover_in(e, tf=tile, ifrm=icon_frame):
                tf.configure(bg="#0c1828")
                for c in tf.winfo_children():
                    if c != ifrm:
                        c.configure(bg="#0c1828")

            def _hover_out(e, tf=tile, ifrm=icon_frame):
                tf.configure(bg=APPS_BG)
                for c in tf.winfo_children():
                    if c != ifrm:
                        c.configure(bg=APPS_BG)

            for widget in (tile, icon_frame, icon_label, name_label):
                widget.bind("<Enter>", _hover_in)
                widget.bind("<Leave>", _hover_out)

    # ------------------------------------------------------------------
    # App detail popup
    # ------------------------------------------------------------------

    def _open_app_detail(self, obj, is_built: bool):
        """Open a detail popup for a built tool or available template."""
        dialog = tk.Toplevel(self.root)
        dialog.configure(bg=APPS_BG)
        dialog.geometry("380x320")
        dialog.transient(self.root)
        dialog.attributes("-topmost", True)

        if is_built:
            tool = obj
            tmpl = get_template(tool.name)
            icon = tmpl.icon if tmpl else "📦"
            title = tool.display_name
            desc = tool.description
            cat = tmpl.category if tmpl else "Utilities"
            status = tool.status.upper()
            status_color = {"DRAFT": APPS_DRAFT_FG, "VERIFIED": APPS_VERIFIED_FG,
                            "PREFERRED": APPS_PREFERRED_FG}.get(status, ACCENT_DIM)
            dialog.title(f"{title}")
        else:
            tmpl = obj
            icon = tmpl.icon
            title = tmpl.display_name
            desc = tmpl.description
            cat = tmpl.category
            status = "AVAILABLE"
            status_color = "#556677"
            dialog.title(f"{title} — Available")

        # Header with icon
        header = tk.Frame(dialog, bg=APPS_BG)
        header.pack(fill="x", padx=16, pady=(16, 8))

        tk.Label(header, text=icon, bg=APPS_BG,
                 font=("Segoe UI Emoji", 28)).pack(side="left", padx=(0, 12))

        info = tk.Frame(header, bg=APPS_BG)
        info.pack(side="left", fill="x", expand=True)
        tk.Label(info, text=title, bg=APPS_BG, fg="#e0f0ff",
                 font=("Consolas", 13, "bold"), anchor="w").pack(fill="x")
        cat_icon = CATEGORY_ICONS.get(cat, "")
        tk.Label(info, text=f"{cat_icon} {cat}  •  {status}",
                 bg=APPS_BG, fg=status_color,
                 font=("Consolas", 8), anchor="w").pack(fill="x")

        # Separator
        tk.Frame(dialog, bg=APPS_CARD_BORDER, height=1).pack(fill="x", padx=16, pady=4)

        # Description
        desc_label = tk.Label(dialog, text=desc, bg=APPS_BG, fg="#8899aa",
                              font=("Consolas", 9), wraplength=340, justify="left",
                              anchor="nw")
        desc_label.pack(fill="x", padx=16, pady=(4, 8))

        if is_built:
            # Version info
            tk.Label(dialog, text=f"Version: {tool.version}  •  Status: {tool.status}",
                     bg=APPS_BG, fg=SYSTEM_MSG_COLOR,
                     font=("Consolas", 8)).pack(padx=16, anchor="w")

        # Separator
        tk.Frame(dialog, bg=APPS_CARD_BORDER, height=1).pack(fill="x", padx=16, pady=8)

        # Action buttons
        btn_frame = tk.Frame(dialog, bg=APPS_BG)
        btn_frame.pack(fill="x", padx=16, pady=(0, 12))

        if is_built:
            # Open
            self._make_detail_btn(btn_frame, "▶  Open", APPS_PREFERRED_FG,
                                  lambda: (dialog.destroy(),
                                           self.backend.tool_launch(tool.name)))
            # Edit
            self._make_detail_btn(btn_frame, "✏️  Edit", "#ffaa44",
                                  lambda: (dialog.destroy(),
                                           self._show_edit_dialog(tool.name)))
            # Rebuild
            self._make_detail_btn(btn_frame, "🔄  Rebuild", ACCENT_MID,
                                  lambda: (dialog.destroy(),
                                           self._trigger_build(tool.name,
                                                               tmpl.build_prompt if tmpl else desc)))

            if tool.status == "draft":
                self._make_detail_btn(btn_frame, "✓  Verify", APPS_VERIFIED_FG,
                                      lambda: (dialog.destroy(),
                                               self.backend.tool_verify(tool.name)))

            # Delete (right-aligned)
            del_btn = tk.Label(
                btn_frame, text=" 🗑️ Delete ", bg="#1a0808", fg="#ff4444",
                font=("Consolas", 9), cursor="hand2", pady=4,
            )
            del_btn.pack(side="right", pady=4)
            del_btn.bind("<Button-1>", lambda e: (dialog.destroy(),
                                                   self._confirm_delete_tool(tool.name)))
            del_btn.bind("<Enter>", lambda e: del_btn.configure(bg="#2a1010"))
            del_btn.bind("<Leave>", lambda e: del_btn.configure(bg="#1a0808"))
        else:
            # Build button (prominent)
            build_btn = tk.Label(
                btn_frame, text="  ⚡  Build This App  ", bg="#0a2030", fg=ACCENT_BRIGHT,
                font=("Consolas", 11, "bold"), cursor="hand2", pady=6,
            )
            build_btn.pack(fill="x", pady=(4, 8))
            build_btn.bind("<Button-1>",
                           lambda e: (dialog.destroy(),
                                      self._trigger_build(tmpl.name, tmpl.build_prompt)))
            build_btn.bind("<Enter>", lambda e: build_btn.configure(bg="#0c2840"))
            build_btn.bind("<Leave>", lambda e: build_btn.configure(bg="#0a2030"))

            # Capabilities
            if tmpl.capabilities:
                caps_text = "  •  ".join(tmpl.capabilities)
                tk.Label(dialog, text=f"Capabilities: {caps_text}",
                         bg=APPS_BG, fg="#445566", font=("Consolas", 7),
                         wraplength=340, anchor="w").pack(fill="x", padx=16)

    def _make_detail_btn(self, parent, text: str, fg_color: str, command):
        """Create a styled button for the detail popup."""
        btn = tk.Label(
            parent, text=f" {text} ", bg="#0c1525", fg=fg_color,
            font=("Consolas", 9), cursor="hand2", pady=4,
        )
        btn.pack(side="left", padx=(0, 6), pady=4)
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.configure(bg="#1a2a3a"))
        btn.bind("<Leave>", lambda e: btn.configure(bg="#0c1525"))

    def _trigger_build(self, name: str, prompt: str):
        """Trigger the ToolForge build flow for a template or rebuild."""
        tmpl = get_template(name)
        display_name = f"Onyx {tmpl.display_name}" if tmpl else f"Onyx {name.replace('_', ' ').title()}"

        # Open chat so user sees build progress
        if not self._chat_visible:
            self._toggle_chat()

        self._append_chat(f"Building {display_name}...", "system")
        self.backend.tool_build(name, f"{prompt}\n\nApp name: {display_name}")

    # ------------------------------------------------------------------
    # Edit / Delete dialogs
    # ------------------------------------------------------------------

    def _show_edit_dialog(self, tool_name: str):
        """Show a dialog for the user to describe changes to a tool."""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit — {tool_name}")
        dialog.configure(bg=APPS_BG)
        dialog.geometry("400x180")
        dialog.transient(self.root)
        dialog.attributes("-topmost", True)

        tk.Label(dialog, text=f"What changes should Onyx make to {tool_name}?",
                 bg=APPS_BG, fg=ACCENT_MID, font=("Consolas", 9)).pack(padx=12, pady=(12, 6))

        text_frame = tk.Frame(dialog, bg=APPS_BG)
        text_frame.pack(fill="both", expand=True, padx=12, pady=4)

        text_input = tk.Text(
            text_frame, bg=CHAT_INPUT_BG, fg=CHAT_INPUT_FG,
            font=("Consolas", 10), wrap="word", height=4,
            insertbackground=ACCENT_BRIGHT, relief="flat",
            highlightthickness=1, highlightcolor=ACCENT_DIM,
            highlightbackground=APPS_CARD_BORDER,
        )
        text_input.pack(fill="both", expand=True)
        text_input.focus_set()

        btn_frame = tk.Frame(dialog, bg=APPS_BG)
        btn_frame.pack(fill="x", padx=12, pady=(4, 12))

        def _submit():
            desc = text_input.get("1.0", "end-1c").strip()
            if desc:
                dialog.destroy()
                self.backend.tool_edit(tool_name, desc)

        submit_btn = tk.Label(
            btn_frame, text=" Apply Changes ", bg=BTN_BG, fg=BTN_FG,
            font=("Consolas", 10), cursor="hand2",
        )
        submit_btn.pack(side="right")
        submit_btn.bind("<Button-1>", lambda e: _submit())
        submit_btn.bind("<Enter>", lambda e: submit_btn.configure(bg=BTN_ACTIVE_BG))
        submit_btn.bind("<Leave>", lambda e: submit_btn.configure(bg=BTN_BG))

        cancel_btn = tk.Label(
            btn_frame, text=" Cancel ", bg=APPS_BG, fg=SYSTEM_MSG_COLOR,
            font=("Consolas", 10), cursor="hand2",
        )
        cancel_btn.pack(side="right", padx=(0, 8))
        cancel_btn.bind("<Button-1>", lambda e: dialog.destroy())

        text_input.bind("<Control-Return>", lambda e: _submit())

    def _confirm_delete_tool(self, tool_name: str):
        """Show a confirmation before deleting a tool."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Delete Tool")
        dialog.configure(bg=APPS_BG)
        dialog.geometry("300x100")
        dialog.transient(self.root)
        dialog.attributes("-topmost", True)

        tk.Label(dialog, text=f"Delete {tool_name}?",
                 bg=APPS_BG, fg="#ff6666", font=("Consolas", 10, "bold")).pack(pady=(16, 8))

        btn_frame = tk.Frame(dialog, bg=APPS_BG)
        btn_frame.pack()

        def _do_delete():
            dialog.destroy()
            self.backend.tool_delete(tool_name)

        yes_btn = tk.Label(btn_frame, text=" Yes, Delete ", bg="#1a0a0a", fg="#ff4444",
                           font=("Consolas", 9), cursor="hand2")
        yes_btn.pack(side="left", padx=8)
        yes_btn.bind("<Button-1>", lambda e: _do_delete())

        no_btn = tk.Label(btn_frame, text=" Cancel ", bg=APPS_BG, fg=SYSTEM_MSG_COLOR,
                          font=("Consolas", 9), cursor="hand2")
        no_btn.pack(side="left", padx=8)
        no_btn.bind("<Button-1>", lambda e: dialog.destroy())

    # ------------------------------------------------------------------
    # Demo system
    # ------------------------------------------------------------------

    def _get_demo_runner(self):
        """Lazy-init the DemoRunner."""
        if self._demo_runner is None:
            from face.demo_runner import DemoRunner
            self._demo_runner = DemoRunner(self.backend, self.face, app=self)
        return self._demo_runner

    def _open_mirror_menu(self, event):
        """Show mirror options: analyze self or tune expressions."""
        menu = tk.Menu(self.root, tearoff=0, bg=BTN_BG, fg=BTN_FG,
                       activebackground=BTN_ACTIVE_BG, activeforeground=BTN_FG,
                       font=("Consolas", 9))
        menu.add_command(label="🪞  Analyze Self",
                         command=lambda: self.backend.analyze_self(tune_expressions=False))
        menu.add_command(label="🎨  Tune Expressions",
                         command=lambda: self.backend.analyze_self(tune_expressions=True))
        try:
            menu.tk_popup(event.x_root, event.y_root - 50)
        finally:
            menu.grab_release()

    # ------------------------------------------------------------------
    # Stage
    # ------------------------------------------------------------------

    def _open_stage_menu(self, event):
        """Show stage options: open stage, run premiere, close stage."""
        menu = tk.Menu(self.root, tearoff=0, bg=BTN_BG, fg=BTN_FG,
                       activebackground=BTN_ACTIVE_BG, activeforeground=BTN_FG,
                       font=("Consolas", 9))

        if self._stage_manager and self._stage_manager.is_open:
            menu.add_command(label="⏹  Close Stage",
                             command=self._close_stage)
            if self._show_engine and self._show_engine.is_running:
                menu.add_command(label="⏸  Pause Show",
                                 command=lambda: self._show_engine.pause())
                menu.add_command(label="⏹  Stop Show",
                                 command=lambda: self._show_engine.stop())
            else:
                menu.add_command(label="🎭  Run Premiere",
                                 command=self._run_premiere)
                menu.add_command(label="📺  Episode 1 (Pilot)",
                                 command=lambda: self._run_episode(1))
            menu.add_separator()
            menu.add_command(label="🎧  DJ Set (15 min)",
                             command=lambda: self._launch_dj_set(15))
            menu.add_command(label="🎧  DJ Set (30 min)",
                             command=lambda: self._launch_dj_set(30))
        else:
            menu.add_command(label="🎭  Open Stage",
                             command=self._launch_stage)
            menu.add_command(label="▶  Open Stage + Premiere",
                             command=lambda: self._launch_stage(run_premiere=True))
            menu.add_command(label="📺  Open Stage + Episode 1",
                             command=lambda: self._launch_stage(run_show="episode1"))
            menu.add_separator()
            menu.add_command(label="🎧  DJ Set (15 min)",
                             command=lambda: self._launch_dj_set(15))
            menu.add_command(label="🎧  DJ Set (30 min)",
                             command=lambda: self._launch_dj_set(30))
            menu.add_command(label="🎧  DJ Set (Custom...)",
                             command=self._launch_dj_set_dialog)

        try:
            menu.tk_popup(event.x_root, event.y_root - 60)
        finally:
            menu.grab_release()

    def _launch_stage(self, run_premiere: bool = False, run_show: str = ""):
        """Open the fullscreen stage."""
        from face.stage.stage_manager import StageManager

        if self._stage_manager and self._stage_manager.is_open:
            return

        self._stage_manager = StageManager(self.root, self.face)
        self._stage_manager.open(on_close=self._on_stage_closed)
        self._stage_btn.configure(fg="#aa66ff")
        self._append_chat("🎭 Stage opened. Press ESC to exit.", "system")

        if run_premiere:
            self.root.after(500, self._run_premiere)
        elif run_show == "episode1":
            self.root.after(500, lambda: self._run_episode(1))

    def _run_premiere(self):
        """Run the Premiere show on the stage."""
        if not self._stage_manager or not self._stage_manager.is_open:
            return

        from face.stage.show_engine import ShowEngine
        from face.stage.shows.premiere import get_premiere_show

        self._show_engine = ShowEngine(self._stage_manager)
        self._show_engine.on_show_end = lambda: self._append_chat(
            "🎭 Premiere show complete.", "system")
        self._show_engine.play(get_premiere_show())
        self._append_chat("🎭 Now playing: The Premiere", "system")

    def _run_episode(self, episode_num: int = 1):
        """Run a daily episode on the stage."""
        if not self._stage_manager or not self._stage_manager.is_open:
            return

        from face.stage.show_engine import ShowEngine
        from face.stage.shows.daily_episode import build_daily_episode

        self._show_engine = ShowEngine(self._stage_manager)
        self._show_engine.on_show_end = lambda: self._append_chat(
            f"📺 Episode {episode_num} complete.", "system")
        self._show_engine.play(build_daily_episode(episode_num))
        self._append_chat(f"📺 Now playing: Episode {episode_num}", "system")

    def _close_stage(self):
        """Close the stage."""
        if self._show_engine and self._show_engine.is_running:
            self._show_engine.stop()
        if self._stage_manager:
            self._stage_manager.close()
            self._stage_manager = None
        self._show_engine = None

    def _on_stage_closed(self):
        """Callback when stage is closed (via ESC or programmatically)."""
        self._stage_manager = None
        self._show_engine = None
        self._stage_btn.configure(fg=ACCENT_DIM)
        self._append_chat("🎭 Stage closed.", "system")

    # ------------------------------------------------------------------
    # DJ Set
    # ------------------------------------------------------------------

    def _launch_dj_set(self, duration_minutes: int = 15, bpm: int = 128,
                       key: str = "A minor", quality: str = "quick_draft"):
        """Launch a DJ set: open stage → generate → play."""
        self._append_chat(
            f"🎧 Starting {duration_minutes}-min DJ set ({bpm} BPM, {key}, {quality})...",
            "system",
        )

        # Switch rigged body to DJ pose + BPM nod
        if hasattr(self, '_body') and hasattr(self._body, 'set_pose'):
            self._body.set_pose("dj", smooth=True)
            self._body.set_bpm(bpm)

        def _run():
            from face.stage.dj_set_generator import DJSetGenerator
            gen = DJSetGenerator(
                bpm=bpm,
                duration_minutes=duration_minutes,
                key=key,
                quality_profile=quality,
            )
            gen.plan_set()
            plan_msg = f"🎧 Set planned: {gen.plan.num_tracks} tracks"
            try:
                self.root.after(0, lambda: self._append_chat(plan_msg, "system"))
            except Exception:
                pass

            def _on_track(track):
                msg = f"  ✅ {track.name} ({track.generation_time:.0f}s)"
                try:
                    self.root.after(0, lambda: self._append_chat(msg, "system"))
                except Exception:
                    pass

            gen.generate(
                on_track_done=_on_track,
                on_complete=lambda p: self.root.after(
                    0, lambda: self._on_dj_set_complete(p)),
                on_error=lambda e: self.root.after(
                    0, lambda: self._append_chat(f"🎧 DJ set failed: {e}", "system")),
                blocking=True,
            )

        threading.Thread(target=_run, daemon=True, name="DJSetGen").start()

    def _on_dj_set_complete(self, plan):
        """Called when DJ set generation finishes."""
        count = plan.generated_count
        total = plan.num_tracks
        self._append_chat(
            f"🎧 DJ set ready! {count}/{total} tracks generated.", "system",
        )
        if count > 0:
            paths = plan.audio_paths
            self._append_chat(
                f"🎧 Audio files in: {paths[0][:paths[0].rfind(os.sep)]}",
                "system",
            )

        # Reset body pose
        if hasattr(self, '_body') and hasattr(self._body, 'set_bpm'):
            self._body.set_bpm(0)
            self._body.set_pose("neutral", smooth=True)

    def _launch_dj_set_dialog(self):
        """Show a dialog to configure DJ set parameters."""
        dlg = tk.Toplevel(self.root)
        dlg.title("DJ Set Configuration")
        dlg.geometry("320x280")
        dlg.configure(bg=BG_COLOR)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        lbl_style = {"bg": BG_COLOR, "fg": ACCENT_MID, "font": ("Consolas", 9)}
        entry_style = {"bg": "#1a2030", "fg": ACCENT_BRIGHT, "font": ("Consolas", 10),
                       "insertbackground": ACCENT_BRIGHT, "relief": "flat", "bd": 2}

        tk.Label(dlg, text="🎧  DJ Set Configuration", font=("Consolas", 11, "bold"),
                 bg=BG_COLOR, fg=ACCENT_BRIGHT).pack(pady=(12, 8))

        # Duration
        f1 = tk.Frame(dlg, bg=BG_COLOR)
        f1.pack(fill="x", padx=20, pady=4)
        tk.Label(f1, text="Duration (min):", **lbl_style).pack(side="left")
        dur_var = tk.StringVar(value="15")
        tk.Entry(f1, textvariable=dur_var, width=6, **entry_style).pack(side="right")

        # BPM
        f2 = tk.Frame(dlg, bg=BG_COLOR)
        f2.pack(fill="x", padx=20, pady=4)
        tk.Label(f2, text="BPM:", **lbl_style).pack(side="left")
        bpm_var = tk.StringVar(value="128")
        tk.Entry(f2, textvariable=bpm_var, width=6, **entry_style).pack(side="right")

        # Key
        f3 = tk.Frame(dlg, bg=BG_COLOR)
        f3.pack(fill="x", padx=20, pady=4)
        tk.Label(f3, text="Key:", **lbl_style).pack(side="left")
        key_var = tk.StringVar(value="A minor")
        tk.Entry(f3, textvariable=key_var, width=12, **entry_style).pack(side="right")

        # Quality
        f4 = tk.Frame(dlg, bg=BG_COLOR)
        f4.pack(fill="x", padx=20, pady=4)
        tk.Label(f4, text="Quality:", **lbl_style).pack(side="left")
        qual_var = tk.StringVar(value="quick_draft")
        qual_menu = tk.OptionMenu(f4, qual_var,
                                  "quick_draft", "draft", "standard",
                                  "radio_quality", "pro")
        qual_menu.configure(bg="#1a2030", fg=ACCENT_BRIGHT, font=("Consolas", 9),
                            activebackground="#2a3040", highlightthickness=0)
        qual_menu.pack(side="right")

        def _go():
            try:
                dur = int(dur_var.get())
                bpm = int(bpm_var.get())
            except ValueError:
                return
            key = key_var.get().strip() or "A minor"
            quality = qual_var.get()
            dlg.destroy()
            self._launch_dj_set(dur, bpm, key, quality)

        tk.Button(dlg, text="🎧  Generate DJ Set", command=_go,
                  bg=ACCENT_MID, fg="white", font=("Consolas", 10, "bold"),
                  activebackground=ACCENT_BRIGHT, relief="flat", bd=0,
                  cursor="hand2").pack(pady=16)

    def _toggle_demo(self):
        """Start/stop demo, or show picker if not running."""
        runner = self._get_demo_runner()
        if runner.is_running:
            runner.stop()
            self._demo_btn.configure(fg=ACCENT_DIM)
            self._append_chat("Demo stopped.", "system")
            return
        self._open_demo_picker()

    def _open_demo_picker(self):
        """Show a scrollable dialog to pick which demo sequence to run."""
        from face.demo_runner import list_demos

        dialog = tk.Toplevel(self.root)
        dialog.title("Onyx Self-Demo")
        dialog.configure(bg=APPS_BG)
        dialog.geometry("400x560")
        dialog.transient(self.root)
        dialog.attributes("-topmost", True)

        tk.Label(dialog, text="SELF-DEMO", font=("Consolas", 14, "bold"),
                 bg=APPS_BG, fg=ACCENT_BRIGHT).pack(pady=(14, 4))
        tk.Label(dialog, text="Pick an episode. Each showcases one capability.",
                 font=("Consolas", 9), bg=APPS_BG, fg=ACCENT_DIM).pack(pady=(0, 6))

        # Record checkbox + mode hint
        record_var = tk.BooleanVar(value=False)
        rec_frame = tk.Frame(dialog, bg=APPS_BG)
        rec_frame.pack(fill="x", padx=16, pady=(0, 6))
        rec_cb = tk.Checkbutton(
            rec_frame, text="Record to MP4 (YouTuber mode)", variable=record_var,
            bg=APPS_BG, fg=ACCENT_DIM, selectcolor=APPS_CARD_BG,
            activebackground=APPS_BG, activeforeground=ACCENT_BRIGHT,
            font=("Consolas", 8),
        )
        rec_cb.pack(side="left")
        mode_hint = tk.Label(rec_frame, text="live", font=("Consolas", 8),
                             bg=APPS_BG, fg=ACCENT_DIM)
        mode_hint.pack(side="right", padx=4)

        def _update_mode_hint():
            if record_var.get():
                mode_hint.configure(text="recording", fg="#ff5555")
            else:
                mode_hint.configure(text="live", fg=ACCENT_DIM)
        rec_cb.configure(command=_update_mode_hint)

        # Scrollable frame for demo cards
        canvas = tk.Canvas(dialog, bg=APPS_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=APPS_BG)

        scroll_frame.bind("<Configure>",
                          lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=380)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0))
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        dialog.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        demos = list_demos()
        for demo in demos:
            card = tk.Frame(scroll_frame, bg=APPS_CARD_BG,
                            highlightbackground=APPS_CARD_BORDER,
                            highlightthickness=1, cursor="hand2")
            card.pack(fill="x", padx=6, pady=3)

            title_f = tk.Frame(card, bg=APPS_CARD_BG)
            title_f.pack(fill="x", padx=10, pady=(5, 1))
            tk.Label(title_f, text=demo["title"], font=("Consolas", 9, "bold"),
                     bg=APPS_CARD_BG, fg=ACCENT_BRIGHT).pack(side="left")
            est = demo["estimated_time"]
            time_str = f"{est // 60}m {est % 60}s" if est >= 60 else f"{est}s"
            tk.Label(title_f, text=f"~{time_str}",
                     font=("Consolas", 7), bg=APPS_CARD_BG, fg=ACCENT_DIM).pack(side="right")

            tk.Label(card, text=demo["description"], font=("Consolas", 7),
                     bg=APPS_CARD_BG, fg=BOT_MSG_COLOR, wraplength=340, justify="left"
                     ).pack(padx=10, pady=(0, 5), anchor="w")

            demo_id = demo["id"]

            def _on_click(e, did=demo_id):
                rec = record_var.get()
                dialog.destroy()
                self._start_demo(did, record=rec)

            card.bind("<Button-1>", _on_click)
            for child in card.winfo_children():
                child.bind("<Button-1>", _on_click)
                for sub in child.winfo_children():
                    sub.bind("<Button-1>", _on_click)

            card.bind("<Enter>", lambda e, c=card: c.configure(highlightbackground=ACCENT_MID))
            card.bind("<Leave>", lambda e, c=card: c.configure(highlightbackground=APPS_CARD_BORDER))

    # Show-based demos — fullscreen episode mode via ShowEngine
    _SHOW_DEMOS = {
        "beat": ("face.stage.shows.beat_demo", "build_beat_demo"),
    }

    def _start_demo(self, sequence_id: str, record: bool = False,
                    auto_exit: bool = False):
        """Start a demo sequence — opens chat panel and begins.

        Show-based demos (registered in _SHOW_DEMOS) launch the fullscreen
        stage with ShowEngine for rich panels, backgrounds, and animations.
        All other demos use the standard DemoRunner (DemoSequence steps).

        NOTE: This may be called from a background thread (cmd_demo's
        _auto_start). Show demos need Tkinter widgets, so we schedule
        their entire flow on the main thread via root.after.
        """
        # Check if this is a Show-based demo — schedule on main thread
        if sequence_id in self._SHOW_DEMOS:
            self.root.after(0, lambda: self._start_show_demo(
                sequence_id, record=record, auto_exit=auto_exit))
            return

        if not self._chat_visible:
            self._toggle_chat()
        self._demo_btn.configure(fg="#ff8844")
        self._append_chat(f"🎬 Starting demo: {sequence_id}"
                          + (" (recording)" if record else ""), "system")
        runner = self._get_demo_runner()
        runner.start(sequence_id, record=record, auto_exit=auto_exit)

    def _start_show_demo(self, sequence_id: str, record: bool = False,
                         auto_exit: bool = False):
        """Launch a Show-based demo on the fullscreen stage.

        MUST run on the main (Tkinter) thread.
        """
        import importlib

        if not self._chat_visible:
            self._toggle_chat()
        self._demo_btn.configure(fg="#ff8844")

        module_path, builder_name = self._SHOW_DEMOS[sequence_id]
        self._append_chat(
            f"🎭 Starting fullscreen episode: {sequence_id}", "system")

        # Import the show builder
        try:
            mod = importlib.import_module(module_path)
            builder = getattr(mod, builder_name)
            show = builder()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self._append_chat(f"❌ Failed to build show: {exc}", "system")
            return

        # Open stage if not already open
        self._launch_stage()

        # Optional: start recording (use module-level singleton so hooks
        # in stage_manager and beat_demo can find the active recorder)
        recording = False
        if record:
            try:
                import core.screen_recorder as _sr
                # Reset singleton so fresh options take effect
                _sr._default_recorder = None
                rec = _sr.get_recorder(fps=20, quality="high", capture_audio=True)
                path = rec.start(f"show_demo_{sequence_id}")
                recording = True
                self._append_chat(f"🔴 Recording → {path}", "system")
            except Exception as exc:
                self._append_chat(f"⚠ Recording failed: {exc}", "system")

        def _on_show_done():
            if recording:
                try:
                    from core.screen_recorder import stop_recording
                    info = stop_recording()
                    if info:
                        mb = info.size_bytes / (1024 * 1024)
                        self._append_chat(
                            f"🎬 Recording saved: {info.path} ({mb:.1f} MB)",
                            "system")
                except Exception:
                    pass
            self._append_chat(
                f"🎭 Episode complete: {show.title}", "system")
            self._demo_btn.configure(fg=ACCENT_DIM)
            if auto_exit:
                self.root.after(2000, self.root.destroy)

        # Start the show via ShowEngine after a short delay for stage to settle
        def _launch_show():
            try:
                from face.stage.show_engine import ShowEngine
                if not self._stage_manager or not self._stage_manager.is_open:
                    self._append_chat("❌ Stage failed to open", "system")
                    return
                self._show_engine = ShowEngine(self._stage_manager)
                self._show_engine.on_show_end = _on_show_done
                self._show_engine.play(show)
                self._append_chat(
                    f"🎭 Now playing: {show.title}", "system")
            except Exception as exc:
                import traceback
                traceback.print_exc()
                self._append_chat(f"❌ Show launch failed: {exc}", "system")

        self.root.after(1500, _launch_show)

    # ------------------------------------------------------------------
    # Body toggle (radial menu)
    # ------------------------------------------------------------------

    def _toggle_body(self):
        """Toggle body visibility and persist the setting."""
        if not hasattr(self, '_body'):
            return
        new_vis = not self._body.is_visible
        self._body.set_visible(new_vis)
        # Persist immediately
        onyx_settings.set("body_visible", new_vis)
        self._append_chat(f"Body {'shown' if new_vis else 'hidden'}.", "system")

    # ------------------------------------------------------------------
    # Screen recording (standalone)
    # ------------------------------------------------------------------

    def _toggle_recording(self):
        """Start/stop standalone screen recording."""
        if self._is_recording:
            self._stop_standalone_recording()
        else:
            self._start_standalone_recording()

    def _start_standalone_recording(self):
        """Start recording the screen."""
        try:
            from core.screen_recorder import ScreenRecorder
            self._screen_recorder = ScreenRecorder(fps=20, quality="high")
            path = self._screen_recorder.start("onyx_session")
            self._is_recording = True
            self._record_btn.configure(fg="#ff3333", text=" ⏺ REC ")
            self._append_chat(f"🔴 Recording → {path}", "system")
        except Exception as exc:
            self._append_chat(f"Recording failed: {exc}", "system")

    def _stop_standalone_recording(self):
        """Stop recording and save the file."""
        if not self._screen_recorder:
            return
        try:
            info = self._screen_recorder.stop()
            self._is_recording = False
            self._screen_recorder = None
            self._record_btn.configure(fg=ACCENT_DIM, text=" ⏺ Rec ")
            if info:
                mb = info.size_bytes / (1024 * 1024)
                self._append_chat(
                    f"⬛ Saved: {info.path} ({mb:.1f} MB, {info.duration:.0f}s)",
                    "system",
                )
        except Exception as exc:
            self._append_chat(f"Stop recording failed: {exc}", "system")
            self._is_recording = False
            self._screen_recorder = None
            self._record_btn.configure(fg=ACCENT_DIM, text=" ⏺ Rec ")

    # ------------------------------------------------------------------
    # Settings dialog
    # ------------------------------------------------------------------

    def _open_settings(self):
        """Open a settings dialog for user preferences and face customization."""
        settings = onyx_settings.load_settings()

        dialog = tk.Toplevel(self.root)
        dialog.title("Onyx Settings")
        dialog.configure(bg=APPS_BG)
        dialog.geometry("440x820")
        dialog.minsize(380, 400)
        dialog.transient(self.root)
        dialog.attributes("-topmost", True)

        # Scrollable canvas + visible scrollbar
        scroll_frame = tk.Frame(dialog, bg=APPS_BG)
        scroll_frame.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(scroll_frame, orient="vertical",
                                 bg=APPS_BG, troughcolor="#0a1220",
                                 highlightthickness=0, borderwidth=0)
        scrollbar.pack(side="right", fill="y")

        canvas = tk.Canvas(scroll_frame, bg=APPS_BG, highlightthickness=0,
                           yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=canvas.yview)

        inner = tk.Frame(canvas, bg=APPS_BG)
        canvas_win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _on_inner_configure)

        def _on_canvas_configure(e):
            canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mousewheel scrolling (bind to dialog so it works everywhere)
        def _on_mousewheel(e):
            canvas.yview_scroll(-1 * (e.delta // 120), "units")
        dialog.bind("<MouseWheel>", _on_mousewheel)

        tk.Label(inner, text="SETTINGS", font=("Consolas", 14, "bold"),
                 bg=APPS_BG, fg=ACCENT_BRIGHT).pack(pady=(14, 4))

        # --- Section: Profile ---
        tk.Label(inner, text="Profile", font=("Consolas", 10, "bold"),
                 bg=APPS_BG, fg=ACCENT_MID).pack(anchor="w", padx=20, pady=(8, 2))

        fields = {}

        def _field(parent, label, key, show=None):
            f = tk.Frame(parent, bg=APPS_BG)
            f.pack(fill="x", padx=20, pady=3)
            tk.Label(f, text=label, bg=APPS_BG, fg=ACCENT_DIM,
                     font=("Consolas", 9), width=16, anchor="w").pack(side="left")
            var = tk.StringVar(value=settings.get(key, ""))
            e = tk.Entry(f, textvariable=var, bg=CHAT_INPUT_BG, fg=CHAT_INPUT_FG,
                         font=("Consolas", 10), insertbackground=ACCENT_BRIGHT,
                         relief="flat", show=show or "")
            e.pack(side="left", fill="x", expand=True, ipady=2)
            fields[key] = var

        _field(inner, "Your Name:", "user_name")
        _field(inner, "ElevenLabs Key:", "elevenlabs_api_key", show="*")
        _field(inner, "Voice ID (Onyx):", "elevenlabs_voice_id")
        _field(inner, "Voice ID (Xyno):", "xyno_voice_id")

        # Checkboxes
        checks = {}
        for label, key in [("TTS Enabled", "tts_enabled"),
                            ("Xyno Co-host", "xyno_enabled"),
                            ("Idle Tasks", "idle_tasks_enabled"),
                            ("Night Mode (3-6am)", "idle_night_mode")]:
            var = tk.BooleanVar(value=settings.get(key, True))
            tk.Checkbutton(inner, text=label, variable=var, bg=APPS_BG, fg=ACCENT_MID,
                           selectcolor=CHAT_INPUT_BG, activebackground=APPS_BG,
                           activeforeground=ACCENT_BRIGHT, font=("Consolas", 9)
                           ).pack(anchor="w", padx=24, pady=1)
            checks[key] = var

        # --- Section: Voice ---
        tk.Frame(inner, bg=ACCENT_DIM, height=1).pack(fill="x", padx=20, pady=(10, 6))
        tk.Label(inner, text="Voice", font=("Consolas", 10, "bold"),
                 bg=APPS_BG, fg=ACCENT_MID).pack(anchor="w", padx=20, pady=(2, 4))

        # TTS Engine selector
        _tts_engines = {
            "auto": {"label": "Auto (best available)"},
            "fish": {"label": "Fish Audio S2"},
            "elevenlabs": {"label": "ElevenLabs"},
            "edge": {"label": "Edge TTS (Microsoft)"},
            "system": {"label": "System (Windows SAPI)"},
        }

        # Edge TTS voice selector
        _edge_voices = {
            "en-US-GuyNeural": {"label": "Guy (US Male)"},
            "en-US-ChristopherNeural": {"label": "Christopher (US Male)"},
            "en-US-EricNeural": {"label": "Eric (US Male)"},
            "en-US-AriaNeural": {"label": "Aria (US Female)"},
            "en-US-JennyNeural": {"label": "Jenny (US Female)"},
            "en-GB-RyanNeural": {"label": "Ryan (UK Male)"},
            "en-GB-SoniaNeural": {"label": "Sonia (UK Female)"},
            "en-AU-WilliamNeural": {"label": "William (AU Male)"},
            "en-IN-PrabhatNeural": {"label": "Prabhat (IN Male)"},
        }

        # We'll add these via the existing _dropdown mechanism after it's defined
        _voice_dropdown_pending = [
            ("TTS Engine:", "tts_engine", _tts_engines,
             settings.get("tts_engine", "auto")),
            ("Edge Voice:", "edge_tts_voice", _edge_voices,
             settings.get("edge_tts_voice", "en-US-GuyNeural")),
        ]

        # Fish Audio S2 config fields
        _field(inner, "Fish API Key:", "fish_audio_api_key", show="*")
        _field(inner, "Fish Voice ID:", "fish_audio_voice_id")

        # SFX budget field
        _field(inner, "ElevenLabs SFX Budget/ep:", "elevenlabs_sfx_budget")

        # Shared dict for all dropdown widgets (personality + face + voice)
        dropdowns = {}

        # --- Section: Personality ---
        tk.Frame(inner, bg=ACCENT_DIM, height=1).pack(fill="x", padx=20, pady=(10, 6))
        tk.Label(inner, text="Personality", font=("Consolas", 10, "bold"),
                 bg=APPS_BG, fg=ACCENT_MID).pack(anchor="w", padx=20, pady=(2, 4))

        # Personality preset selector
        try:
            from core.personality_manager import get_personality_manager
            manager = get_personality_manager()
            presets = manager.list_presets()
            active_preset = manager.get_active_preset()
            current_preset = active_preset.name if active_preset else "OnyxKraken Default"
            
            # Build preset options dict
            preset_options = {name: {"label": name} for name in presets}
            
            # Personality dropdown with live preview
            f = tk.Frame(inner, bg=APPS_BG)
            f.pack(fill="x", padx=20, pady=3)
            tk.Label(f, text="Preset:", bg=APPS_BG, fg=ACCENT_DIM,
                     font=("Consolas", 9), width=16, anchor="w").pack(side="left")
            
            preset_var = tk.StringVar(value=current_preset)
            om = tk.OptionMenu(f, preset_var, *presets)
            om.configure(bg=CHAT_INPUT_BG, fg=CHAT_INPUT_FG, font=("Consolas", 9),
                         highlightthickness=0, relief="flat", activebackground=APPS_BG,
                         activeforeground=ACCENT_BRIGHT)
            om["menu"].configure(bg=CHAT_INPUT_BG, fg=CHAT_INPUT_FG, font=("Consolas", 9),
                                 activebackground=ACCENT_DIM, activeforeground=ACCENT_BRIGHT)
            om.pack(side="left", fill="x", expand=True)
            
            # Store in dropdowns dict for saving
            dropdowns["personality_preset"] = (preset_var, {name: name for name in presets})
            
            # Preview panel showing personality traits
            preview_frame = tk.Frame(inner, bg=APPS_CARD_BG, highlightbackground=APPS_CARD_BORDER,
                                     highlightthickness=1)
            preview_frame.pack(fill="x", padx=20, pady=4)
            
            preview_labels = {}
            
            def _update_preview(*args):
                selected = preset_var.get()
                preset = manager.get_preset(selected)
                if preset:
                    # Clear existing labels
                    for widget in preview_frame.winfo_children():
                        widget.destroy()
                    
                    # Show preset info
                    tk.Label(preview_frame, text=f"  {preset.identity.get('role', 'N/A')}",
                             bg=APPS_CARD_BG, fg=ACCENT_MID, font=("Consolas", 8),
                             anchor="w").pack(fill="x", padx=8, pady=(4, 2))
                    
                    # Trait bars
                    traits = [
                        ("Humor", preset.get_humor_level(), "#ff8844"),
                        ("Formality", preset.get_formality_level(), "#44aaff"),
                        ("Verbosity", preset.get_verbosity_level(), "#88ff44"),
                    ]
                    
                    for trait_name, level, color in traits:
                        row = tk.Frame(preview_frame, bg=APPS_CARD_BG)
                        row.pack(fill="x", padx=8, pady=1)
                        tk.Label(row, text=f"{trait_name}:", bg=APPS_CARD_BG, fg=ACCENT_DIM,
                                 font=("Consolas", 7), width=10, anchor="w").pack(side="left")
                        
                        # Bar background
                        bar_bg = tk.Frame(row, bg="#0a1220", height=8)
                        bar_bg.pack(side="left", fill="x", expand=True)
                        
                        # Bar fill
                        bar_fill = tk.Frame(bar_bg, bg=color, height=8)
                        bar_fill.place(x=0, y=0, relwidth=level/10, relheight=1.0)
                        
                        tk.Label(row, text=f"{level}/10", bg=APPS_CARD_BG, fg=color,
                                 font=("Consolas", 7), width=4).pack(side="left", padx=2)
                    
                    # Behavior flags
                    flags = []
                    if preset.should_use_emoji():
                        flags.append("😊 Emoji")
                    if preset.should_use_memes():
                        flags.append("🎭 Memes")
                    if preset.should_use_self_deprecating_humor():
                        flags.append("😅 Self-humor")
                    
                    if flags:
                        tk.Label(preview_frame, text="  " + " • ".join(flags),
                                 bg=APPS_CARD_BG, fg="#6a7a8a", font=("Consolas", 7),
                                 anchor="w").pack(fill="x", padx=8, pady=(2, 4))
            
            preset_var.trace_add("write", _update_preview)
            _update_preview()  # Initial preview
            
        except Exception as e:
            tk.Label(inner, text=f"  Personality system unavailable: {e}",
                     bg=APPS_BG, fg="#ff6666", font=("Consolas", 7),
                     wraplength=360).pack(anchor="w", padx=24, pady=2)

        # --- Section: Face Customization ---
        tk.Frame(inner, bg=ACCENT_DIM, height=1).pack(fill="x", padx=20, pady=(10, 6))
        tk.Label(inner, text="Face Customization", font=("Consolas", 10, "bold"),
                 bg=APPS_BG, fg=ACCENT_MID).pack(anchor="w", padx=20, pady=(2, 4))

        def _dropdown(parent, label, key, options_dict, current_val):
            f = tk.Frame(parent, bg=APPS_BG)
            f.pack(fill="x", padx=20, pady=3)
            tk.Label(f, text=label, bg=APPS_BG, fg=ACCENT_DIM,
                     font=("Consolas", 9), width=16, anchor="w").pack(side="left")
            # Build label→key mapping
            labels = []
            label_to_key = {}
            key_to_label = {}
            for k, v in options_dict.items():
                lbl = v.get("label", k) if isinstance(v, dict) else k
                labels.append(lbl)
                label_to_key[lbl] = k
                key_to_label[k] = lbl
            var = tk.StringVar(value=key_to_label.get(current_val, labels[0] if labels else ""))
            om = tk.OptionMenu(f, var, *labels)
            om.configure(bg=CHAT_INPUT_BG, fg=CHAT_INPUT_FG, font=("Consolas", 9),
                         highlightthickness=0, relief="flat", activebackground=APPS_BG,
                         activeforeground=ACCENT_BRIGHT)
            om["menu"].configure(bg=CHAT_INPUT_BG, fg=CHAT_INPUT_FG, font=("Consolas", 9),
                                 activebackground=ACCENT_DIM, activeforeground=ACCENT_BRIGHT)
            om.pack(side="left", fill="x", expand=True)
            dropdowns[key] = (var, label_to_key)

            # Live preview on change
            def _on_change(*args):
                selected_label = var.get()
                selected_key = label_to_key.get(selected_label, current_val)
                if hasattr(self, 'face'):
                    kwargs = {key: selected_key}
                    # Map setting key to apply_customization param
                    param_map = {"face_theme": "theme", "eye_style": "eye_style",
                                 "face_shape": "face_shape", "accessory": "accessory"}
                    param = param_map.get(key)
                    if param:
                        self.face.apply_customization(**{param: selected_key})
            var.trace_add("write", _on_change)

        # Render voice dropdowns now that _dropdown is defined
        for lbl, key, opts, cur in _voice_dropdown_pending:
            _dropdown(inner, lbl, key, opts, cur)

        # Load spec catalogs
        from face.face_gui import _THEMES, _EYE_STYLES, _FACE_SHAPES, _ACCESSORIES
        _dropdown(inner, "Color Theme:", "face_theme", _THEMES, settings.get("face_theme", "cyan"))
        _dropdown(inner, "Eye Style:", "eye_style", _EYE_STYLES, settings.get("eye_style", "default"))
        _dropdown(inner, "Face Shape:", "face_shape", _FACE_SHAPES, settings.get("face_shape", "default"))
        _dropdown(inner, "Accessory:", "accessory", _ACCESSORIES, settings.get("accessory", "none"))

        # Scan lines checkbox
        scan_var = tk.BooleanVar(value=settings.get("scan_lines", True))
        def _on_scan_change(*args):
            if hasattr(self, 'face'):
                self.face.apply_customization(scan_lines=scan_var.get())
        scan_var.trace_add("write", _on_scan_change)
        tk.Checkbutton(inner, text="CRT Scan Lines", variable=scan_var, bg=APPS_BG, fg=ACCENT_MID,
                       selectcolor=CHAT_INPUT_BG, activebackground=APPS_BG,
                       activeforeground=ACCENT_BRIGHT, font=("Consolas", 9)
                       ).pack(anchor="w", padx=24, pady=1)
        checks["scan_lines"] = scan_var

        # --- Section: Custom Accent Color ---
        accent_f = tk.Frame(inner, bg=APPS_BG)
        accent_f.pack(fill="x", padx=20, pady=3)
        tk.Label(accent_f, text="Custom Accent:", bg=APPS_BG, fg=ACCENT_DIM,
                 font=("Consolas", 9), width=16, anchor="w").pack(side="left")
        accent_var = tk.StringVar(value=settings.get("custom_accent_color", ""))
        accent_entry = tk.Entry(accent_f, textvariable=accent_var, bg=CHAT_INPUT_BG,
                                fg=CHAT_INPUT_FG, font=("Consolas", 10),
                                insertbackground=ACCENT_BRIGHT, relief="flat", width=9)
        accent_entry.pack(side="left", padx=(0, 4), ipady=2)
        accent_preview = tk.Label(accent_f, text="  ●  ", bg=APPS_BG,
                                  fg=accent_var.get() or ACCENT_BRIGHT,
                                  font=("Consolas", 14))
        accent_preview.pack(side="left")
        tk.Label(accent_f, text="(#hex or empty)", bg=APPS_BG, fg="#556677",
                 font=("Consolas", 7)).pack(side="left", padx=4)

        def _on_accent_change(*args):
            val = accent_var.get().strip()
            if val and val.startswith("#") and len(val) == 7:
                accent_preview.configure(fg=val)
                if hasattr(self, 'face'):
                    self.face.apply_customization(custom_accent=val)
            elif not val:
                accent_preview.configure(fg=ACCENT_BRIGHT)
                # Revert to theme default
                theme_key = dropdowns.get("face_theme", (None, {}))[0]
                if theme_key:
                    lbl = theme_key.get()
                    key = dropdowns["face_theme"][1].get(lbl, "cyan")
                    if hasattr(self, 'face'):
                        self.face.apply_theme(key)
        accent_var.trace_add("write", _on_accent_change)
        fields["custom_accent_color"] = accent_var

        # --- Section: Geometry ---
        tk.Frame(inner, bg=ACCENT_DIM, height=1).pack(fill="x", padx=20, pady=(10, 6))
        tk.Label(inner, text="Face Geometry", font=("Consolas", 10, "bold"),
                 bg=APPS_BG, fg=ACCENT_MID).pack(anchor="w", padx=20, pady=(2, 4))

        geo_sliders = {}
        cur_geo = settings.get("geometry", {})
        from face.face_gui import _SPEC as _FACE_SPEC
        _geo_defaults = _FACE_SPEC["geometry"]

        def _geo_slider(label, key, from_, to_, resolution):
            initial = cur_geo.get(key, _geo_defaults.get(key, (from_ + to_) / 2))
            f = tk.Frame(inner, bg=APPS_BG)
            f.pack(fill="x", padx=20, pady=1)
            tk.Label(f, text=label, bg=APPS_BG, fg=ACCENT_DIM,
                     font=("Consolas", 9), width=16, anchor="w").pack(side="left")
            val_lbl = tk.Label(f, text=str(round(initial, 1)), bg=APPS_BG,
                               fg=ACCENT_BRIGHT, font=("Consolas", 9), width=6, anchor="e")
            val_lbl.pack(side="right")
            s = tk.Scale(f, from_=from_, to=to_, orient="horizontal",
                         resolution=resolution, bg=APPS_BG, fg=ACCENT_MID,
                         troughcolor=CHAT_INPUT_BG, highlightthickness=0,
                         sliderrelief="flat", font=("Consolas", 7),
                         showvalue=False, length=120, activebackground=ACCENT_BRIGHT)
            s.set(initial)
            def _changed(v, k=key):
                val_lbl.configure(text=str(round(float(v), 1)))
                if hasattr(self, 'face'):
                    self.face.apply_geometry(**{k: float(v)})
            s.configure(command=_changed)
            s.pack(side="left", fill="x", expand=True, padx=(4, 4))
            geo_sliders[key] = s

        _geo_slider("Eye Width:", "eye_width", 20, 90, 1)
        _geo_slider("Eye Height:", "eye_height", 20, 100, 1)
        _geo_slider("Eye Spacing:", "eye_spacing", 40, 180, 2)
        _geo_slider("Eye Y:", "eye_y", 60, 200, 2)
        _geo_slider("Pupil Size:", "pupil_radius", 5, 30, 1)
        _geo_slider("Mouth Y:", "mouth_y", 180, 320, 2)
        _geo_slider("Mouth Width:", "mouth_width", 20, 140, 2)

        # Reset geometry button
        def _reset_geo():
            for key, s in geo_sliders.items():
                s.set(_geo_defaults.get(key, 0))
            if hasattr(self, 'face'):
                self.face.apply_geometry(**_geo_defaults)
        reset_geo_f = tk.Frame(inner, bg=APPS_BG)
        reset_geo_f.pack(fill="x", padx=20, pady=2)
        reset_geo_btn = tk.Label(reset_geo_f, text=" Reset Geometry ",
                                 bg=CHAT_INPUT_BG, fg=ACCENT_DIM,
                                 font=("Consolas", 8), cursor="hand2", padx=6, pady=2)
        reset_geo_btn.pack(side="right")
        reset_geo_btn.bind("<Button-1>", lambda e: _reset_geo())
        reset_geo_btn.bind("<Enter>", lambda e: reset_geo_btn.configure(fg=ACCENT_BRIGHT))
        reset_geo_btn.bind("<Leave>", lambda e: reset_geo_btn.configure(fg=ACCENT_DIM))

        # --- Section: Animation ---
        tk.Frame(inner, bg=ACCENT_DIM, height=1).pack(fill="x", padx=20, pady=(10, 6))
        tk.Label(inner, text="Animation", font=("Consolas", 10, "bold"),
                 bg=APPS_BG, fg=ACCENT_MID).pack(anchor="w", padx=20, pady=(2, 4))

        anim_sliders = {}
        cur_anim = settings.get("animation", {})
        _anim_defaults = _FACE_SPEC["animation"]

        def _anim_slider(label, key, spec_key, from_, to_, resolution):
            initial = cur_anim.get(key, _anim_defaults.get(spec_key, (from_ + to_) / 2))
            f = tk.Frame(inner, bg=APPS_BG)
            f.pack(fill="x", padx=20, pady=1)
            tk.Label(f, text=label, bg=APPS_BG, fg=ACCENT_DIM,
                     font=("Consolas", 9), width=16, anchor="w").pack(side="left")
            val_lbl = tk.Label(f, text=str(round(initial, 2)), bg=APPS_BG,
                               fg=ACCENT_BRIGHT, font=("Consolas", 9), width=6, anchor="e")
            val_lbl.pack(side="right")
            s = tk.Scale(f, from_=from_, to=to_, orient="horizontal",
                         resolution=resolution, bg=APPS_BG, fg=ACCENT_MID,
                         troughcolor=CHAT_INPUT_BG, highlightthickness=0,
                         sliderrelief="flat", font=("Consolas", 7),
                         showvalue=False, length=120, activebackground=ACCENT_BRIGHT)
            s.set(initial)
            def _changed(v, k=key):
                val_lbl.configure(text=str(round(float(v), 2)))
                if hasattr(self, 'face'):
                    self.face.apply_animation(**{k: float(v)})
            s.configure(command=_changed)
            s.pack(side="left", fill="x", expand=True, padx=(4, 4))
            anim_sliders[key] = (s, spec_key)

        _anim_slider("Blink Min:", "blink_min", "blink_interval_min", 0.5, 10.0, 0.25)
        _anim_slider("Blink Max:", "blink_max", "blink_interval_max", 2.0, 15.0, 0.25)
        _anim_slider("Blink Speed:", "blink_duration", "blink_duration", 0.04, 0.5, 0.02)
        _anim_slider("Gaze Speed:", "gaze_speed", "gaze_speed", 1.0, 15.0, 0.5)
        _anim_slider("Gaze Min:", "gaze_change_min", "gaze_change_min", 0.2, 5.0, 0.1)
        _anim_slider("Gaze Max:", "gaze_change_max", "gaze_change_max", 1.0, 10.0, 0.25)

        # Reset animation button
        def _reset_anim():
            _anim_map = {
                "blink_min": "blink_interval_min", "blink_max": "blink_interval_max",
                "blink_duration": "blink_duration", "gaze_speed": "gaze_speed",
                "gaze_change_min": "gaze_change_min", "gaze_change_max": "gaze_change_max",
            }
            for key, (s, spec_key) in anim_sliders.items():
                s.set(_anim_defaults.get(spec_key, 1.0))
            if hasattr(self, 'face'):
                self.face.apply_animation(
                    **{k: _anim_defaults[v] for k, v in _anim_map.items() if v in _anim_defaults})
        reset_anim_f = tk.Frame(inner, bg=APPS_BG)
        reset_anim_f.pack(fill="x", padx=20, pady=2)
        reset_anim_btn = tk.Label(reset_anim_f, text=" Reset Animation ",
                                  bg=CHAT_INPUT_BG, fg=ACCENT_DIM,
                                  font=("Consolas", 8), cursor="hand2", padx=6, pady=2)
        reset_anim_btn.pack(side="right")
        reset_anim_btn.bind("<Button-1>", lambda e: _reset_anim())
        reset_anim_btn.bind("<Enter>", lambda e: reset_anim_btn.configure(fg=ACCENT_BRIGHT))
        reset_anim_btn.bind("<Leave>", lambda e: reset_anim_btn.configure(fg=ACCENT_DIM))

        # --- Section: Face Presets ---
        tk.Frame(inner, bg=ACCENT_DIM, height=1).pack(fill="x", padx=20, pady=(10, 6))
        tk.Label(inner, text="Face Presets", font=("Consolas", 10, "bold"),
                 bg=APPS_BG, fg=ACCENT_MID).pack(anchor="w", padx=20, pady=(2, 4))

        saved_presets = dict(settings.get("face_presets", {}))
        preset_list_frame = tk.Frame(inner, bg=APPS_BG)
        preset_list_frame.pack(fill="x", padx=20, pady=2)

        def _gather_current_face_config():
            """Gather current face customization state into a dict."""
            cfg = {}
            # Theme
            if "face_theme" in dropdowns:
                lbl = dropdowns["face_theme"][0].get()
                cfg["face_theme"] = dropdowns["face_theme"][1].get(lbl, "cyan")
            cfg["eye_style"] = dropdowns.get("eye_style", (None, {}))[0].get() if "eye_style" in dropdowns else "default"
            if "eye_style" in dropdowns:
                cfg["eye_style"] = dropdowns["eye_style"][1].get(cfg["eye_style"], "default")
            cfg["face_shape"] = dropdowns.get("face_shape", (None, {}))[0].get() if "face_shape" in dropdowns else "default"
            if "face_shape" in dropdowns:
                cfg["face_shape"] = dropdowns["face_shape"][1].get(cfg["face_shape"], "default")
            cfg["accessory"] = dropdowns.get("accessory", (None, {}))[0].get() if "accessory" in dropdowns else "none"
            if "accessory" in dropdowns:
                cfg["accessory"] = dropdowns["accessory"][1].get(cfg["accessory"], "none")
            cfg["scan_lines"] = scan_var.get()
            cfg["custom_accent_color"] = accent_var.get().strip()
            cfg["geometry"] = {k: round(s.get(), 1) for k, s in geo_sliders.items()}
            cfg["animation"] = {k: round(s.get(), 2) for k, (s, _) in anim_sliders.items()}
            return cfg

        def _apply_preset(cfg):
            """Apply a saved preset config to all controls."""
            # Theme
            if "face_theme" in cfg and "face_theme" in dropdowns:
                var, l2k = dropdowns["face_theme"]
                k2l = {v: k for k, v in l2k.items()}
                if cfg["face_theme"] in k2l:
                    var.set(k2l[cfg["face_theme"]])
            for dd_key in ("eye_style", "face_shape", "accessory"):
                if dd_key in cfg and dd_key in dropdowns:
                    var, l2k = dropdowns[dd_key]
                    k2l = {v: k for k, v in l2k.items()}
                    if cfg[dd_key] in k2l:
                        var.set(k2l[cfg[dd_key]])
            if "scan_lines" in cfg:
                scan_var.set(cfg["scan_lines"])
            if "custom_accent_color" in cfg:
                accent_var.set(cfg["custom_accent_color"])
            if "geometry" in cfg:
                for k, v in cfg["geometry"].items():
                    if k in geo_sliders:
                        geo_sliders[k].set(v)
            if "animation" in cfg:
                for k, v in cfg["animation"].items():
                    if k in anim_sliders:
                        anim_sliders[k][0].set(v)

        def _rebuild_preset_list():
            for w in preset_list_frame.winfo_children():
                w.destroy()
            if not saved_presets:
                tk.Label(preset_list_frame, text="  No saved presets yet",
                         bg=APPS_BG, fg="#556677", font=("Consolas", 8)).pack(anchor="w")
                return
            for name, cfg in saved_presets.items():
                row = tk.Frame(preset_list_frame, bg=APPS_BG)
                row.pack(fill="x", pady=1)
                # Color swatch
                swatch_c = cfg.get("custom_accent_color", "") or "#00d4ff"
                tk.Label(row, text=" ● ", bg=APPS_BG, fg=swatch_c,
                         font=("Consolas", 10)).pack(side="left")
                lbl = tk.Label(row, text=name, bg=APPS_BG, fg=ACCENT_MID,
                               font=("Consolas", 9), cursor="hand2")
                lbl.pack(side="left")
                lbl.bind("<Button-1>", lambda e, c=cfg: _apply_preset(c))
                lbl.bind("<Enter>", lambda e, l=lbl: l.configure(fg=ACCENT_BRIGHT))
                lbl.bind("<Leave>", lambda e, l=lbl: l.configure(fg=ACCENT_MID))
                del_lbl = tk.Label(row, text=" x ", bg=APPS_BG, fg="#664444",
                                   font=("Consolas", 8), cursor="hand2")
                del_lbl.pack(side="right")
                def _del(n=name):
                    saved_presets.pop(n, None)
                    _rebuild_preset_list()
                del_lbl.bind("<Button-1>", lambda e, n=name: _del(n))
                del_lbl.bind("<Enter>", lambda e, l=del_lbl: l.configure(fg="#ff4444"))
                del_lbl.bind("<Leave>", lambda e, l=del_lbl: l.configure(fg="#664444"))

        _rebuild_preset_list()

        # Save new preset row
        save_preset_f = tk.Frame(inner, bg=APPS_BG)
        save_preset_f.pack(fill="x", padx=20, pady=4)
        preset_name_var = tk.StringVar(value="")
        tk.Label(save_preset_f, text="Name:", bg=APPS_BG, fg=ACCENT_DIM,
                 font=("Consolas", 9)).pack(side="left")
        preset_name_entry = tk.Entry(save_preset_f, textvariable=preset_name_var,
                                     bg=CHAT_INPUT_BG, fg=CHAT_INPUT_FG,
                                     font=("Consolas", 9), insertbackground=ACCENT_BRIGHT,
                                     relief="flat", width=14)
        preset_name_entry.pack(side="left", padx=4, ipady=2)
        def _save_preset():
            name = preset_name_var.get().strip()
            if not name:
                return
            saved_presets[name] = _gather_current_face_config()
            preset_name_var.set("")
            _rebuild_preset_list()
        save_preset_btn = tk.Label(save_preset_f, text=" Save Preset ",
                                   bg=CHAT_INPUT_BG, fg=ACCENT_DIM,
                                   font=("Consolas", 8), cursor="hand2", padx=4, pady=2)
        save_preset_btn.pack(side="left", padx=4)
        save_preset_btn.bind("<Button-1>", lambda e: _save_preset())
        save_preset_btn.bind("<Enter>", lambda e: save_preset_btn.configure(fg=ACCENT_BRIGHT))
        save_preset_btn.bind("<Leave>", lambda e: save_preset_btn.configure(fg=ACCENT_DIM))

        # --- Section: Face Packs ---
        tk.Frame(inner, bg=ACCENT_DIM, height=1).pack(fill="x", padx=20, pady=(10, 6))
        tk.Label(inner, text="Face Packs", font=("Consolas", 10, "bold"),
                 bg=APPS_BG, fg=ACCENT_MID).pack(anchor="w", padx=20, pady=(2, 4))

        packs_frame = tk.Frame(inner, bg=APPS_BG)
        packs_frame.pack(fill="x", padx=20, pady=2)

        def _rebuild_packs_list():
            for w in packs_frame.winfo_children():
                w.destroy()
            try:
                from core.face_packs import pack_manager
                pack_manager.init()
                packs = pack_manager.list_packs()
                _ap = pack_manager.get_active_pack()
                active_id = _ap.id if _ap else None
                if not packs:
                    tk.Label(packs_frame, text="  No face packs found",
                             bg=APPS_BG, fg="#556677", font=("Consolas", 8)).pack(anchor="w")
                    return
                for pack in packs:
                    pid = pack.id
                    row = tk.Frame(packs_frame, bg=APPS_CARD_BG if pid == active_id else APPS_BG,
                                   highlightbackground=APPS_CARD_BORDER if pid == active_id else APPS_BG,
                                   highlightthickness=1 if pid == active_id else 0)
                    row.pack(fill="x", pady=2, ipady=3)
                    # Active indicator
                    status = " ✓ " if pid == active_id else "   "
                    tk.Label(row, text=status, bg=row["bg"], fg="#44ff88" if pid == active_id else APPS_BG,
                             font=("Consolas", 9)).pack(side="left")
                    # Name + info
                    info_f = tk.Frame(row, bg=row["bg"])
                    info_f.pack(side="left", fill="x", expand=True)
                    name_text = pack.name
                    price_text = "Free" if pack.is_free else f"${pack.price / 100:.2f}"
                    tk.Label(info_f, text=name_text, bg=row["bg"], fg=ACCENT_MID,
                             font=("Consolas", 9, "bold"), anchor="w").pack(anchor="w")
                    tk.Label(info_f, text=f"v{pack.version} • {price_text}",
                             bg=row["bg"], fg="#556677", font=("Consolas", 7), anchor="w").pack(anchor="w")
                    # Activate button
                    if pid != active_id:
                        act_btn = tk.Label(row, text=" Use ", bg=CHAT_INPUT_BG, fg=ACCENT_DIM,
                                           font=("Consolas", 8), cursor="hand2", padx=4, pady=1)
                        act_btn.pack(side="right", padx=4)
                        def _activate(p=pid):
                            pack_manager.activate_pack(p)
                            if hasattr(self, 'face'):
                                merged = pack_manager.get_merged_spec()
                                # Re-apply themes/styles from merged spec
                                new_themes = merged.get("themes", {})
                                if new_themes:
                                    from face import face_gui
                                    face_gui._THEMES.update(new_themes)
                            _rebuild_packs_list()
                        act_btn.bind("<Button-1>", lambda e, p=pid: _activate(p))
                        act_btn.bind("<Enter>", lambda e, b=act_btn: b.configure(fg=ACCENT_BRIGHT))
                        act_btn.bind("<Leave>", lambda e, b=act_btn: b.configure(fg=ACCENT_DIM))
            except Exception as ex:
                tk.Label(packs_frame, text=f"  Face packs unavailable: {ex}",
                         bg=APPS_BG, fg="#ff6666", font=("Consolas", 7),
                         wraplength=340).pack(anchor="w")

        _rebuild_packs_list()

        # --- Section: Body ---
        tk.Frame(inner, bg=ACCENT_DIM, height=1).pack(fill="x", padx=20, pady=(10, 6))
        tk.Label(inner, text="Body", font=("Consolas", 10, "bold"),
                 bg=APPS_BG, fg=ACCENT_MID).pack(anchor="w", padx=20, pady=(2, 4))

        # Body Visible toggle
        body_vis_var = tk.BooleanVar(value=settings.get("body_visible", True))
        def _on_body_vis(*args):
            if hasattr(self, '_body'):
                self._body.set_visible(body_vis_var.get())
        body_vis_var.trace_add("write", _on_body_vis)
        tk.Checkbutton(inner, text="Show Body", variable=body_vis_var, bg=APPS_BG, fg=ACCENT_MID,
                       selectcolor=CHAT_INPUT_BG, activebackground=APPS_BG,
                       activeforeground=ACCENT_BRIGHT, font=("Consolas", 9)
                       ).pack(anchor="w", padx=24, pady=1)
        checks["body_visible"] = body_vis_var

        # Body Position X slider
        def _make_slider(parent, label, from_, to_, resolution, initial, on_change):
            f = tk.Frame(parent, bg=APPS_BG)
            f.pack(fill="x", padx=20, pady=2)
            tk.Label(f, text=label, bg=APPS_BG, fg=ACCENT_DIM,
                     font=("Consolas", 9), width=16, anchor="w").pack(side="left")
            val_label = tk.Label(f, text=str(initial), bg=APPS_BG, fg=ACCENT_BRIGHT,
                                 font=("Consolas", 9), width=6, anchor="e")
            val_label.pack(side="right")
            scale = tk.Scale(f, from_=from_, to=to_, orient="horizontal",
                             resolution=resolution, bg=APPS_BG, fg=ACCENT_MID,
                             troughcolor=CHAT_INPUT_BG, highlightthickness=0,
                             sliderrelief="flat", font=("Consolas", 7),
                             showvalue=False, length=140,
                             activebackground=ACCENT_BRIGHT)
            scale.set(initial)
            def _changed(v):
                val_label.configure(text=str(round(float(v), 2)))
                on_change(float(v))
            scale.configure(command=_changed)
            scale.pack(side="left", fill="x", expand=True, padx=(4, 4))
            return scale

        def _on_offset_x(v):
            if hasattr(self, '_body'):
                self._body.set_offset(int(v), self._body._offset_y)
        body_ox_scale = _make_slider(inner, "Position X:", -200, 200, 5,
                                      settings.get("body_offset_x", 0), _on_offset_x)

        def _on_offset_y(v):
            if hasattr(self, '_body'):
                self._body.set_offset(self._body._offset_x, int(v))
        body_oy_scale = _make_slider(inner, "Position Y:", -200, 200, 5,
                                      settings.get("body_offset_y", 0), _on_offset_y)

        def _on_body_scale(v):
            if hasattr(self, '_body'):
                self._body.set_scale(float(v))
        body_scale_slider = _make_slider(inner, "Body Scale:", 0.3, 2.0, 0.05,
                                          settings.get("body_scale", 1.0), _on_body_scale)

        # Reset body position button
        def _reset_body():
            body_ox_scale.set(0)
            body_oy_scale.set(0)
            body_scale_slider.set(1.0)
            if hasattr(self, '_body'):
                self._body.set_offset(0, 0)
                self._body.set_scale(1.0)
        reset_f = tk.Frame(inner, bg=APPS_BG)
        reset_f.pack(fill="x", padx=20, pady=2)
        reset_btn = tk.Label(reset_f, text=" Reset Position ", bg=CHAT_INPUT_BG, fg=ACCENT_DIM,
                             font=("Consolas", 8), cursor="hand2", padx=6, pady=2)
        reset_btn.pack(side="right")
        reset_btn.bind("<Button-1>", lambda e: _reset_body())
        reset_btn.bind("<Enter>", lambda e: reset_btn.configure(fg=ACCENT_BRIGHT))
        reset_btn.bind("<Leave>", lambda e: reset_btn.configure(fg=ACCENT_DIM))

        # Character Switcher
        tk.Frame(inner, bg=ACCENT_DIM, height=1).pack(fill="x", padx=20, pady=(10, 6))
        tk.Label(inner, text="Character", font=("Consolas", 10, "bold"),
                 bg=APPS_BG, fg=ACCENT_MID).pack(anchor="w", padx=20, pady=(2, 4))

        try:
            from face.stage.character_library import CHARACTER_TEMPLATES, THEME_COLORS
            char_options = {
                k: {"label": f"{t.display_name} — {t.description}"}
                for k, t in CHARACTER_TEMPLATES.items()
            }
            current_char = settings.get("active_character", "onyx")

            # Character dropdown
            char_f = tk.Frame(inner, bg=APPS_BG)
            char_f.pack(fill="x", padx=20, pady=3)
            tk.Label(char_f, text="Active:", bg=APPS_BG, fg=ACCENT_DIM,
                     font=("Consolas", 9), width=16, anchor="w").pack(side="left")

            char_labels = []
            char_label_to_key = {}
            char_key_to_label = {}
            for k, t in CHARACTER_TEMPLATES.items():
                lbl = t.display_name
                char_labels.append(lbl)
                char_label_to_key[lbl] = k
                char_key_to_label[k] = lbl

            char_var = tk.StringVar(value=char_key_to_label.get(current_char, "Onyx"))
            char_om = tk.OptionMenu(char_f, char_var, *char_labels)
            char_om.configure(bg=CHAT_INPUT_BG, fg=CHAT_INPUT_FG, font=("Consolas", 9),
                              highlightthickness=0, relief="flat", activebackground=APPS_BG,
                              activeforeground=ACCENT_BRIGHT)
            char_om["menu"].configure(bg=CHAT_INPUT_BG, fg=CHAT_INPUT_FG, font=("Consolas", 9),
                                      activebackground=ACCENT_DIM, activeforeground=ACCENT_BRIGHT)
            char_om.pack(side="left", fill="x", expand=True)

            # Character preview card
            char_preview = tk.Frame(inner, bg=APPS_CARD_BG, highlightbackground=APPS_CARD_BORDER,
                                     highlightthickness=1)
            char_preview.pack(fill="x", padx=20, pady=4)

            def _update_char_preview(*args):
                selected = char_label_to_key.get(char_var.get(), "onyx")
                tmpl = CHARACTER_TEMPLATES.get(selected)
                if not tmpl:
                    return
                for w in char_preview.winfo_children():
                    w.destroy()
                colors = THEME_COLORS.get(tmpl.theme, THEME_COLORS["cyan"])
                color_bar = tk.Frame(char_preview, bg=colors["primary"], height=4)
                color_bar.pack(fill="x")
                tk.Label(char_preview, text=f"  {tmpl.description}",
                         bg=APPS_CARD_BG, fg=ACCENT_MID, font=("Consolas", 8),
                         anchor="w", wraplength=340).pack(fill="x", padx=8, pady=(4, 2))
                info_items = [
                    f"Theme: {tmpl.theme}",
                    f"Eyes: {tmpl.eye_style}",
                    f"Body: {tmpl.body_style}",
                    f"Pose: {tmpl.default_pose}",
                ]
                tk.Label(char_preview, text="  " + " • ".join(info_items),
                         bg=APPS_CARD_BG, fg="#6a7a8a", font=("Consolas", 7),
                         anchor="w").pack(fill="x", padx=8, pady=(0, 4))

            char_var.trace_add("write", _update_char_preview)
            _update_char_preview()

            # Live-apply character switch
            def _on_char_change(*args):
                selected = char_label_to_key.get(char_var.get(), "onyx")
                tmpl = CHARACTER_TEMPLATES.get(selected)
                if not tmpl:
                    return
                # Update face theme/eyes/shape/accessory
                if hasattr(self, 'face'):
                    self.face.apply_customization(
                        theme=tmpl.theme, eye_style=tmpl.eye_style,
                        face_shape=tmpl.face_shape, accessory=tmpl.accessory,
                    )
                # Update body style and colors
                if hasattr(self, '_body') and self._body._body:
                    colors = THEME_COLORS.get(tmpl.theme, THEME_COLORS["cyan"])
                    self._body._body.colors = colors.copy()
                    self._body.set_body_style(tmpl.body_style)

            char_var.trace_add("write", _on_char_change)

            dropdowns["active_character"] = (char_var, char_label_to_key)

        except Exception as e:
            tk.Label(inner, text=f"  Character library unavailable: {e}",
                     bg=APPS_BG, fg="#ff6666", font=("Consolas", 7),
                     wraplength=360).pack(anchor="w", padx=24, pady=2)

        # --- Save/Cancel ---
        tk.Frame(inner, bg=ACCENT_DIM, height=1).pack(fill="x", padx=20, pady=(10, 6))
        btn_f = tk.Frame(inner, bg=APPS_BG)
        btn_f.pack(pady=10)

        def _save():
            for key, var in fields.items():
                settings[key] = var.get()
            for key, var in checks.items():
                settings[key] = var.get()
            # Save dropdown values (convert labels back to keys)
            for key, (var, label_to_key) in dropdowns.items():
                selected_label = var.get()
                settings[key] = label_to_key.get(selected_label, settings.get(key, ""))

            # Save geometry slider values
            try:
                settings["geometry"] = {k: round(s.get(), 1) for k, s in geo_sliders.items()}
            except Exception:
                pass

            # Save animation slider values
            try:
                settings["animation"] = {k: round(s.get(), 2) for k, (s, _) in anim_sliders.items()}
            except Exception:
                pass

            # Save face presets
            settings["face_presets"] = saved_presets

            # Save body slider values
            try:
                settings["body_offset_x"] = int(body_ox_scale.get())
                settings["body_offset_y"] = int(body_oy_scale.get())
                settings["body_scale"] = round(float(body_scale_slider.get()), 2)
            except Exception:
                pass
            
            # Switch personality preset if changed
            if "personality_preset" in settings:
                try:
                    from core.personality_manager import get_personality_manager
                    manager = get_personality_manager()
                    manager.switch_preset(settings["personality_preset"])
                    self._append_chat(f"Personality switched to: {settings['personality_preset']}", "system")
                except Exception as e:
                    self._append_chat(f"Failed to switch personality: {e}", "system")
            
            onyx_settings.save_settings(settings)
            # Update backend with new name
            user_name = settings.get("user_name", "")
            if user_name:
                self.backend.user_name = user_name
            dialog.destroy()
            self._append_chat("Settings saved.", "system")

        save_btn = tk.Label(btn_f, text=" Save ", bg=BTN_BG, fg=BTN_FG,
                            font=("Consolas", 10, "bold"), padx=14, pady=5, cursor="hand2")
        save_btn.pack(side="left", padx=8)
        save_btn.bind("<Button-1>", lambda e: _save())
        save_btn.bind("<Enter>", lambda e: save_btn.configure(bg=BTN_ACTIVE_BG))
        save_btn.bind("<Leave>", lambda e: save_btn.configure(bg=BTN_BG))

        cancel_btn = tk.Label(btn_f, text=" Cancel ", bg=APPS_BG, fg=SYSTEM_MSG_COLOR,
                              font=("Consolas", 10), padx=10, pady=5, cursor="hand2")
        cancel_btn.pack(side="left", padx=8)
        cancel_btn.bind("<Button-1>", lambda e: dialog.destroy())

    # ------------------------------------------------------------------
    # Chat panel
    # ------------------------------------------------------------------

    def _build_chat_panel(self):
        self._chat_frame = tk.Frame(self.root, bg=CHAT_BG, width=CHAT_WIDTH)
        # Not packed yet — shown/hidden by _toggle_chat

        # Header
        header = tk.Frame(self._chat_frame, bg=CHAT_BG, height=24)
        header.pack(fill="x", padx=6, pady=(6, 2))
        self._chat_header_label = tk.Label(header, text="CHAT", bg=CHAT_BG, fg=ACCENT_DIM,
                 font=("Consolas", 8, "bold"))
        self._chat_header_label.pack(side="left")

        # Separator
        tk.Frame(self._chat_frame, bg=CHAT_BORDER, height=1).pack(fill="x", padx=6)

        # --- Pack bottom controls FIRST so they're always visible ---

        # Input area (pack at bottom first)
        input_frame = tk.Frame(self._chat_frame, bg=CHAT_BG)
        input_frame.pack(side="bottom", fill="x", padx=6, pady=6)

        # Separator above input
        tk.Frame(self._chat_frame, bg=CHAT_BORDER, height=1).pack(side="bottom", fill="x", padx=6)

        # Typing indicator (above separator)
        self._typing_frame = tk.Frame(self._chat_frame, bg=CHAT_BG, height=18)
        self._typing_frame.pack(side="bottom", fill="x", padx=10)
        self._typing_frame.pack_propagate(False)
        self._typing_label = tk.Label(self._typing_frame, text="",
                                      bg=CHAT_BG, fg=ACCENT_DIM,
                                      font=("Consolas", 8), anchor="w")
        self._typing_label.pack(side="left")
        self._typing_visible = False
        self._typing_dots = 0

        # --- Now pack chat history to fill remaining space ---

        # Chat history (scrollable)
        history_frame = tk.Frame(self._chat_frame, bg=CHAT_BG)
        history_frame.pack(fill="both", expand=True, padx=0, pady=4)

        self._chat_scrollbar = tk.Scrollbar(history_frame, orient="vertical",
                                            bg=CHAT_BG, troughcolor=CHAT_BG,
                                            highlightthickness=0, borderwidth=0)
        self._chat_scrollbar.pack(side="right", fill="y")

        self._chat_history = tk.Text(
            history_frame, bg=CHAT_BG, fg=BOT_MSG_COLOR,
            font=("Consolas", 9), wrap="word",
            state="disabled", relief="flat", borderwidth=0,
            highlightthickness=0, padx=6, pady=4,
            insertbackground=ACCENT_BRIGHT,
            selectbackground=ACCENT_DIM,
            yscrollcommand=self._chat_scrollbar.set,
            spacing1=0, spacing3=0,
        )
        self._chat_history.pack(fill="both", expand=True)
        self._chat_scrollbar.config(command=self._chat_history.yview)

        # Configure bubble-style text tags
        self._chat_history.tag_configure("user_label",
            foreground=USER_MSG_COLOR, font=("Consolas", 8, "bold"),
            spacing1=10, spacing3=1)
        self._chat_history.tag_configure("user_msg",
            foreground="#d0eeff", background=USER_BUBBLE_BG,
            font=("Consolas", 9), lmargin1=8, lmargin2=8, rmargin=8,
            spacing1=2, spacing3=2, relief="flat")
        self._chat_history.tag_configure("bot_label",
            foreground=BOT_MSG_COLOR, font=("Consolas", 8, "bold"),
            spacing1=10, spacing3=1)
        self._chat_history.tag_configure("bot_msg",
            foreground="#99aabb", background=BOT_BUBBLE_BG,
            font=("Consolas", 9), lmargin1=8, lmargin2=8, rmargin=8,
            spacing1=2, spacing3=2, relief="flat")
        self._chat_history.tag_configure("system",
            foreground=SYSTEM_MSG_COLOR, font=("Consolas", 8, "italic"),
            justify="center", spacing1=6, spacing3=2)
        self._chat_history.tag_configure("error",
            foreground="#ff6666", background="#1a0a0a",
            font=("Consolas", 9), lmargin1=8, lmargin2=8, rmargin=8,
            spacing1=4, spacing3=2)
        self._chat_history.tag_configure("success",
            foreground="#66ff88", background="#0a1a0a",
            font=("Consolas", 9), lmargin1=8, lmargin2=8, rmargin=8,
            spacing1=4, spacing3=2)
        self._chat_history.tag_configure("timestamp",
            foreground=TIMESTAMP_COLOR, font=("Consolas", 7),
            spacing1=1, spacing3=4)

        # Text input row
        input_row = tk.Frame(input_frame, bg=CHAT_BG)
        input_row.pack(fill="x")

        self._input_var = tk.StringVar()
        self._input_entry = tk.Entry(
            input_row, textvariable=self._input_var,
            bg=CHAT_INPUT_BG, fg=CHAT_INPUT_FG,
            font=("Consolas", 10), relief="flat", borderwidth=0,
            insertbackground=ACCENT_BRIGHT,
            highlightthickness=1, highlightcolor=ACCENT_DIM,
            highlightbackground=CHAT_BORDER,
        )
        self._input_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self._input_entry.bind("<Return>", lambda e: self._send_message())

        # Send button
        send_btn = tk.Label(
            input_row, text=" ➤ ", bg=BTN_BG, fg=BTN_FG,
            font=("Consolas", 12), cursor="hand2",
            relief="flat", borderwidth=0,
        )
        send_btn.pack(side="right", padx=(4, 0))
        send_btn.bind("<Button-1>", lambda e: self._send_message())
        send_btn.bind("<Enter>", lambda e: send_btn.configure(bg=BTN_ACTIVE_BG))
        send_btn.bind("<Leave>", lambda e: send_btn.configure(bg=BTN_BG))

        # Voice buttons row
        voice_row = tk.Frame(input_frame, bg=CHAT_BG)
        voice_row.pack(fill="x", pady=(4, 0))

        # Mic button
        self._mic_btn = tk.Label(
            voice_row, text=" 🎤 Mic ", bg=BTN_BG, fg=BTN_FG,
            font=("Consolas", 9), cursor="hand2", relief="flat",
        )
        self._mic_btn.pack(side="left", padx=(0, 4))
        self._mic_btn.bind("<Button-1>", lambda e: self._on_mic_click())
        self._mic_btn.bind("<Enter>", lambda e: self._mic_btn.configure(bg=BTN_ACTIVE_BG))
        self._mic_btn.bind("<Leave>", lambda e: self._mic_btn.configure(
            bg=BTN_BG if not getattr(self, '_recording', False) else BTN_RECORDING))

        # Hands-free toggle
        self._hf_btn = tk.Label(
            voice_row, text=" ⚡ Hands-free ", bg=BTN_BG, fg=ACCENT_DIM,
            font=("Consolas", 9), cursor="hand2", relief="flat",
        )
        self._hf_btn.pack(side="left", padx=(0, 4))
        self._hf_btn.bind("<Button-1>", lambda e: self._on_handsfree_click())
        self._hf_btn.bind("<Enter>", lambda e: self._hf_btn.configure(bg=BTN_ACTIVE_BG))
        self._hf_btn.bind("<Leave>", lambda e: self._hf_btn.configure(
            bg=BTN_BG if not self.backend.hands_free else "#0a2020"))

        # TTS toggle
        self._tts_enabled = True
        self._tts_btn = tk.Label(
            voice_row, text=" 🔊 TTS ", bg=BTN_BG, fg=ACCENT_MID,
            font=("Consolas", 9), cursor="hand2", relief="flat",
        )
        self._tts_btn.pack(side="right")
        self._tts_btn.bind("<Button-1>", lambda e: self._toggle_tts())

    # ------------------------------------------------------------------
    # Chat toggle (docked vs floating based on body visibility)
    # ------------------------------------------------------------------

    def _toggle_chat(self):
        if self._chat_visible:
            # --- Close chat ---
            if self._chat_float_win:
                self._close_floating_chat()
            else:
                self._chat_frame.pack_forget()
                self._chat_visible = False
                w = self.root.winfo_width() - CHAT_WIDTH
                h = self.root.winfo_height()
                self.root.geometry(f"{max(w, MIN_W)}x{h}")
            self._toggle_btn.configure(fg=ACCENT_DIM)
        else:
            # --- Open chat ---
            body_visible = hasattr(self, '_body') and self._body.is_visible
            if body_visible:
                self._build_floating_chat()
            else:
                self._chat_frame.pack(fill="both", expand=False, side="right")
                self._chat_frame.configure(width=CHAT_WIDTH)
                self._chat_visible = True
                w = self.root.winfo_width() + CHAT_WIDTH
                h = self.root.winfo_height()
                self.root.geometry(f"{w}x{max(h, MIN_H)}")
                self._input_entry.focus_set()
            self._toggle_btn.configure(fg=ACCENT_MID)

    # ------------------------------------------------------------------
    # Floating chat window (used when body is visible)
    # ------------------------------------------------------------------

    def _build_floating_chat(self):
        """Create a floating Toplevel chat window with fresh widgets."""
        if self._chat_float_win is not None:
            # Already open — bring to front
            self._chat_float_win.lift()
            self._input_entry.focus_set()
            return

        # Position next to the face window
        self.root.update_idletasks()
        rx = self.root.winfo_rootx()
        ry = self.root.winfo_rooty()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()

        win = tk.Toplevel(self.root)
        win.title("Onyx Chat")
        win.configure(bg=CHAT_BG)
        win.geometry(f"{CHAT_WIDTH + 40}x{rh}+{rx + rw + 8}+{ry}")
        win.minsize(280, 300)
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", self._close_floating_chat)
        self._chat_float_win = win

        # Build chat widgets inside the floating window
        container = tk.Frame(win, bg=CHAT_BG)
        container.pack(fill="both", expand=True)

        # Header
        header = tk.Frame(container, bg=CHAT_BG, height=24)
        header.pack(fill="x", padx=6, pady=(6, 2))
        self._chat_header_label = tk.Label(header, text="CHAT", bg=CHAT_BG, fg=ACCENT_DIM,
                                           font=("Consolas", 8, "bold"))
        self._chat_header_label.pack(side="left")

        tk.Frame(container, bg=CHAT_BORDER, height=1).pack(fill="x", padx=6)

        # Bottom controls first (so they're always visible)
        input_frame = tk.Frame(container, bg=CHAT_BG)
        input_frame.pack(side="bottom", fill="x", padx=6, pady=6)

        tk.Frame(container, bg=CHAT_BORDER, height=1).pack(side="bottom", fill="x", padx=6)

        # Typing indicator
        self._typing_frame = tk.Frame(container, bg=CHAT_BG, height=18)
        self._typing_frame.pack(side="bottom", fill="x", padx=10)
        self._typing_frame.pack_propagate(False)
        self._typing_label = tk.Label(self._typing_frame, text="",
                                      bg=CHAT_BG, fg=ACCENT_DIM,
                                      font=("Consolas", 8), anchor="w")
        self._typing_label.pack(side="left")

        # Chat history (scrollable, fills remaining space)
        history_frame = tk.Frame(container, bg=CHAT_BG)
        history_frame.pack(fill="both", expand=True, padx=0, pady=4)

        chat_sb = tk.Scrollbar(history_frame, orient="vertical",
                               bg=CHAT_BG, troughcolor=CHAT_BG,
                               highlightthickness=0, borderwidth=0)
        chat_sb.pack(side="right", fill="y")

        self._chat_history = tk.Text(
            history_frame, bg=CHAT_BG, fg=BOT_MSG_COLOR,
            font=("Consolas", 9), wrap="word",
            state="disabled", relief="flat", borderwidth=0,
            highlightthickness=0, padx=6, pady=4,
            insertbackground=ACCENT_BRIGHT,
            selectbackground=ACCENT_DIM,
            yscrollcommand=chat_sb.set,
            spacing1=0, spacing3=0,
        )
        self._chat_history.pack(fill="both", expand=True)
        chat_sb.config(command=self._chat_history.yview)

        # Configure text tags (same as docked)
        self._chat_history.tag_configure("user_label",
            foreground=USER_MSG_COLOR, font=("Consolas", 8, "bold"),
            spacing1=10, spacing3=1)
        self._chat_history.tag_configure("user_msg",
            foreground="#d0eeff", background=USER_BUBBLE_BG,
            font=("Consolas", 9), lmargin1=8, lmargin2=8, rmargin=8,
            spacing1=2, spacing3=2, relief="flat")
        self._chat_history.tag_configure("bot_label",
            foreground=BOT_MSG_COLOR, font=("Consolas", 8, "bold"),
            spacing1=10, spacing3=1)
        self._chat_history.tag_configure("bot_msg",
            foreground="#99aabb", background=BOT_BUBBLE_BG,
            font=("Consolas", 9), lmargin1=8, lmargin2=8, rmargin=8,
            spacing1=2, spacing3=2, relief="flat")
        self._chat_history.tag_configure("system",
            foreground=SYSTEM_MSG_COLOR, font=("Consolas", 8, "italic"),
            justify="center", spacing1=6, spacing3=2)
        self._chat_history.tag_configure("error",
            foreground="#ff6666", background="#1a0a0a",
            font=("Consolas", 9), lmargin1=8, lmargin2=8, rmargin=8,
            spacing1=4, spacing3=2)
        self._chat_history.tag_configure("success",
            foreground="#66ff88", background="#0a1a0a",
            font=("Consolas", 9), lmargin1=8, lmargin2=8, rmargin=8,
            spacing1=4, spacing3=2)
        self._chat_history.tag_configure("timestamp",
            foreground=TIMESTAMP_COLOR, font=("Consolas", 7),
            spacing1=1, spacing3=4)

        # Input row
        input_row = tk.Frame(input_frame, bg=CHAT_BG)
        input_row.pack(fill="x")

        self._input_var = tk.StringVar()
        self._input_entry = tk.Entry(
            input_row, textvariable=self._input_var,
            bg=CHAT_INPUT_BG, fg=CHAT_INPUT_FG,
            font=("Consolas", 10), relief="flat", borderwidth=0,
            insertbackground=ACCENT_BRIGHT,
            highlightthickness=1, highlightcolor=ACCENT_DIM,
            highlightbackground=CHAT_BORDER,
        )
        self._input_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self._input_entry.bind("<Return>", lambda e: self._send_message())

        send_btn = tk.Label(
            input_row, text=" ➤ ", bg=BTN_BG, fg=BTN_FG,
            font=("Consolas", 12), cursor="hand2",
            relief="flat", borderwidth=0,
        )
        send_btn.pack(side="right", padx=(4, 0))
        send_btn.bind("<Button-1>", lambda e: self._send_message())
        send_btn.bind("<Enter>", lambda e: send_btn.configure(bg=BTN_ACTIVE_BG))
        send_btn.bind("<Leave>", lambda e: send_btn.configure(bg=BTN_BG))

        # Voice buttons
        voice_row = tk.Frame(input_frame, bg=CHAT_BG)
        voice_row.pack(fill="x", pady=(4, 0))

        self._mic_btn = tk.Label(
            voice_row, text=" 🎤 Mic ", bg=BTN_BG, fg=BTN_FG,
            font=("Consolas", 9), cursor="hand2", relief="flat",
        )
        self._mic_btn.pack(side="left", padx=(0, 4))
        self._mic_btn.bind("<Button-1>", lambda e: self._on_mic_click())
        self._mic_btn.bind("<Enter>", lambda e: self._mic_btn.configure(bg=BTN_ACTIVE_BG))
        self._mic_btn.bind("<Leave>", lambda e: self._mic_btn.configure(
            bg=BTN_BG if not getattr(self, '_recording', False) else BTN_RECORDING))

        self._hf_btn = tk.Label(
            voice_row, text=" ⚡ Hands-free ", bg=BTN_BG, fg=ACCENT_DIM,
            font=("Consolas", 9), cursor="hand2", relief="flat",
        )
        self._hf_btn.pack(side="left", padx=(0, 4))
        self._hf_btn.bind("<Button-1>", lambda e: self._on_handsfree_click())
        self._hf_btn.bind("<Enter>", lambda e: self._hf_btn.configure(bg=BTN_ACTIVE_BG))
        self._hf_btn.bind("<Leave>", lambda e: self._hf_btn.configure(
            bg=BTN_BG if not self.backend.hands_free else "#0a2020"))

        self._tts_btn = tk.Label(
            voice_row, text=" 🔊 TTS ", bg=BTN_BG, fg=ACCENT_MID,
            font=("Consolas", 9), cursor="hand2", relief="flat",
        )
        self._tts_btn.pack(side="right")
        self._tts_btn.bind("<Button-1>", lambda e: self._toggle_tts())

        # Load chat history into the floating window
        self._load_chat_history()

        self._chat_visible = True
        self._input_entry.focus_set()
        _log.info("Floating chat window opened")

    def _close_floating_chat(self):
        """Close the floating chat window, restore docked widget refs."""
        if self._chat_float_win is not None:
            try:
                self._chat_float_win.destroy()
            except tk.TclError:
                pass
            self._chat_float_win = None

        # Restore docked widget references
        self._chat_history = self._docked_chat_history
        self._input_entry = self._docked_input_entry
        self._input_var = self._docked_input_var
        self._chat_header_label = self._docked_chat_header
        self._typing_label = self._docked_typing_label
        self._typing_frame = self._docked_typing_frame
        self._mic_btn = self._docked_mic_btn
        self._hf_btn = self._docked_hf_btn
        self._tts_btn = self._docked_tts_btn

        self._chat_visible = False
        _log.info("Floating chat window closed, docked refs restored")

    # ------------------------------------------------------------------
    # Companion mode (Duo) — Onyx + Xyno dual conversation
    # ------------------------------------------------------------------

    _companion_session = None
    _companion_xyno = None

    def _toggle_companion(self):
        """Toggle companion mode — launch stage-based multi-character conversation with character selection."""
        # Check if a conversation is already running
        if hasattr(self, '_conversation_running') and self._conversation_running:
            self._append_chat("A conversation is already in progress.", "system")
            return
        
        # Show character selection dialog
        self._show_character_selection_dialog()
    
    def _show_character_selection_dialog(self):
        """Show a dialog to select characters for the conversation."""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Characters for Conversation")
        dialog.configure(bg=FACE_COLOR)
        dialog.geometry("500x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (600 // 2)
        dialog.geometry(f"500x600+{x}+{y}")
        
        # Title
        title_label = tk.Label(
            dialog,
            text="Select Characters (2-5)",
            font=("Segoe UI", 16, "bold"),
            fg=ACCENT_BRIGHT,
            bg=FACE_COLOR
        )
        title_label.pack(pady=20)
        
        # Character selection frame
        char_frame = tk.Frame(dialog, bg=FACE_COLOR)
        char_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Available characters
        characters = [
            ("onyx", "Onyx", "#00d4ff", "Confident and witty AI agent"),
            ("xyno", "Xyno", "#ff69b4", "Warm and clever AI companion"),
            ("volt", "Volt", "#ffaa00", "Analytical and precise AI"),
            ("sage", "Sage", "#88ff88", "Wise and contemplative AI"),
            ("echo", "Echo", "#aa88ff", "Creative and energetic AI"),
        ]
        
        # Checkboxes for each character
        selected_chars = {}
        
        for char_id, char_name, char_color, char_desc in characters:
            char_container = tk.Frame(char_frame, bg=FACE_COLOR)
            char_container.pack(fill="x", pady=8)
            
            # Checkbox variable
            var = tk.BooleanVar(value=(char_id in ["onyx", "xyno"]))  # Default: Onyx + Xyno
            selected_chars[char_id] = var
            
            # Checkbox
            cb = tk.Checkbutton(
                char_container,
                text="",
                variable=var,
                bg=FACE_COLOR,
                fg=char_color,
                selectcolor=FACE_COLOR,
                activebackground=FACE_COLOR,
                activeforeground=char_color,
                font=("Segoe UI", 12),
            )
            cb.pack(side="left", padx=5)
            
            # Character info
            info_frame = tk.Frame(char_container, bg=FACE_COLOR)
            info_frame.pack(side="left", fill="x", expand=True)
            
            name_label = tk.Label(
                info_frame,
                text=char_name,
                font=("Segoe UI", 12, "bold"),
                fg=char_color,
                bg=FACE_COLOR,
                anchor="w"
            )
            name_label.pack(fill="x")
            
            desc_label = tk.Label(
                info_frame,
                text=char_desc,
                font=("Segoe UI", 9),
                fg=ACCENT_DIM,
                bg=FACE_COLOR,
                anchor="w"
            )
            desc_label.pack(fill="x")
        
        # Options frame
        options_frame = tk.Frame(dialog, bg=FACE_COLOR)
        options_frame.pack(fill="x", padx=20, pady=10)
        
        # Turn count
        turn_frame = tk.Frame(options_frame, bg=FACE_COLOR)
        turn_frame.pack(fill="x", pady=5)
        
        tk.Label(
            turn_frame,
            text="Conversation Turns:",
            font=("Segoe UI", 10),
            fg=ACCENT_MID,
            bg=FACE_COLOR
        ).pack(side="left")
        
        turn_var = tk.StringVar(value="15")
        turn_entry = tk.Entry(
            turn_frame,
            textvariable=turn_var,
            width=5,
            font=("Segoe UI", 10),
            bg="#0a1220",
            fg=ACCENT_BRIGHT,
            insertbackground=ACCENT_BRIGHT,
            relief="flat"
        )
        turn_entry.pack(side="left", padx=10)
        
        # Self-improve mode
        improve_var = tk.BooleanVar(value=False)
        improve_cb = tk.Checkbutton(
            options_frame,
            text="Self-Improvement Mode (discuss how to improve Onyx)",
            variable=improve_var,
            bg=FACE_COLOR,
            fg=ACCENT_MID,
            selectcolor=FACE_COLOR,
            activebackground=FACE_COLOR,
            activeforeground=ACCENT_BRIGHT,
            font=("Segoe UI", 9),
        )
        improve_cb.pack(fill="x", pady=5)
        
        # Error label
        error_label = tk.Label(
            dialog,
            text="",
            font=("Segoe UI", 9),
            fg="#ff4444",
            bg=FACE_COLOR
        )
        error_label.pack(pady=5)
        
        # Buttons frame
        button_frame = tk.Frame(dialog, bg=FACE_COLOR)
        button_frame.pack(pady=20)
        
        def _start_conversation():
            # Get selected characters
            selected = [char_id for char_id, var in selected_chars.items() if var.get()]
            
            # Validate selection
            if len(selected) < 2:
                error_label.configure(text="Please select at least 2 characters")
                return
            if len(selected) > 5:
                error_label.configure(text="Maximum 5 characters allowed")
                return
            
            # Get turn count
            try:
                turns = int(turn_var.get())
                if turns < 5 or turns > 50:
                    error_label.configure(text="Turns must be between 5 and 50")
                    return
            except ValueError:
                error_label.configure(text="Invalid turn count")
                return
            
            # Close dialog
            dialog.destroy()
            
            # Start conversation with selected characters
            self._start_conversation_with_characters(
                character_ids=selected,
                max_turns=turns,
                self_improve=improve_var.get()
            )
        
        def _cancel():
            dialog.destroy()
        
        # Start button
        start_btn = tk.Button(
            button_frame,
            text="Start Conversation",
            command=_start_conversation,
            font=("Segoe UI", 11, "bold"),
            bg=ACCENT_BRIGHT,
            fg="#000000",
            activebackground=ACCENT_MID,
            activeforeground="#000000",
            relief="flat",
            padx=20,
            pady=10,
            cursor="hand2"
        )
        start_btn.pack(side="left", padx=10)
        
        # Cancel button
        cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=_cancel,
            font=("Segoe UI", 11),
            bg="#0a1220",
            fg=ACCENT_DIM,
            activebackground="#0c1420",
            activeforeground=ACCENT_MID,
            relief="flat",
            padx=20,
            pady=10,
            cursor="hand2"
        )
        cancel_btn.pack(side="left", padx=10)
    
    def _start_conversation_with_characters(self, character_ids, max_turns, self_improve):
        """Start a conversation with the selected characters."""
        self._companion_btn.configure(fg="#ff69b4")
        
        char_names = ", ".join([cid.capitalize() for cid in character_ids])
        self._append_chat(f"Generating conversation with {char_names}...", "system")
        
        # Generate conversation in background thread, then run on main thread
        def _generate_conversation():
            try:
                self._conversation_running = True
                
                # Build conversation show
                from face.stage.shows.conversation_show import build_conversation_show, run_conversation_on_stage
                
                self.root.after(0, lambda: self._append_chat("Generating dialogue...", "system"))
                
                show_data = build_conversation_show(
                    character_ids=character_ids,
                    max_turns=max_turns,
                    topic=None,  # Random topic
                    self_improve=self_improve,
                )
                
                # Schedule stage execution on main thread (Tkinter requires this)
                def _run_on_main_thread():
                    try:
                        self._append_chat("Opening stage...", "system")
                        run_conversation_on_stage(self, show_data, record=False)
                    except Exception as e:
                        _log.error(f"Stage execution error: {e}", exc_info=True)
                        self._append_chat(f"Stage error: {e}", "error")
                    finally:
                        self._conversation_running = False
                        self._companion_btn.configure(fg=ACCENT_DIM)
                        self._append_chat("Conversation ended.", "system")
                
                self.root.after(0, _run_on_main_thread)
                
            except Exception as e:
                _log.error(f"Conversation generation error: {e}", exc_info=True)
                self.root.after(0, lambda: self._append_chat(f"Generation error: {e}", "error"))
                self.root.after(0, lambda: self._companion_btn.configure(fg=ACCENT_DIM))
                self._conversation_running = False
        
        import threading
        threading.Thread(target=_generate_conversation, daemon=True, name="DuoConversation").start()

    # ------------------------------------------------------------------
    # Mode toggle
    # ------------------------------------------------------------------

    def _toggle_mode(self):
        """Toggle between companion and work mode via UI."""
        new_mode = "work" if self.backend.mode == "companion" else "companion"
        self.backend.set_mode(new_mode)
        self._update_mode_ui(new_mode)

    def _update_mode_ui(self, mode: str):
        """Update the mode indicator label and chat header to reflect the current mode."""
        if mode == "work":
            self._mode_label.configure(text=" ⚡ Work ", fg="#ffaa00")
            self._chat_header_label.configure(text="WORK MODE", fg="#ffaa00")
        else:
            self._mode_label.configure(text=" 💬 Chat ", fg=ACCENT_DIM)
            self._chat_header_label.configure(text="CHAT", fg=ACCENT_DIM)

    # ------------------------------------------------------------------
    # Chat messaging
    # ------------------------------------------------------------------

    def _append_chat(self, text: str, tag: str = "bot"):
        ts = datetime.now().strftime("%H:%M")
        # Persist to SQLite (fire-and-forget)
        role_map = {"user": "user", "bot": "assistant", "success": "assistant",
                     "error": "system", "system": "system"}
        self.backend.persist_message(role_map.get(tag, "system"), text)

        self._chat_history.configure(state="normal")
        if tag == "user":
            self._chat_history.insert("end", f"  You  {ts}\n", "user_label")
            self._chat_history.insert("end", f" {text} \n", "user_msg")
        elif tag in ("bot", "success"):
            label_tag = "bot_label"
            msg_tag = "success" if tag == "success" else "bot_msg"
            self._chat_history.insert("end", f"  Onyx  {ts}\n", label_tag)
            
            # Check if typewriter effect is enabled (default: True for aesthetics)
            use_typewriter = getattr(config, "CHAT_TYPEWRITER_EFFECT", True)
            
            if use_typewriter:
                # Typewriter reveal for bot messages
                self._chat_history.insert("end", " ", msg_tag)  # placeholder start
                self._chat_history.configure(state="disabled")
                self._chat_history.see("end")
                self._typewriter_reveal(text + " \n", msg_tag, 0)
                return
            else:
                # Instant display - much faster
                self._chat_history.insert("end", f" {text} \n", msg_tag)
        elif tag == "error":
            self._chat_history.insert("end", f"  Error  {ts}\n", "bot_label")
            self._chat_history.insert("end", f" {text} \n", "error")
        else:
            self._chat_history.insert("end", f"{text}\n", tag)
        self._chat_history.configure(state="disabled")
        self._chat_history.see("end")

    def _load_chat_history(self):
        """Load recent messages from previous sessions into the chat panel."""
        try:
            prev = self.backend.get_previous_messages(limit=20)
            if not prev:
                return
            self._chat_history.configure(state="normal")
            self._chat_history.insert("end", "── Previous Session ──\n", "system")
            for msg in prev:
                role = msg.get("role", "system")
                text = msg.get("text", "")
                if not text:
                    continue
                if role == "user":
                    self._chat_history.insert("end", f"  You\n", "user_label")
                    self._chat_history.insert("end", f" {text} \n", "user_msg")
                elif role == "assistant":
                    self._chat_history.insert("end", f"  Onyx\n", "bot_label")
                    self._chat_history.insert("end", f" {text} \n", "bot_msg")
                else:
                    self._chat_history.insert("end", f"{text}\n", "system")
            self._chat_history.insert("end", "── New Session ──\n", "system")
            self._chat_history.configure(state="disabled")
            self._chat_history.see("end")
        except Exception:
            pass  # history loading is non-critical

    def _typewriter_reveal(self, text: str, tag: str, idx: int):
        """Reveal text character-by-character in the chat history."""
        if not self._running or idx >= len(text):
            return
        self._chat_history.configure(state="normal")
        self._chat_history.insert("end", text[idx], tag)
        self._chat_history.configure(state="disabled")
        self._chat_history.see("end")
        # Speed: 20ms per char (~50 chars/sec), fast enough to not annoy
        self.root.after(20, self._typewriter_reveal, text, tag, idx + 1)

    @staticmethod
    def _progress_bar(step: int, total: int, width: int = 12) -> str:
        """Build a compact text progress bar like [████░░░░░░░░]."""
        if total <= 0:
            return ""
        filled = max(1, round(width * step / total))
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}]"

    def _show_typing(self, show: bool = True):
        """Show or hide the typing indicator."""
        self._typing_visible = show
        if show:
            self._typing_dots = 0
            self._animate_typing()
        else:
            self._typing_label.configure(text="")

    def _animate_typing(self):
        """Animate the typing indicator dots."""
        if not self._typing_visible:
            return
        self._typing_dots = (self._typing_dots % 3) + 1
        dots = "·" * self._typing_dots + " " * (3 - self._typing_dots)
        self._typing_label.configure(text=f"  Onyx is thinking {dots}")
        self.root.after(400, self._animate_typing)

    def _send_message(self):
        text = self._input_var.get().strip()
        if not text:
            return
        self._input_var.set("")
        self._append_chat(text, "user")

        # Open chat if not visible
        if not self._chat_visible:
            self._toggle_chat()

        self.backend.submit_goal(text)

    # ------------------------------------------------------------------
    # Voice controls
    # ------------------------------------------------------------------

    def _on_mic_click(self):
        if self.backend.is_busy:
            self._append_chat("Agent is busy.", "system")
            return
        self._recording = True
        self._mic_btn.configure(bg=BTN_RECORDING, fg="#ffffff", text=" 🎤 Recording... ")
        self.backend.listen(duration=5.0)

    def _on_handsfree_click(self):
        active = self.backend.toggle_hands_free()
        if active:
            self._hf_btn.configure(fg=BTN_HANDSFREE, bg="#0a2020")
        else:
            self._hf_btn.configure(fg=ACCENT_DIM, bg=BTN_BG)

    def _toggle_tts(self):
        self._tts_enabled = not self._tts_enabled
        if self._tts_enabled:
            self._tts_btn.configure(fg=ACCENT_MID, text=" 🔊 TTS ")
        else:
            self._tts_btn.configure(fg="#444444", text=" 🔇 TTS ")

    # ------------------------------------------------------------------
    # Backend callback polling
    # ------------------------------------------------------------------

    def _poll_backend(self):
        if not self._running:
            return

        for cb in self.backend.poll_callbacks():
            kind = cb.kind
            data = cb.data

            if kind == "response":
                self._show_typing(False)
                self._append_chat(data["text"], "success" if data.get("success") else "bot")
                # Flash emotion based on outcome
                if data.get("success"):
                    self.face.set_emotion("satisfied")
                else:
                    self.face.set_emotion("neutral")

            elif kind == "speak":
                self._show_typing(False)
                # Strip roleplay actions (*glows brighter*) — show in chat, not TTS
                from face.backend import strip_roleplay_for_tts
                clean_speech, action_emotions = strip_roleplay_for_tts(data["text"])
                # Trigger face emotions from any actions found
                if action_emotions:
                    self.face.set_emotion(action_emotions[0])
                # TTS in background — mouth animation starts on "speak_start"
                if self._tts_enabled and clean_speech:
                    self.backend.speak_tts(clean_speech)
                elif clean_speech:
                    # No TTS — animate mouth immediately (visual only)
                    self.face.speak(clean_speech, chars_per_sec=13)
                    if not action_emotions:
                        self.face.set_emotion("amused")

            elif kind == "speak_start":
                # Audio playback is about to begin — sync mouth animation now
                from face.backend import strip_roleplay_for_tts
                clean_speech, _ = strip_roleplay_for_tts(data["text"])
                cps = data.get("chars_per_sec", 13.0)
                if clean_speech:
                    self.face.speak(clean_speech, chars_per_sec=cps)
                self.face.set_emotion("amused")

            elif kind == "status":
                state = data.get("state", "idle")
                self.face.set_status(data.get("text", ""))
                if state == "thinking":
                    self.face.set_emotion("thinking")
                    self.face.set_idle(False)
                    self._status_dot.configure(fg="#ffaa00")
                    self._show_typing(True)
                elif state == "building":
                    self.face.set_emotion("focused")
                    self.face.set_idle(False)
                    self._status_dot.configure(fg="#55ccff")
                    self._show_typing(True)
                    # Override typing text for building
                    self._typing_label.configure(text="  Onyx is coding...")
                elif state == "working":
                    self.face.set_emotion("working")
                    self.face.set_idle(False)
                    self._status_dot.configure(fg="#00ff88")
                    self._show_typing(False)
                    # Drop topmost during task execution so agent can work
                    self.root.attributes("-topmost", False)
                elif state == "listening":
                    self.face.set_emotion("listening")
                    self.face.set_idle(False)
                    self._status_dot.configure(fg="#ff4444")
                    self._show_typing(False)
                else:  # idle
                    self.face.set_emotion("neutral")
                    self.face.set_idle(True)
                    self._status_dot.configure(fg=ACCENT_DIM)
                    self._show_typing(False)
                    self.root.attributes("-topmost", True)

            elif kind == "progress":
                step = data.get("step", 0)
                total = data.get("total", 0)
                desc = data.get("description", "")
                status = data.get("status", "")
                if status == "started":
                    bar = self._progress_bar(step, total)
                    self._append_chat(f"{bar}  Step {step}/{total}: {desc}", "system")
                    self.face.set_status(f"Step {step}/{total}")
                elif status == "completed":
                    self.face.set_emotion("satisfied" if step == total else "working")

            elif kind == "narration":
                narr_text = data.get("text", "")
                self._append_chat(f"🔨 {narr_text}", "system")
                self.face.set_status(narr_text[:40])

            elif kind == "heard":
                # STT result — put in input and auto-send
                text = data["text"]
                self._recording = False
                self._mic_btn.configure(bg=BTN_BG, fg=BTN_FG, text=" 🎤 Mic ")
                self._append_chat(text, "user")

                if not self._chat_visible:
                    self._toggle_chat()

                self.backend.submit_goal(text)

                # Hands-free loop will restart automatically after TTS completes (handled in backend)

            elif kind == "mode_change":
                self._update_mode_ui(data.get("mode", "companion"))

            elif kind == "apps_refresh":
                if self._apps_visible:
                    self._refresh_apps()

            elif kind == "ext_launch":
                self._open_ext_remote(data.get("ext_name", ""))

            elif kind == "workflow_builder_open":
                self._open_workflow_builder()

            elif kind == "node_canvas_open":
                self._open_node_canvas()

            elif kind == "workflow_done":
                status = data.get("status", "")
                wf_id = data.get("workflow_id", "")
                if status == "error":
                    self._append_chat(
                        f"Workflow {wf_id} failed: {data.get('error', '')}", "error"
                    )
                else:
                    nc = data.get("node_count", 0)
                    self._append_chat(
                        f"Workflow {wf_id} completed ({nc} nodes)", "system"
                    )

            elif kind == "face_customize":
                theme = data.get("theme")
                eye_style = data.get("eye_style")
                if theme:
                    self.face.apply_theme(theme)
                if eye_style:
                    self.face.apply_customization(eye_style=eye_style)

            elif kind == "toolforge_build":
                self._open_toolforge(data)

            # -- Workflow HUD callbacks --
            elif kind == "hud_start":
                self._hud_start_workflow(data)
            elif kind == "hud_step_active":
                if self._workflow_hud:
                    self._workflow_hud.set_step_active(data.get("index", 0))
            elif kind == "hud_step_done":
                if self._workflow_hud:
                    self._workflow_hud.set_step_done(
                        data.get("index", 0),
                        success=data.get("success", True),
                        duration=data.get("duration", 0),
                    )
            elif kind == "hud_activity":
                if self._workflow_hud:
                    self._workflow_hud.set_activity(data.get("text", ""))
            elif kind == "hud_narration":
                if self._workflow_hud:
                    self._workflow_hud.set_narration(data.get("text", ""))
            elif kind == "hud_progress":
                if self._workflow_hud:
                    self._workflow_hud.set_progress(
                        data.get("current", 0), data.get("total", 0))
            elif kind == "hud_finish":
                if self._workflow_hud:
                    self._workflow_hud.finish(
                        success=data.get("success", True),
                        message=data.get("message", ""),
                    )

            elif kind == "system":
                self._append_chat(data["text"], "system")

            elif kind == "error":
                self._append_chat(data["message"], "error")
                self._recording = False
                self._mic_btn.configure(bg=BTN_BG, fg=BTN_FG, text=" 🎤 Mic ")

        self.root.after(50, self._poll_backend)

    # ------------------------------------------------------------------
    # ToolForge popup
    # ------------------------------------------------------------------

    _toolforge_win = None

    def _open_toolforge(self, data: dict):
        """Open the ToolForge popup and run the build flow."""
        from face.toolforge import ToolForgeWindow
        import threading

        tool_name = data.get("tool_name", "App")
        display_name = data.get("display_name", f"Onyx {tool_name}")
        safe_name = data.get("safe_name", tool_name.lower().replace(" ", "_"))
        code = data.get("code", "")
        tool_dir = data.get("tool_dir", "")
        description = data.get("description", tool_name)

        def _on_approve():
            self.backend.tool_build_approve(
                tool_name=tool_name,
                display_name=display_name,
                safe_name=safe_name,
                description=description,
            )
            self._append_chat(f"✅ {display_name} approved and added to apps!", "success")

        def _on_edit(change_desc):
            # Rebuild with the user's requested changes
            self.backend.tool_build(
                tool_name=tool_name,
                description=f"{description}. Changes: {change_desc}",
                rebuild=True,
            )

        def _on_close():
            self._toolforge_win = None

        self._toolforge_win = ToolForgeWindow(
            parent=self.root,
            tool_name=display_name,
            on_approve=_on_approve,
            on_edit=_on_edit,
            on_close=_on_close,
        )

        self._append_chat(f"⚡ ToolForge: Building {display_name}...", "system")
        self.face.set_emotion("determined")

        # Run the build flow in a background thread
        def _run_flow():
            self._toolforge_win.run_build_flow(code, tool_dir)

        threading.Thread(target=_run_flow, daemon=True).start()

    # ------------------------------------------------------------------
    # Workflow HUD (floating progress panels around Onyx)
    # ------------------------------------------------------------------

    def _hud_start_workflow(self, data: dict):
        """Create or reuse the WorkflowHUD and start showing a workflow."""
        from face.workflow_hud import WorkflowHUD
        if self._workflow_hud and self._workflow_hud.is_visible:
            self._workflow_hud.dismiss()
        self._workflow_hud = WorkflowHUD(self.root)
        self._workflow_hud.start_workflow(
            workflow_id=data.get("workflow_id", ""),
            step_names=data.get("step_names", []),
            step_ids=data.get("step_ids"),
        )

    # ------------------------------------------------------------------
    # Workflow Builder & Node Canvas
    # ------------------------------------------------------------------

    _workflow_builder_win = None
    _node_canvas_win = None

    def _open_workflow_builder(self):
        """Open the list-based workflow builder window."""
        if self._workflow_builder_win is not None:
            try:
                self._workflow_builder_win.lift()
                self._workflow_builder_win.focus_force()
                return
            except tk.TclError:
                self._workflow_builder_win = None

        from face.workflow_builder import WorkflowBuilderWindow

        def _on_close():
            self._workflow_builder_win = None

        self._workflow_builder_win = WorkflowBuilderWindow(
            self.root, on_close=_on_close,
        )

    def _open_node_canvas(self, workflow=None):
        """Open the visual node canvas window."""
        if self._node_canvas_win is not None:
            try:
                self._node_canvas_win.lift()
                self._node_canvas_win.focus_force()
                return
            except tk.TclError:
                self._node_canvas_win = None

        from face.node_canvas import NodeCanvasWindow

        def _on_close():
            self._node_canvas_win = None

        self._node_canvas_win = NodeCanvasWindow(
            self.root, workflow=workflow, on_close=_on_close,
        )

    def _prompt_build_app(self):
        """Open a dialog to let the user request a new app build."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Build New App")
        dialog.configure(bg="#0a0e16")
        dialog.geometry("380x180")
        dialog.attributes("-topmost", True)
        dialog.transient(self.root)

        tk.Label(dialog, text="What app should Onyx build?",
                 bg="#0a0e16", fg="#c8d8e0", font=("Consolas", 10)).pack(padx=12, pady=(12, 4))

        name_entry = tk.Entry(dialog, bg="#0c1018", fg="#c8d8e0",
                              font=("Consolas", 10), insertbackground="#00e5ff",
                              relief="flat", bd=2)
        name_entry.pack(fill="x", padx=12, pady=4)
        name_entry.insert(0, "Timer")
        name_entry.focus_set()

        tk.Label(dialog, text="Description (optional):",
                 bg="#0a0e16", fg="#5a7a8a", font=("Consolas", 9)).pack(padx=12, pady=(4, 0), anchor="w")

        desc_entry = tk.Entry(dialog, bg="#0c1018", fg="#c8d8e0",
                              font=("Consolas", 10), insertbackground="#00e5ff",
                              relief="flat", bd=2)
        desc_entry.pack(fill="x", padx=12, pady=4)

        def _submit():
            name = name_entry.get().strip()
            desc = desc_entry.get().strip()
            dialog.destroy()
            if name:
                self.backend.tool_build(name, desc)

        name_entry.bind("<Return>", lambda e: _submit())
        desc_entry.bind("<Return>", lambda e: _submit())

        btn = tk.Label(dialog, text=" ⚡ Build ", bg="#0e1620", fg="#00e5ff",
                       font=("Consolas", 10, "bold"), cursor="hand2", padx=12, pady=4)
        btn.pack(pady=8)
        btn.bind("<Button-1>", lambda e: _submit())

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Window management — position, size, awareness
    # ------------------------------------------------------------------

    # Default size: face only (no panels)
    _DEFAULT_W = REF_W
    _DEFAULT_H = REF_H + CTRL_STRIP_H

    # Minimum size when docked to a corner (as small as possible)
    _COMPACT_W = FACE_MIN_W
    _COMPACT_H = FACE_MIN_H + CTRL_STRIP_H

    # Taskbar height estimate (Windows)
    _TASKBAR_H = 48

    def get_window_rect(self) -> dict:
        """Get current window position and size."""
        self.root.update_idletasks()
        return {
            "x": self.root.winfo_x(),
            "y": self.root.winfo_y(),
            "width": self.root.winfo_width(),
            "height": self.root.winfo_height(),
        }

    def get_screen_size(self) -> tuple[int, int]:
        """Get screen dimensions."""
        return (self.root.winfo_screenwidth(), self.root.winfo_screenheight())

    def move_window(self, x: int, y: int):
        """Move the window to absolute screen coordinates."""
        self.root.geometry(f"+{x}+{y}")
        self.root.update_idletasks()

    def resize_window(self, width: int, height: int):
        """Resize the window."""
        self.root.geometry(f"{width}x{height}")
        self.root.update_idletasks()

    def position_center(self, width: int = 0, height: int = 0):
        """Center the window on screen with given or default size."""
        w = width or self._DEFAULT_W
        h = height or self._DEFAULT_H
        sw, sh = self.get_screen_size()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.update_idletasks()
        _log.debug("Window centered: %dx%d at +%d+%d", w, h, x, y)

    def position_bottom_left(self, compact: bool = True):
        """Move to bottom-left corner, as small as possible.

        Used when Blender is the primary focus.
        """
        sw, sh = self.get_screen_size()
        w = self._COMPACT_W if compact else self._DEFAULT_W
        h = self._COMPACT_H if compact else self._DEFAULT_H
        x = 8  # small margin from left edge
        y = sh - h - self._TASKBAR_H
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.update_idletasks()
        _log.debug("Window bottom-left: %dx%d at +%d+%d", w, h, x, y)

    def position_bottom_right(self, compact: bool = True):
        """Move to bottom-right corner, as small as possible.

        Used when Unreal Engine is the primary focus.
        """
        sw, sh = self.get_screen_size()
        w = self._COMPACT_W if compact else self._DEFAULT_W
        h = self._COMPACT_H if compact else self._DEFAULT_H
        x = sw - w - 8  # small margin from right edge
        y = sh - h - self._TASKBAR_H
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.update_idletasks()
        _log.debug("Window bottom-right: %dx%d at +%d+%d", w, h, x, y)

    def position_default(self):
        """Restore to default centered size, closing any open panels."""
        self._close_all_panels()
        self.position_center(self._DEFAULT_W, self._DEFAULT_H)

    def _close_all_panels(self):
        """Close chat, apps, and extensions panels if open."""
        if self._chat_visible:
            self._toggle_chat()
        if self._apps_visible:
            self._toggle_apps()
        if self._ext_visible:
            self._toggle_extensions()

    def _open_chat_panel(self):
        """Ensure chat panel is open."""
        if not self._chat_visible:
            self._toggle_chat()

    def _close_chat_panel(self):
        """Ensure chat panel is closed."""
        if self._chat_visible:
            self._toggle_chat()

    def set_always_on_top(self, on_top: bool):
        """Set whether the window stays on top."""
        self.root.attributes("-topmost", on_top)

    # ------------------------------------------------------------------
    # Demo lifecycle — polished window management during demos
    # ------------------------------------------------------------------

    def demo_prepare_for_program(self, program: str = "blender"):
        """Prepare Onyx's window for when a program is the focus.

        Closes panels, shrinks to compact, moves to the appropriate corner.
        """
        self._close_all_panels()
        if program.lower() in ("blender", "blender3d"):
            self.position_bottom_left(compact=True)
        elif program.lower() in ("unreal", "ue", "unreal engine"):
            self.position_bottom_right(compact=True)
        else:
            self.position_bottom_left(compact=True)
        self.set_always_on_top(True)

    def demo_return_to_center(self):
        """After demo work, return to default centered position."""
        self._close_all_panels()
        self.position_center(self._DEFAULT_W, self._DEFAULT_H)
        self.set_always_on_top(True)

    def demo_open_for_narration(self):
        """Open chat panel so narration is visible during demos."""
        self._open_chat_panel()

    def demo_cleanup(self):
        """Full cleanup after a demo: re-center, resize, close panels."""
        self._close_all_panels()
        self.position_center(self._DEFAULT_W, self._DEFAULT_H)
        self.set_always_on_top(True)
        self.face.set_emotion("neutral")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self):
        self._running = False
        if self._workflow_hud:
            try:
                self._workflow_hud.dismiss()
            except Exception:
                pass
            self._workflow_hud = None
        if self._chat_float_win:
            try:
                self._chat_float_win.destroy()
            except tk.TclError:
                pass
            self._chat_float_win = None
        if hasattr(self, '_body'):
            self._body.detach()
        self.face.stop()
        try:
            self.root.destroy()
        except tk.TclError:
            pass  # window already destroyed

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_APP_STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "app_state.json")


def _load_app_state() -> dict:
    try:
        with open(_APP_STATE_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_app_state(state: dict):
    os.makedirs(os.path.dirname(_APP_STATE_PATH), exist_ok=True)
    with open(_APP_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def _run_onboarding(app: OnyxKrakenApp):
    """Guided onboarding sequence for first-time users."""

    def _step(delay: float, text: str, emotion: str = "neutral",
              speak: bool = True, tag: str = "system"):
        time.sleep(delay)
        if speak:
            app.face.set_emotion(emotion)
            app.face.speak(text, chars_per_sec=11)
        app.root.after(0, lambda: app._append_chat(text, tag))

    time.sleep(1.5)
    _step(0.5, "Hello! I'm OnyxKraken — your autonomous desktop agent.", "curious", True, "bot")
    _step(4.0, "I can see your screen, control your apps, and complete tasks for you.", "amused", True, "bot")
    _step(4.5, "Here's how to get started:", "neutral", False, "system")
    _step(1.5, "💬  Type a goal in the text box below (e.g. \"Open Notepad and write hello\")", "neutral", False, "system")
    _step(1.0, "🎤  Or click the Mic button to speak your goal", "neutral", False, "system")
    _step(1.0, "⚡  Toggle Hands-free for continuous voice mode", "neutral", False, "system")
    _step(1.5, "I'll plan the steps, take screenshots, and execute actions automatically.", "determined", True, "bot")
    _step(4.5, "Ready when you are. What would you like me to do?", "satisfied", True, "bot")

    # Mark onboarding complete
    state = _load_app_state()
    state["onboarding_complete"] = True
    state["onboarding_date"] = datetime.now().isoformat()
    _save_app_state(state)


def _run_returning_welcome(app: OnyxKrakenApp):
    """Short welcome for returning users."""
    time.sleep(1.5)
    app.face.speak("Hello. I am OnyxKraken.", chars_per_sec=10)
    app.face.set_emotion("satisfied")
    time.sleep(3)
    app.root.after(0, lambda: app._append_chat(
        "Ready. Type a goal or click the mic to speak.", "system"))

    # Check for unverified tools and notify
    try:
        from core.toolsmith import list_tools
        tools = list_tools()
        drafts = [t for t in tools if t.status == "draft"]
        if drafts:
            time.sleep(1.5)
            names = ", ".join(t.display_name for t in drafts)
            msg = f"📱 {len(drafts)} app(s) need verification: {names}. Open the Apps panel to test and verify."
            app.root.after(0, lambda: app._append_chat(msg, "system"))
            # Auto-open the apps panel
            time.sleep(1.0)
            app.root.after(0, lambda: app._toggle_apps() if not app._apps_visible else None)
    except Exception:
        pass


def main():
    app = OnyxKrakenApp()

    state = _load_app_state()
    if state.get("onboarding_complete"):
        threading.Thread(target=_run_returning_welcome, args=(app,), daemon=True).start()
    else:
        threading.Thread(target=_run_onboarding, args=(app,), daemon=True).start()

    app.run()


if __name__ == "__main__":
    main()
