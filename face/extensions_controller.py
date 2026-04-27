"""Extensions Controller — floating command center for all Onyx capabilities.

A full-featured floating window that replaces the old docked Extensions panel.
Provides one-click access to:
  - Extensions (SmartEngine, EVERA, JustEdit) with Open Remote buttons
  - Chain Workflows (full production, battle recap, music video, etc.)
  - Autonomous Hands (activate/deactivate/run, dashboard)
  - System Health (live CPU/RAM/VRAM/disk/services)
  - Connections (Discord, external integrations)
  - Quick Actions (demos, recording, Blender build, DJ set)

Usage:
    from face.extensions_controller import ExtensionsController
    ctrl = ExtensionsController(root, backend=backend, on_close=callback)
"""

import logging
import threading
import time
import tkinter as tk
from typing import Callable, Optional

_log = logging.getLogger("face.extensions_controller")

# ---------------------------------------------------------------------------
# Theme (matching Face GUI dark theme)
# ---------------------------------------------------------------------------

BG = "#060a10"
BG_PANEL = "#0a0e16"
BG_CARD = "#0a1220"
BG_BTN = "#0e1620"
BG_BTN_HOVER = "#142030"
BG_SECTION = "#080c14"
BG_INPUT = "#0c1220"
ACCENT = "#00e5ff"
ACCENT_MID = "#0088aa"
ACCENT_DIM = "#005566"
TEXT = "#c0d0e0"
TEXT_DIM = "#6a7a8a"
TEXT_VDIM = "#3a4a5a"
BORDER = "#0e2a3d"
SUCCESS = "#00e676"
ERROR = "#ff5252"
WARNING = "#ffab40"

# Section accent colors
SEC_EXT = "#e040fb"
SEC_CHAIN = "#ff6e40"
SEC_HANDS = "#40c4ff"
SEC_HEALTH = "#00e676"
SEC_CONN = "#ffab40"
SEC_QUICK = "#00e5ff"

WINDOW_W = 520
WINDOW_H = 780


class ExtensionsController:
    """Floating command center window for all Onyx capabilities."""

    def __init__(self, parent: tk.Tk, backend=None,
                 on_close: Optional[Callable] = None,
                 ext_remotes: Optional[dict] = None,
                 open_ext_remote_fn: Optional[Callable] = None):
        self.parent = parent
        self.backend = backend
        self._on_close = on_close
        self._ext_remotes = ext_remotes or {}
        self._open_ext_remote = open_ext_remote_fn
        self._running = True
        self._health_poll_id = None

        self._build_window()
        self._start_health_polling()

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _build_window(self):
        self.win = tk.Toplevel(self.parent)
        self.win.title("Onyx Controller")
        self.win.configure(bg=BG)
        self.win.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.win.minsize(420, 500)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.attributes("-topmost", True)

        # Position right of parent
        self.win.update_idletasks()
        try:
            px = self.parent.winfo_rootx() + self.parent.winfo_width() + 12
            py = self.parent.winfo_rooty()
            self.win.geometry(f"+{px}+{py}")
        except Exception:
            pass

        # Title bar
        title_bar = tk.Frame(self.win, bg=BG_PANEL, height=42)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)

        tk.Label(
            title_bar, text="  \u26a1  Onyx Controller",
            bg=BG_PANEL, fg=ACCENT, font=("Consolas", 13, "bold"), anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=4)

        ref_btn = tk.Label(
            title_bar, text=" \u27f3 ", bg=BG_PANEL, fg=ACCENT_DIM,
            font=("Consolas", 14), cursor="hand2",
        )
        ref_btn.pack(side="right", padx=2)
        ref_btn.bind("<Button-1>", lambda e: self._rebuild_content())
        ref_btn.bind("<Enter>", lambda e: ref_btn.configure(fg=ACCENT))
        ref_btn.bind("<Leave>", lambda e: ref_btn.configure(fg=ACCENT_DIM))

        close_btn = tk.Label(
            title_bar, text=" \u2715 ", bg=BG_PANEL, fg=ACCENT_DIM,
            font=("Consolas", 14), cursor="hand2",
        )
        close_btn.pack(side="right", padx=4)
        close_btn.bind("<Button-1>", lambda e: self.close())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=ERROR))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=ACCENT_DIM))

        tk.Frame(self.win, bg=BORDER, height=1).pack(fill="x")

        # Status bar (bottom)
        tk.Frame(self.win, bg=BORDER, height=1).pack(side="bottom", fill="x")
        self._status_frame = tk.Frame(self.win, bg=BG_SECTION, height=24)
        self._status_frame.pack(side="bottom", fill="x")
        self._status_frame.pack_propagate(False)
        self._status_label = tk.Label(
            self._status_frame, text="  Ready", bg=BG_SECTION, fg=TEXT_DIM,
            font=("Consolas", 8), anchor="w",
        )
        self._status_label.pack(side="left", fill="x", expand=True, padx=4)

        # Scrollable content
        self._canvas = tk.Canvas(self.win, bg=BG, highlightthickness=0)
        self._scrollbar = tk.Scrollbar(
            self.win, orient="vertical", command=self._canvas.yview,
        )
        self._content = tk.Frame(self._canvas, bg=BG)
        self._content.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.create_window((0, 0), window=self._content, anchor="nw",
                                    tags="content_window")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(fill="both", expand=True)

        def _resize_content(event):
            self._canvas.itemconfig("content_window", width=event.width)
        self._canvas.bind("<Configure>", _resize_content)

        def _on_mousewheel(event):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._canvas.bind("<MouseWheel>", _on_mousewheel)
        self._content.bind("<MouseWheel>", _on_mousewheel)

        self._build_content()

    def _rebuild_content(self):
        for child in self._content.winfo_children():
            child.destroy()
        self._build_content()
        self._set_status("Refreshed")

    def _build_content(self):
        self._build_system_health_section()
        self._build_extensions_section()
        self._build_chain_workflows_section()
        self._build_hands_section()
        self._build_quick_actions_section()
        self._build_connections_section()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _section_header(self, title: str, icon: str, color: str):
        sep = tk.Frame(self._content, bg=BORDER, height=1)
        sep.pack(fill="x", padx=8, pady=(14, 0))
        hdr = tk.Frame(self._content, bg=BG)
        hdr.pack(fill="x", padx=12, pady=(6, 4))
        tk.Label(hdr, text=f"{icon}  {title}", bg=BG, fg=color,
                 font=("Consolas", 11, "bold"), anchor="w").pack(side="left")
        return hdr

    def _make_btn(self, parent, text: str, command: Callable,
                  fg: str = ACCENT, bg_color: str = BG_BTN,
                  side: str = "left", font_size: int = 9, pady: int = 4):
        btn = tk.Label(
            parent, text=f"  {text}  ", bg=bg_color, fg=fg,
            font=("Consolas", font_size), cursor="hand2", pady=pady,
        )
        btn.pack(side=side, padx=4, pady=3)
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.configure(bg=BG_BTN_HOVER))
        btn.bind("<Leave>", lambda e: btn.configure(bg=bg_color))
        return btn

    def _make_card(self, parent) -> tk.Frame:
        card = tk.Frame(parent, bg=BG_CARD,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", padx=10, pady=3)

        def _enter(e, c=card):
            c.configure(highlightbackground=ACCENT_DIM)
        def _leave(e, c=card):
            c.configure(highlightbackground=BORDER)
        card.bind("<Enter>", _enter)
        card.bind("<Leave>", _leave)
        card.bind("<MouseWheel>",
                  lambda e: self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        return card

    def _set_status(self, text: str):
        try:
            self._status_label.configure(text=f"  {text}")
        except Exception:
            pass

    def _submit_goal(self, goal: str):
        if self.backend:
            self.backend.submit_goal(goal)
            self._set_status(f"Sent: {goal[:50]}")
        else:
            self._set_status("No backend connected")

    # ------------------------------------------------------------------
    # Section: System Health (live)
    # ------------------------------------------------------------------

    def _build_system_health_section(self):
        self._section_header("System Health", "\U0001f49a", SEC_HEALTH)

        self._health_card = self._make_card(self._content)
        self._health_labels = {}

        grid = tk.Frame(self._health_card, bg=BG_CARD)
        grid.pack(fill="x", padx=10, pady=6)

        for i, (key, label) in enumerate([
            ("cpu", "CPU"), ("ram", "RAM"),
            ("vram", "VRAM"), ("disk", "Disk"),
        ]):
            col = i % 2
            row = i // 2
            f = tk.Frame(grid, bg=BG_CARD)
            f.grid(row=row, column=col, sticky="ew", padx=6, pady=2)
            grid.columnconfigure(col, weight=1)

            tk.Label(f, text=label, bg=BG_CARD, fg=TEXT_DIM,
                     font=("Consolas", 8), anchor="w", width=5).pack(side="left")
            val = tk.Label(f, text="...", bg=BG_CARD, fg=TEXT,
                           font=("Consolas", 9, "bold"), anchor="w")
            val.pack(side="left", fill="x", expand=True)
            self._health_labels[key] = val

        svc_frame = tk.Frame(self._health_card, bg=BG_CARD)
        svc_frame.pack(fill="x", padx=10, pady=(2, 6))
        tk.Label(svc_frame, text="Services:", bg=BG_CARD, fg=TEXT_DIM,
                 font=("Consolas", 8)).pack(side="left")
        self._health_labels["services"] = tk.Label(
            svc_frame, text="...", bg=BG_CARD, fg=TEXT,
            font=("Consolas", 8), anchor="w", wraplength=380,
        )
        self._health_labels["services"].pack(side="left", fill="x", expand=True, padx=4)

        self._health_labels["warnings"] = tk.Label(
            self._health_card, text="", bg=BG_CARD, fg=WARNING,
            font=("Consolas", 8), anchor="w", wraplength=440,
        )
        self._health_labels["warnings"].pack(fill="x", padx=10, pady=(0, 4))

        self._update_health()

    def _update_health(self):
        def _do():
            try:
                from core.system_health import health
                r = health.get_report(force=True)

                cpu_text = f"{r.cpu.usage_percent:.0f}% ({r.cpu.core_count} cores)"
                ram_text = f"{r.ram.used_gb:.1f}/{r.ram.total_gb:.1f} GB ({r.ram.percent:.0f}%)"
                if r.vram.available:
                    vram_text = f"{r.vram.free_gb:.1f} GB free ({r.vram.gpu_name})"
                else:
                    vram_text = "No GPU"
                disk_text = f"{r.disk.free_gb:.1f}/{r.disk.total_gb:.1f} GB free"

                svc_parts = []
                for s in r.services:
                    dot = "\u25cf" if s.running else "\u25cb"
                    svc_parts.append(f"{dot} {s.name}")
                svc_text = "  ".join(svc_parts)

                warn_text = "  |  ".join(r.warnings) if r.warnings else ""

                self.win.after(0, lambda: self._apply_health(
                    cpu_text, ram_text, vram_text, disk_text, svc_text, warn_text, r))
            except Exception as exc:
                self.win.after(0, lambda: self._health_labels.get("cpu", tk.Label()).configure(
                    text=f"Error: {exc}"))

        threading.Thread(target=_do, daemon=True).start()

    def _apply_health(self, cpu, ram, vram, disk, svcs, warns, report):
        try:
            self._health_labels["cpu"].configure(text=cpu)
            self._health_labels["ram"].configure(text=ram)
            vram_fg = WARNING if report.vram.percent > 85 else TEXT
            self._health_labels["vram"].configure(text=vram, fg=vram_fg)
            disk_fg = WARNING if report.disk.free_gb < 10 else TEXT
            self._health_labels["disk"].configure(text=disk, fg=disk_fg)
            self._health_labels["services"].configure(text=svcs)
            self._health_labels["warnings"].configure(text=warns)
        except Exception:
            pass

    def _start_health_polling(self):
        if not self._running:
            return
        self._update_health()
        self._health_poll_id = self.win.after(15000, self._start_health_polling)

    # ------------------------------------------------------------------
    # Section: Extensions
    # ------------------------------------------------------------------

    def _build_extensions_section(self):
        self._section_header("Extensions", "\U0001f9e9", SEC_EXT)

        try:
            from face.extensions import EXTENSION_REGISTRY
            exts = EXTENSION_REGISTRY
        except ImportError:
            exts = []

        for ext in exts:
            card = self._make_card(self._content)
            top = tk.Frame(card, bg=BG_CARD)
            top.pack(fill="x", padx=10, pady=(6, 2))

            tk.Label(top, text=ext.icon, bg=BG_CARD,
                     font=("Segoe UI Emoji", 14)).pack(side="left", padx=(0, 6))

            info = tk.Frame(top, bg=BG_CARD)
            info.pack(side="left", fill="x", expand=True)
            tk.Label(info, text=ext.display_name, bg=BG_CARD, fg=ext.color,
                     font=("Consolas", 10, "bold"), anchor="w").pack(fill="x")

            is_open = ext.name in self._ext_remotes
            status = "\u25cf Open" if is_open else "\u25cb Ready"
            status_fg = ext.color if is_open else TEXT_VDIM
            tk.Label(info, text=status, bg=BG_CARD, fg=status_fg,
                     font=("Consolas", 7)).pack(anchor="w")

            tk.Label(card, text=ext.description, bg=BG_CARD, fg=TEXT_DIM,
                     font=("Consolas", 7), wraplength=420, justify="left",
                     anchor="nw").pack(fill="x", padx=10, pady=(0, 4))

            btn_row = tk.Frame(card, bg=BG_CARD)
            btn_row.pack(fill="x", padx=8, pady=(0, 6))

            ext_name = ext.name
            if is_open:
                self._make_btn(btn_row, "\u2b06 Focus",
                               lambda n=ext_name: self._focus_ext(n), fg=ext.color)
            else:
                self._make_btn(btn_row, "\u25b6 Open Remote",
                               lambda n=ext_name: self._open_ext(n), fg=ext.color)

    def _open_ext(self, name: str):
        if self._open_ext_remote:
            self._open_ext_remote(name)
            self._set_status(f"Opened {name} remote")
            self.win.after(500, self._rebuild_content)

    def _focus_ext(self, name: str):
        remote = self._ext_remotes.get(name)
        if remote:
            try:
                remote.win.lift()
                remote.win.focus_force()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Section: Chain Workflows
    # ------------------------------------------------------------------

    _WORKFLOWS = [
        ("full_production", "Full Production",
         "Record \u2192 Music \u2192 Edit \u2192 Export MP4",
         "\U0001f3ac", "#ff6e40", "run the full production workflow"),
        ("beat_battle_recap", "Beat Battle Recap",
         "Load battle \u2192 Record recap \u2192 Edit \u2192 Export",
         "\U0001f94a", "#ff4081", "run the battle recap workflow"),
        ("music_video", "Music Video Pipeline",
         "Generate song \u2192 Create visuals \u2192 Edit \u2192 Export",
         "\U0001f3b5", "#e040fb", "run the music video pipeline"),
        ("highlight_reel", "Demo Highlight Reel",
         "Collect recordings \u2192 Add music \u2192 Compile showreel",
         "\U0001f39e\ufe0f", "#ffab40", "run the highlight reel workflow"),
        ("3d_showcase", "3D Showcase",
         "Build in Blender \u2192 Record \u2192 Score \u2192 Edit \u2192 Export",
         "\U0001f3d7\ufe0f", "#40c4ff", "run the 3d showcase workflow"),
    ]

    def _build_chain_workflows_section(self):
        self._section_header("Chain Workflows", "\u26a1", SEC_CHAIN)

        for wf_id, name, desc, icon, color, goal in self._WORKFLOWS:
            card = self._make_card(self._content)
            row = tk.Frame(card, bg=BG_CARD)
            row.pack(fill="x", padx=10, pady=6)

            tk.Label(row, text=icon, bg=BG_CARD,
                     font=("Segoe UI Emoji", 13)).pack(side="left", padx=(0, 8))

            info = tk.Frame(row, bg=BG_CARD)
            info.pack(side="left", fill="x", expand=True)
            tk.Label(info, text=name, bg=BG_CARD, fg=color,
                     font=("Consolas", 10, "bold"), anchor="w").pack(fill="x")
            tk.Label(info, text=desc, bg=BG_CARD, fg=TEXT_DIM,
                     font=("Consolas", 7), anchor="w").pack(fill="x")

            btn_area = tk.Frame(row, bg=BG_CARD)
            btn_area.pack(side="right")
            self._make_btn(btn_area, "\u25b6 Run",
                           lambda wid=wf_id: self._start_chain_workflow(wid),
                           fg=color)
            self._make_btn(btn_area, "\U0001f578 Nodes",
                           lambda wid=wf_id: self._open_node_view(wid),
                           fg="#00e5ff", font_size=8)
            self._make_btn(btn_area, "\u2713 Check",
                           lambda wid=wf_id: self._preflight_workflow(wid),
                           fg=TEXT_DIM, font_size=8)

    def _start_chain_workflow(self, workflow_id: str):
        """Directly execute a chain workflow via the backend."""
        if self.backend:
            self._set_status(f"Starting {workflow_id}...")
            # Use the backend's chain workflow runner which wires
            # narration + progress callbacks to the Face GUI
            def _do():
                self.backend._run_chain_workflow(workflow_id)
                self.win.after(0, lambda: self._set_status(
                    f"Workflow {workflow_id} finished"))
                self.win.after(500, self._rebuild_content)
            threading.Thread(target=_do, daemon=True).start()
        else:
            # No backend — run directly with status-bar narration
            self._set_status(f"Running {workflow_id} (no backend)...")
            def _do_direct():
                try:
                    from core.chain_workflow import run_workflow
                    def _narrate(text):
                        self.win.after(0, lambda t=text: self._set_status(t[:80]))
                    def _progress(cur, total, name):
                        self.win.after(0, lambda: self._set_status(
                            f"[{cur}/{total}] {name}"))
                    result = run_workflow(workflow_id,
                                         narrate_fn=_narrate,
                                         on_progress=_progress)
                    if result.success:
                        self.win.after(0, lambda: self._set_status(
                            f"\u2713 {workflow_id}: {result.steps_completed}/{result.steps_total} steps done"))
                    else:
                        self.win.after(0, lambda: self._set_status(
                            f"\u2717 {workflow_id}: {result.error[:60]}"))
                except Exception as exc:
                    self.win.after(0, lambda: self._set_status(f"Error: {exc}"))
            threading.Thread(target=_do_direct, daemon=True).start()

    def _preflight_workflow(self, workflow_id: str):
        """Run pre-flight for a workflow — auto-starts missing services."""
        self._set_status(f"Ensuring services for {workflow_id}...")
        def _do():
            try:
                from core.system_health import health
                # auto_start=True is the default — will launch missing engines
                ok, issues = health.can_run_chain_workflow(workflow_id, auto_start=True)
                if ok:
                    self.win.after(0, lambda: self._set_status(
                        f"\u2713 {workflow_id}: All services ready!"))
                    self.win.after(500, self._rebuild_content)
                else:
                    msg = f"\u2717 {workflow_id}: " + "; ".join(issues)
                    self.win.after(0, lambda: self._set_status(msg))
            except Exception as exc:
                self.win.after(0, lambda: self._set_status(f"Check error: {exc}"))
        threading.Thread(target=_do, daemon=True).start()

    def _open_node_view(self, workflow_id: str):
        """Open the node canvas with a chain workflow preset loaded."""
        import pathlib
        presets_dir = pathlib.Path(__file__).resolve().parent.parent / "core" / "nodes" / "presets"
        preset_path = presets_dir / f"{workflow_id}.json"

        workflow_data = None
        if preset_path.exists():
            try:
                import json as _json
                with open(preset_path, "r") as f:
                    workflow_data = _json.load(f)
            except Exception:
                pass

        # Open via the app's node canvas (if we have access to parent)
        try:
            from face.node_canvas import NodeCanvasWindow
            win = NodeCanvasWindow(self.win, workflow=workflow_data)
            self._set_status(f"Node view: {workflow_id}")
        except Exception as exc:
            self._set_status(f"Node view error: {exc}")

    # ------------------------------------------------------------------
    # Section: Autonomous Hands
    # ------------------------------------------------------------------

    _HAND_INFO = [
        ("content", "Content Creator", "Generate & schedule social posts", "\U0001f4dd", "#e040fb", 120),
        ("practice", "Skill Practice", "Practice weakest skill to improve", "\U0001f3cb\ufe0f", "#40c4ff", 180),
        ("monitor", "Change Monitor", "Watch files and dirs for changes", "\U0001f441\ufe0f", "#ffab40", 30),
        ("dj", "DJ Onyx", "Generate daily music tracks", "\U0001f3a7", "#ff6e40", 360),
        ("maintenance", "Maintenance", "Cleanup, health checks, compaction", "\U0001f527", "#00e676", 60),
    ]

    def _build_hands_section(self):
        self._section_header("Autonomous Hands", "\U0001f932", SEC_HANDS)

        dash_row = tk.Frame(self._content, bg=BG)
        dash_row.pack(fill="x", padx=12, pady=(2, 4))
        self._make_btn(dash_row, "\U0001f4ca Dashboard", self._show_hands_dashboard,
                       fg=SEC_HANDS)
        self._make_btn(dash_row, "\U0001f4c8 Telemetry", self._show_telemetry,
                       fg=ACCENT_MID)

        for hand_id, name, desc, icon, color, sched_min in self._HAND_INFO:
            card = self._make_card(self._content)
            row = tk.Frame(card, bg=BG_CARD)
            row.pack(fill="x", padx=10, pady=6)

            tk.Label(row, text=icon, bg=BG_CARD,
                     font=("Segoe UI Emoji", 13)).pack(side="left", padx=(0, 8))

            info = tk.Frame(row, bg=BG_CARD)
            info.pack(side="left", fill="x", expand=True)
            tk.Label(info, text=name, bg=BG_CARD, fg=color,
                     font=("Consolas", 10, "bold"), anchor="w").pack(fill="x")

            sched_text = f"Every {sched_min}min" if sched_min else "Manual"
            tk.Label(info, text=f"{desc}  \u2022  {sched_text}", bg=BG_CARD, fg=TEXT_DIM,
                     font=("Consolas", 7), anchor="w").pack(fill="x")

            btn_area = tk.Frame(row, bg=BG_CARD)
            btn_area.pack(side="right")
            self._make_btn(btn_area, "\u25b6 Run",
                           lambda hid=hand_id: self._submit_goal(f"run {hid} hand now"),
                           fg=color, font_size=8)
            self._make_btn(btn_area, "\u2713 On",
                           lambda hid=hand_id: self._submit_goal(f"activate {hid} hand"),
                           fg=SUCCESS, font_size=8)
            self._make_btn(btn_area, "\u2717 Off",
                           lambda hid=hand_id: self._submit_goal(f"deactivate {hid} hand"),
                           fg=ERROR, font_size=8)

    def _show_hands_dashboard(self):
        try:
            from core.hands.scheduler import HandScheduler
            from core.hands.builtin import create_all_hands
            sched = HandScheduler()
            for h in create_all_hands():
                sched.register(h)
            summary = sched.dashboard_summary()
        except Exception as exc:
            summary = f"Error loading dashboard: {exc}"
        self._show_popup("Hands Dashboard", summary, SEC_HANDS)

    def _show_telemetry(self):
        try:
            from core.telemetry import telemetry
            summary = telemetry.get_stats_summary()
        except Exception as exc:
            summary = f"Error loading telemetry: {exc}"
        self._show_popup("Telemetry Stats", summary, ACCENT_MID)

    def _show_popup(self, title: str, content: str, color: str):
        popup = tk.Toplevel(self.win)
        popup.title(title)
        popup.configure(bg=BG)
        popup.geometry("480x400")
        popup.attributes("-topmost", True)

        popup.update_idletasks()
        px = self.win.winfo_rootx() + 20
        py = self.win.winfo_rooty() + 50
        popup.geometry(f"+{px}+{py}")

        tk.Label(popup, text=f"  {title}", bg=BG_PANEL, fg=color,
                 font=("Consolas", 12, "bold"), anchor="w",
                 height=2).pack(fill="x")
        tk.Frame(popup, bg=BORDER, height=1).pack(fill="x")

        text_w = tk.Text(
            popup, bg=BG_SECTION, fg=TEXT, font=("Consolas", 9),
            wrap="word", relief="flat", bd=0, padx=12, pady=8,
            insertbackground=ACCENT,
        )
        text_w.pack(fill="both", expand=True, padx=4, pady=4)
        text_w.insert("1.0", content)
        text_w.configure(state="disabled")

        close_row = tk.Frame(popup, bg=BG, height=32)
        close_row.pack(fill="x")
        close_row.pack_propagate(False)
        self._make_btn(close_row, "Close", popup.destroy, fg=ACCENT_DIM)

    # ------------------------------------------------------------------
    # Section: Quick Actions
    # ------------------------------------------------------------------

    _QUICK_ACTIONS = [
        ("\U0001f3b5 Start DJ Set", "start a 15 minute DJ set", "#ff6e40"),
        ("\U0001f3ac Record Demo", "record a demo", "#ff4444"),
        ("\U0001f3d7\ufe0f Build House (Blender)", "build a house in Blender", "#40c4ff"),
        ("\U0001f3e2 Build Building (Blender)", "build a building in Blender", "#40c4ff"),
        ("\U0001f916 Build Robot (Blender)", "build a mech robot in Blender", "#40c4ff"),
        ("\U0001f94a Beat Battle", "start a beat battle", "#ff4081"),
        ("\U0001f4f8 Screenshot Self", "take a screenshot of yourself", "#ffab40"),
        ("\U0001f4dd Write a Story", "write a story", "#e040fb"),
        ("\U0001f3a8 Animation Studio", "open the animation studio", "#aa66ff"),
        ("\U0001f4a1 Show Capabilities", "what can you do", "#00e5ff"),
    ]

    def _build_quick_actions_section(self):
        self._section_header("Quick Actions", "\U0001f680", SEC_QUICK)

        # Two-column grid of action buttons
        grid = tk.Frame(self._content, bg=BG)
        grid.pack(fill="x", padx=10, pady=4)

        for i, (label, goal, color) in enumerate(self._QUICK_ACTIONS):
            col = i % 2
            row = i // 2
            grid.columnconfigure(col, weight=1)

            btn = tk.Label(
                grid, text=f"  {label}  ", bg=BG_BTN, fg=color,
                font=("Consolas", 8), cursor="hand2", pady=6,
                anchor="w",
            )
            btn.grid(row=row, column=col, sticky="ew", padx=4, pady=3)
            goal_copy = goal
            btn.bind("<Button-1>", lambda e, g=goal_copy: self._submit_goal(g))
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=BG_BTN_HOVER))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=BG_BTN))

    # ------------------------------------------------------------------
    # Section: Connections
    # ------------------------------------------------------------------

    def _build_connections_section(self):
        self._section_header("Connections", "\U0001f517", SEC_CONN)

        try:
            from face.connections import CONNECTIONS, get_manager
            mgr = get_manager()

            for ci in CONNECTIONS:
                is_conn = mgr.is_connected(ci.name)
                card = self._make_card(self._content)
                row = tk.Frame(card, bg=BG_CARD)
                row.pack(fill="x", padx=10, pady=4)

                dot = "\u25cf" if is_conn else "\u25cb"
                dot_fg = SUCCESS if is_conn else TEXT_VDIM

                tk.Label(row, text=f"{ci.icon} {ci.display_name}",
                         bg=BG_CARD, fg=ci.color,
                         font=("Consolas", 9, "bold")).pack(side="left")
                tk.Label(row, text=f" {dot}", bg=BG_CARD, fg=dot_fg,
                         font=("Consolas", 9)).pack(side="left", padx=4)

                conn_name = ci.name
                self._make_btn(row, "\u25b6 Open",
                               lambda n=conn_name: self._open_connection(n),
                               fg=ci.color, font_size=8, side="right")
        except Exception as exc:
            tk.Label(self._content, text=f"  Connections unavailable: {exc}",
                     bg=BG, fg=TEXT_DIM, font=("Consolas", 8)).pack(
                         anchor="w", padx=12, pady=4)

        # Bottom padding
        tk.Frame(self._content, bg=BG, height=20).pack(fill="x")

    def _open_connection(self, conn_name: str):
        """Delegate to the parent app's connection handler."""
        try:
            app = self.parent.nametowidget(".")
            if hasattr(app, "_open_connection_control"):
                app._open_connection_control(conn_name)
            else:
                self._set_status(f"Connection: {conn_name} (handler not found)")
        except Exception:
            self._set_status(f"Opening {conn_name}...")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self):
        self._running = False
        if self._health_poll_id:
            try:
                self.win.after_cancel(self._health_poll_id)
            except Exception:
                pass
        if self._on_close:
            self._on_close()
        try:
            self.win.destroy()
        except Exception:
            pass

    def focus(self):
        try:
            self.win.lift()
            self.win.focus_force()
        except Exception:
            pass
