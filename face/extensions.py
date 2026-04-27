"""Extensions — Retractable panel + remote control windows for OnyxKraken extensions.

Each extension (SmartEngine, Evera, JustEdit, etc.) gets a dedicated remote
control window with controls specific to that extension's functionality.

Extensions are registered in EXTENSION_REGISTRY and discovered automatically
by the Extensions panel in app.py.

Usage:
    from face.extensions import EXTENSION_REGISTRY, open_extension_remote
"""

import logging
import os
import threading
import time
import tkinter as tk
from typing import Callable, Optional

_log = logging.getLogger("face.extensions")

# ---------------------------------------------------------------------------
# Theme constants (matching Face GUI dark theme)
# ---------------------------------------------------------------------------

BG = "#060a10"
BG_PANEL = "#0a0e16"
BG_CARD = "#0a1220"
BG_INPUT = "#0c1220"
BG_BTN = "#0e1620"
BG_BTN_HOVER = "#142030"
BG_SECTION = "#080c14"
ACCENT = "#00e5ff"
ACCENT_MID = "#0088aa"
ACCENT_DIM = "#005566"
ACCENT_VDIM = "#003040"
TEXT = "#c0d0e0"
TEXT_DIM = "#6a7a8a"
TEXT_VDIM = "#3a4a5a"
BORDER = "#0e2a3d"
SUCCESS = "#00e676"
ERROR = "#ff5252"
WARNING = "#ffab40"

# Extension-specific accent colors
EXT_COLORS = {
    "smartengine": "#e040fb",   # purple — writing/creativity
    "evera": "#ff6e40",         # orange — music/audio
    "justedit": "#40c4ff",      # blue — video
}


# ---------------------------------------------------------------------------
# Extension descriptor
# ---------------------------------------------------------------------------

class ExtensionInfo:
    """Metadata for a registered extension."""

    def __init__(self, name: str, display_name: str, icon: str,
                 description: str, color: str, remote_class: type,
                 module_path: str = ""):
        self.name = name
        self.display_name = display_name
        self.icon = icon
        self.description = description
        self.color = color
        self.remote_class = remote_class
        self.module_path = module_path


# ---------------------------------------------------------------------------
# Base remote control window
# ---------------------------------------------------------------------------

class ExtensionRemote:
    """Base class for extension remote control windows.

    Subclass and override _build_controls() to add extension-specific UI.
    """

    WINDOW_W = 480
    WINDOW_H = 560

    def __init__(self, parent: tk.Tk, ext_info: ExtensionInfo,
                 backend=None, on_close: Optional[Callable] = None):
        self.parent = parent
        self.ext_info = ext_info
        self.backend = backend
        self._on_close = on_close
        self._running = True

        self._build_window()

    def _build_window(self):
        self.win = tk.Toplevel(self.parent)
        self.win.title(f"{self.ext_info.icon} {self.ext_info.display_name}")
        self.win.configure(bg=BG)
        self.win.geometry(f"{self.WINDOW_W}x{self.WINDOW_H}")
        self.win.minsize(380, 400)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.attributes("-topmost", True)

        # Center on screen
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = (sw - self.WINDOW_W) // 2
        y = (sh - self.WINDOW_H) // 2
        self.win.geometry(f"+{x}+{y}")

        # Title bar
        title_frame = tk.Frame(self.win, bg=BG_PANEL, height=40)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)

        color = self.ext_info.color
        tk.Label(
            title_frame,
            text=f"  {self.ext_info.icon}  {self.ext_info.display_name}",
            bg=BG_PANEL, fg=color, font=("Consolas", 12, "bold"), anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=4)

        close_btn = tk.Label(
            title_frame, text=" ✕ ", bg=BG_PANEL, fg=ACCENT_DIM,
            font=("Consolas", 12), cursor="hand2",
        )
        close_btn.pack(side="right", padx=4)
        close_btn.bind("<Button-1>", lambda e: self.close())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=ERROR))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=ACCENT_DIM))

        tk.Frame(self.win, bg=BORDER, height=1).pack(fill="x")

        # Status bar (bottom)
        tk.Frame(self.win, bg=BORDER, height=1).pack(side="bottom", fill="x")
        self._status_frame = tk.Frame(self.win, bg=BG_SECTION, height=26)
        self._status_frame.pack(side="bottom", fill="x")
        self._status_frame.pack_propagate(False)
        self._status_label = tk.Label(
            self._status_frame, text="  Ready", bg=BG_SECTION, fg=TEXT_DIM,
            font=("Consolas", 8), anchor="w",
        )
        self._status_label.pack(side="left", fill="x", expand=True, padx=4)

        # Scrollable content area
        self._content_canvas = tk.Canvas(self.win, bg=BG, highlightthickness=0)
        self._content_scrollbar = tk.Scrollbar(
            self.win, orient="vertical", command=self._content_canvas.yview,
        )
        self._content = tk.Frame(self._content_canvas, bg=BG)
        self._content.bind(
            "<Configure>",
            lambda e: self._content_canvas.configure(
                scrollregion=self._content_canvas.bbox("all")),
        )
        self._content_canvas.create_window((0, 0), window=self._content, anchor="nw")
        self._content_canvas.configure(yscrollcommand=self._content_scrollbar.set)

        self._content_scrollbar.pack(side="right", fill="y")
        self._content_canvas.pack(fill="both", expand=True)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            self._content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._content_canvas.bind("<MouseWheel>", _on_mousewheel)
        self._content.bind("<MouseWheel>", _on_mousewheel)

        # Build extension-specific controls
        self._build_controls()

    def _build_controls(self):
        """Override in subclass to add extension-specific UI."""
        tk.Label(self._content, text="No controls configured.",
                 bg=BG, fg=TEXT_DIM, font=("Consolas", 10)).pack(pady=40)

    def set_status(self, text: str):
        try:
            self._status_label.configure(text=f"  {text}")
        except Exception:
            pass

    def close(self):
        self._running = False
        if self._on_close:
            self._on_close()
        try:
            self.win.destroy()
        except Exception:
            pass

    # -- Helpers for subclasses --

    def _section(self, title: str, icon: str = ""):
        """Add a section header to the content area."""
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill="x", padx=12, pady=(12, 4))
        tk.Label(frame, text=f"{icon}  {title}" if icon else title,
                 bg=BG, fg=self.ext_info.color,
                 font=("Consolas", 10, "bold"), anchor="w").pack(side="left")
        tk.Frame(self._content, bg=BORDER, height=1).pack(fill="x", padx=12)
        return frame

    def _action_btn(self, parent, text: str, command: Callable,
                    color: str = None, side: str = "left"):
        """Add a styled action button."""
        fg = color or self.ext_info.color
        btn = tk.Label(
            parent, text=f"  {text}  ", bg=BG_BTN, fg=fg,
            font=("Consolas", 9), cursor="hand2", pady=4,
        )
        btn.pack(side=side, padx=4, pady=4)
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.configure(bg=BG_BTN_HOVER))
        btn.bind("<Leave>", lambda e: btn.configure(bg=BG_BTN))
        return btn

    def _info_row(self, parent, label: str, value: str = "", value_fg: str = None):
        """Add an info row (label: value)."""
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=16, pady=2)
        tk.Label(row, text=label, bg=BG, fg=TEXT_DIM,
                 font=("Consolas", 8), anchor="w", width=16).pack(side="left")
        val_label = tk.Label(row, text=value, bg=BG, fg=value_fg or TEXT,
                             font=("Consolas", 9), anchor="w")
        val_label.pack(side="left", fill="x", expand=True)
        return val_label

    def _input_field(self, parent, label: str, default: str = "",
                     width: int = 30) -> tk.Entry:
        """Add a labeled input field."""
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=16, pady=3)
        tk.Label(row, text=label, bg=BG, fg=TEXT_DIM,
                 font=("Consolas", 8), anchor="w", width=14).pack(side="left")
        entry = tk.Entry(
            row, bg=BG_INPUT, fg=TEXT, font=("Consolas", 9),
            insertbackground=ACCENT, relief="flat", bd=1,
            highlightthickness=1, highlightcolor=ACCENT_DIM,
            highlightbackground=BORDER, width=width,
        )
        entry.pack(side="left", fill="x", expand=True, ipady=3)
        if default:
            entry.insert(0, default)
        return entry

    def _output_area(self, parent, height: int = 6) -> tk.Text:
        """Add a scrollable output text area."""
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill="x", padx=16, pady=4)
        text = tk.Text(
            frame, bg=BG_SECTION, fg=TEXT, font=("Consolas", 8),
            wrap="word", height=height, relief="flat", bd=0,
            insertbackground=ACCENT, state="disabled",
            highlightthickness=1, highlightcolor=ACCENT_DIM,
            highlightbackground=BORDER, padx=6, pady=4,
        )
        text.pack(fill="x", expand=True)
        return text

    def _append_output(self, text_widget: tk.Text, msg: str,
                       color: str = None):
        """Append text to an output area."""
        text_widget.configure(state="normal")
        text_widget.insert("end", msg + "\n")
        text_widget.configure(state="disabled")
        text_widget.see("end")

    def _run_async(self, func: Callable, status_msg: str = "Working..."):
        """Run a function in a background thread with status update."""
        self.set_status(status_msg)

        def _wrapper():
            try:
                func()
            except Exception as e:
                _log.error("Extension async error: %s", e)
                self.win.after(0, lambda: self.set_status(f"Error: {e}"))

        threading.Thread(target=_wrapper, daemon=True).start()


# ---------------------------------------------------------------------------
# SmartEngine Remote — Writing & Story Creation
# ---------------------------------------------------------------------------

class SmartEngineRemote(ExtensionRemote):
    """Remote control for SmartEngine — AI-powered story writing."""

    def _build_controls(self):
        self._client = None
        self._projects_data = []

        # -- Connection section --
        self._section("Connection", "🔌")
        conn_frame = tk.Frame(self._content, bg=BG)
        conn_frame.pack(fill="x", padx=12, pady=4)
        self._conn_status = self._info_row(conn_frame, "Status:", "Checking...", WARNING)
        btn_row = tk.Frame(self._content, bg=BG)
        btn_row.pack(fill="x", padx=12, pady=2)
        self._action_btn(btn_row, "▶ Start Server", self._start_server)
        self._action_btn(btn_row, "⟳ Refresh", self._check_connection)
        self._action_btn(btn_row, "■ Stop Server", self._stop_server, color=ERROR)

        # -- Projects section --
        self._section("Projects", "📚")
        proj_btn_row = tk.Frame(self._content, bg=BG)
        proj_btn_row.pack(fill="x", padx=12, pady=2)
        self._new_proj_name = self._input_field(self._content, "Project Name:", "My Story")
        proj_btn_row2 = tk.Frame(self._content, bg=BG)
        proj_btn_row2.pack(fill="x", padx=12, pady=2)
        self._action_btn(proj_btn_row2, "✚ Create Project", self._create_project)
        self._action_btn(proj_btn_row2, "⟳ List Projects", self._list_projects)
        self._projects_output = self._output_area(self._content, height=5)

        # -- Quick Pipeline section --
        self._section("Quick Pipeline", "⚡")
        tk.Label(self._content, text="  Generate a complete story from a single idea",
                 bg=BG, fg=TEXT_DIM, font=("Consolas", 8)).pack(anchor="w", padx=16)
        self._idea_input = self._input_field(self._content, "Story Idea:", "")
        pipeline_row = tk.Frame(self._content, bg=BG)
        pipeline_row.pack(fill="x", padx=12, pady=2)
        self._action_btn(pipeline_row, "🚀 Run Full Pipeline", self._run_pipeline)
        self._pipeline_output = self._output_area(self._content, height=8)

        # -- Auto-check connection --
        self.win.after(500, self._check_connection)

    def _get_client(self):
        if self._client is None:
            try:
                from apps.modules.smartengine import SmartEngineClient
                self._client = SmartEngineClient()
            except ImportError:
                self.set_status("SmartEngine module not found")
        return self._client

    def _check_connection(self):
        def _do():
            client = self._get_client()
            if client and client.is_running():
                self.win.after(0, lambda: self._conn_status.configure(
                    text="Connected", fg=SUCCESS))
                self.win.after(0, lambda: self.set_status("Connected to SmartEngine"))
            else:
                self.win.after(0, lambda: self._conn_status.configure(
                    text="Offline", fg=ERROR))
                self.win.after(0, lambda: self.set_status("SmartEngine not running"))
        self._run_async(_do, "Checking connection...")

    def _start_server(self):
        def _do():
            try:
                from apps.modules.smartengine import start_smartengine_server
                start_smartengine_server()
                time.sleep(3)
                self.win.after(0, self._check_connection)
            except Exception as e:
                self.win.after(0, lambda: self.set_status(f"Start failed: {e}"))
        self._run_async(_do, "Starting SmartEngine server...")

    def _stop_server(self):
        def _do():
            try:
                from apps.modules.smartengine import stop_smartengine_server
                stop_smartengine_server()
                time.sleep(1)
                self.win.after(0, self._check_connection)
            except Exception as e:
                self.win.after(0, lambda: self.set_status(f"Stop failed: {e}"))
        self._run_async(_do, "Stopping server...")

    def _create_project(self):
        name = self._new_proj_name.get().strip()
        if not name:
            self.set_status("Enter a project name")
            return

        def _do():
            client = self._get_client()
            if not client:
                return
            try:
                result = client.create_project(name)
                pid = result.get("id", "?")
                self.win.after(0, lambda: self._append_output(
                    self._projects_output, f"✅ Created: {name} (id: {pid})"))
                self.win.after(0, lambda: self.set_status(f"Project created: {name}"))
            except Exception as e:
                self.win.after(0, lambda: self._append_output(
                    self._projects_output, f"❌ Error: {e}"))
                self.win.after(0, lambda: self.set_status(f"Error: {e}"))
        self._run_async(_do, f"Creating project '{name}'...")

    def _list_projects(self):
        def _do():
            client = self._get_client()
            if not client:
                return
            try:
                projects = client.list_projects()
                self._projects_data = projects
                self.win.after(0, lambda: self._show_projects(projects))
            except Exception as e:
                self.win.after(0, lambda: self._append_output(
                    self._projects_output, f"❌ Error: {e}"))
        self._run_async(_do, "Loading projects...")

    def _show_projects(self, projects):
        self._projects_output.configure(state="normal")
        self._projects_output.delete("1.0", "end")
        if not projects:
            self._projects_output.insert("end", "No projects found.\n")
        else:
            for p in projects:
                name = p.get("name", "Untitled")
                pid = p.get("id", "?")[:8]
                status = p.get("status", "")
                self._projects_output.insert("end", f"  📖 {name}  ({pid}...)  {status}\n")
            self.set_status(f"{len(projects)} project(s) found")
        self._projects_output.configure(state="disabled")

    def _run_pipeline(self):
        idea = self._idea_input.get().strip()
        if not idea:
            self.set_status("Enter a story idea")
            return

        def _do():
            client = self._get_client()
            if not client:
                return
            self.win.after(0, lambda: self._append_output(
                self._pipeline_output, f"🚀 Starting pipeline: \"{idea[:50]}...\""))
            try:
                result = client.full_pipeline(idea)
                words = result.get("word_count", 0)
                chapters = result.get("chapter_count", 0)
                steps = result.get("steps", [])
                self.win.after(0, lambda: self._append_output(
                    self._pipeline_output,
                    f"✅ Complete! {chapters} chapters, {words} words\n"
                    f"   Steps: {' → '.join(steps)}"))
                self.win.after(0, lambda: self.set_status("Pipeline complete!"))
            except Exception as e:
                self.win.after(0, lambda: self._append_output(
                    self._pipeline_output, f"❌ Pipeline error: {e}"))
                self.win.after(0, lambda: self.set_status(f"Error: {e}"))
        self._run_async(_do, "Running full pipeline...")


# ---------------------------------------------------------------------------
# Evera Remote — Music Generation
# ---------------------------------------------------------------------------

class EveraRemote(ExtensionRemote):
    """Remote control for EVERA — AI music generation."""

    def _build_controls(self):
        self._module = None

        # -- Status section --
        self._section("Engine Status", "🔌")
        status_frame = tk.Frame(self._content, bg=BG)
        status_frame.pack(fill="x", padx=12, pady=4)
        self._engine_status = self._info_row(status_frame, "Engine:", "Not initialized", WARNING)
        btn_row = tk.Frame(self._content, bg=BG)
        btn_row.pack(fill="x", padx=12, pady=2)
        self._action_btn(btn_row, "▶ Initialize", self._init_engine)
        self._action_btn(btn_row, "⟳ Status", self._check_status)
        self._action_btn(btn_row, "■ Shutdown", self._shutdown, color=ERROR)

        # -- Generate Track section --
        self._section("Generate Track", "🎵")
        self._genre_input = self._input_field(self._content, "Genre:", "pop")
        self._mood_input = self._input_field(self._content, "Mood:", "upbeat")
        self._theme_input = self._input_field(self._content, "Theme:", "")

        gen_row = tk.Frame(self._content, bg=BG)
        gen_row.pack(fill="x", padx=12, pady=2)
        instrumental_var = tk.BooleanVar(value=False)
        tk.Checkbutton(gen_row, text="Instrumental", variable=instrumental_var,
                       bg=BG, fg=TEXT_DIM, selectcolor=BG_SECTION,
                       activebackground=BG, activeforeground=ACCENT,
                       font=("Consolas", 8)).pack(side="left", padx=16)
        self._instrumental_var = instrumental_var
        self._action_btn(gen_row, "🎶 Generate", self._generate_track, side="right")
        self._gen_output = self._output_area(self._content, height=4)

        # -- Artists section --
        self._section("Artists", "🎤")
        artist_row = tk.Frame(self._content, bg=BG)
        artist_row.pack(fill="x", padx=12, pady=2)
        self._action_btn(artist_row, "📋 List Artists", self._list_artists)
        self._artist_name = self._input_field(self._content, "New Artist:", "")
        create_row = tk.Frame(self._content, bg=BG)
        create_row.pack(fill="x", padx=12, pady=2)
        self._action_btn(create_row, "✚ Create Artist", self._create_artist)
        self._artists_output = self._output_area(self._content, height=4)

        # -- Tracks section --
        self._section("Library", "📀")
        tracks_row = tk.Frame(self._content, bg=BG)
        tracks_row.pack(fill="x", padx=12, pady=2)
        self._action_btn(tracks_row, "📋 List Tracks", self._list_tracks)
        self._action_btn(tracks_row, "🎸 Genres", self._list_genres)
        self._tracks_output = self._output_area(self._content, height=5)

    def _get_module(self):
        if self._module is None:
            try:
                from apps.modules.evera import EveraModule
                self._module = EveraModule()
            except ImportError:
                self.set_status("Evera module not found")
        return self._module

    def _init_engine(self):
        def _do():
            mod = self._get_module()
            if not mod:
                return
            try:
                result = mod.execute_action("evera_start")
                if result.get("ok"):
                    self.win.after(0, lambda: self._engine_status.configure(
                        text="Running", fg=SUCCESS))
                    self.win.after(0, lambda: self.set_status("Engine initialized"))
                else:
                    self.win.after(0, lambda: self._engine_status.configure(
                        text=f"Error: {result.get('error', '?')}", fg=ERROR))
            except Exception as e:
                self.win.after(0, lambda: self.set_status(f"Init failed: {e}"))
        self._run_async(_do, "Initializing EVERA engine...")

    def _check_status(self):
        def _do():
            mod = self._get_module()
            if not mod:
                return
            try:
                result = mod.execute_action("evera_status")
                if result.get("ok"):
                    status = result.get("status", {})
                    msg = f"Tracks: {status.get('total_tracks', '?')}, Artists: {status.get('total_artists', '?')}"
                    self.win.after(0, lambda: self._engine_status.configure(
                        text=msg, fg=SUCCESS))
                    self.win.after(0, lambda: self.set_status("Status retrieved"))
                else:
                    self.win.after(0, lambda: self._engine_status.configure(
                        text="Offline", fg=ERROR))
            except Exception as e:
                self.win.after(0, lambda: self._engine_status.configure(
                    text=f"Error", fg=ERROR))
        self._run_async(_do, "Checking status...")

    def _shutdown(self):
        def _do():
            mod = self._get_module()
            if not mod:
                return
            mod.execute_action("evera_stop")
            self.win.after(0, lambda: self._engine_status.configure(
                text="Stopped", fg=TEXT_DIM))
            self.win.after(0, lambda: self.set_status("Engine stopped"))
        self._run_async(_do, "Shutting down...")

    def _generate_track(self):
        genre = self._genre_input.get().strip() or "pop"
        mood = self._mood_input.get().strip()
        theme = self._theme_input.get().strip()
        instrumental = self._instrumental_var.get()

        def _do():
            mod = self._get_module()
            if not mod:
                return
            params = {"genre": genre, "instrumental": instrumental}
            if mood:
                params["mood"] = mood
            if theme:
                params["theme"] = theme
            self.win.after(0, lambda: self._append_output(
                self._gen_output, f"🎵 Generating {genre} track..."))
            try:
                result = mod.execute_action("evera_generate", params)
                if result.get("ok"):
                    data = result.get("data", {})
                    title = data.get("title", "Untitled")
                    path = data.get("local_copy", data.get("filepath", ""))
                    self.win.after(0, lambda: self._append_output(
                        self._gen_output, f"✅ {title}\n   {path}"))
                    self.win.after(0, lambda: self.set_status(f"Generated: {title}"))
                else:
                    self.win.after(0, lambda: self._append_output(
                        self._gen_output, f"❌ {result.get('error', 'Unknown error')}"))
            except Exception as e:
                self.win.after(0, lambda: self._append_output(
                    self._gen_output, f"❌ Error: {e}"))
        self._run_async(_do, f"Generating {genre} track...")

    def _list_artists(self):
        def _do():
            mod = self._get_module()
            if not mod:
                return
            try:
                result = mod.execute_action("evera_list_artists")
                artists = result.get("artists", [])
                self.win.after(0, lambda: self._show_artists(artists))
            except Exception as e:
                self.win.after(0, lambda: self._append_output(
                    self._artists_output, f"❌ {e}"))
        self._run_async(_do, "Loading artists...")

    def _show_artists(self, artists):
        self._artists_output.configure(state="normal")
        self._artists_output.delete("1.0", "end")
        if not artists:
            self._artists_output.insert("end", "No artists yet.\n")
        else:
            for a in artists[:20]:
                name = a.get("name", "Unknown")
                atype = a.get("artist_type", "")
                genres = ", ".join(a.get("genres", [])[:3])
                self._artists_output.insert("end", f"  🎤 {name}  ({atype})  {genres}\n")
            self.set_status(f"{len(artists)} artist(s)")
        self._artists_output.configure(state="disabled")

    def _create_artist(self):
        name = self._artist_name.get().strip()
        if not name:
            self.set_status("Enter an artist name")
            return

        def _do():
            mod = self._get_module()
            if not mod:
                return
            try:
                result = mod.execute_action("evera_create_artist", {"name": name})
                if result.get("ok"):
                    self.win.after(0, lambda: self._append_output(
                        self._artists_output, f"✅ Created artist: {name}"))
                    self.win.after(0, lambda: self.set_status(f"Artist created: {name}"))
                else:
                    self.win.after(0, lambda: self._append_output(
                        self._artists_output, f"❌ {result.get('error', '?')}"))
            except Exception as e:
                self.win.after(0, lambda: self._append_output(
                    self._artists_output, f"❌ {e}"))
        self._run_async(_do, f"Creating artist '{name}'...")

    def _list_tracks(self):
        def _do():
            mod = self._get_module()
            if not mod:
                return
            try:
                result = mod.execute_action("evera_list_tracks", {"limit": 20})
                tracks = result.get("tracks", [])
                self.win.after(0, lambda: self._show_tracks(tracks))
            except Exception as e:
                self.win.after(0, lambda: self._append_output(
                    self._tracks_output, f"❌ {e}"))
        self._run_async(_do, "Loading tracks...")

    def _show_tracks(self, tracks):
        self._tracks_output.configure(state="normal")
        self._tracks_output.delete("1.0", "end")
        if not tracks:
            self._tracks_output.insert("end", "No tracks in library.\n")
        else:
            for t in tracks[:20]:
                title = t.get("title", "Untitled")
                genre = t.get("genre", "?")
                dur = t.get("duration", 0)
                mins = int(dur) // 60
                secs = int(dur) % 60
                self._tracks_output.insert("end",
                    f"  📀 {title}  ({genre}, {mins}:{secs:02d})\n")
            self.set_status(f"{len(tracks)} track(s)")
        self._tracks_output.configure(state="disabled")

    def _list_genres(self):
        def _do():
            mod = self._get_module()
            if not mod:
                return
            try:
                result = mod.execute_action("evera_genres")
                genres = result.get("genres", [])
                self.win.after(0, lambda: self._show_genres(genres))
            except Exception as e:
                self.win.after(0, lambda: self._append_output(
                    self._tracks_output, f"❌ {e}"))
        self._run_async(_do, "Loading genres...")

    def _show_genres(self, genres):
        self._tracks_output.configure(state="normal")
        self._tracks_output.delete("1.0", "end")
        if isinstance(genres, list):
            for g in genres:
                if isinstance(g, dict):
                    self._tracks_output.insert("end", f"  🎸 {g.get('name', g)}\n")
                else:
                    self._tracks_output.insert("end", f"  🎸 {g}\n")
            self.set_status(f"{len(genres)} genres available")
        else:
            self._tracks_output.insert("end", f"  {genres}\n")
        self._tracks_output.configure(state="disabled")


# ---------------------------------------------------------------------------
# JustEdit Remote — Video Editing
# ---------------------------------------------------------------------------

class JustEditRemote(ExtensionRemote):
    """Remote control for JustEdit — browser-based video editor."""

    def _build_controls(self):
        self._server_running = False

        # -- Server section --
        self._section("Editor Server", "🔌")
        server_frame = tk.Frame(self._content, bg=BG)
        server_frame.pack(fill="x", padx=12, pady=4)
        self._server_status = self._info_row(server_frame, "Status:", "Stopped", TEXT_DIM)
        btn_row = tk.Frame(self._content, bg=BG)
        btn_row.pack(fill="x", padx=12, pady=2)
        self._action_btn(btn_row, "▶ Start Editor", self._start_editor)
        self._action_btn(btn_row, "■ Stop Editor", self._stop_editor, color=ERROR)
        self._action_btn(btn_row, "🌐 Open in Browser", self._open_browser)

        # -- New Project section --
        self._section("New Project", "🎬")
        self._proj_name = self._input_field(self._content, "Project Name:", "Onyx Edit")
        new_row = tk.Frame(self._content, bg=BG)
        new_row.pack(fill="x", padx=12, pady=2)
        self._action_btn(new_row, "✚ Create Empty", self._create_empty_project)

        # -- Import from Recordings section --
        self._section("Import Recordings", "📹")
        tk.Label(self._content,
                 text="  Auto-import Onyx screen recordings into a timeline",
                 bg=BG, fg=TEXT_DIM, font=("Consolas", 8)).pack(anchor="w", padx=16)
        import_row = tk.Frame(self._content, bg=BG)
        import_row.pack(fill="x", padx=12, pady=2)
        self._action_btn(import_row, "📂 Import All Recordings", self._import_recordings)
        self._action_btn(import_row, "📂 Import Latest 5", self._import_latest)
        self._import_output = self._output_area(self._content, height=5)

        # -- Quick Edits section --
        self._section("Quick Actions", "⚡")
        quick_row = tk.Frame(self._content, bg=BG)
        quick_row.pack(fill="x", padx=12, pady=2)
        self._action_btn(quick_row, "🎞️ Demo Highlight Reel", self._demo_reel)
        self._quick_output = self._output_area(self._content, height=4)

    def _start_editor(self):
        def _do():
            try:
                from apps.modules.justedit import start_justedit_server
                start_justedit_server()
                self._server_running = True
                self.win.after(0, lambda: self._server_status.configure(
                    text="Running (localhost:5173)", fg=SUCCESS))
                self.win.after(0, lambda: self.set_status("JustEdit server started"))
            except Exception as e:
                self.win.after(0, lambda: self.set_status(f"Start failed: {e}"))
        self._run_async(_do, "Starting JustEdit server...")

    def _stop_editor(self):
        def _do():
            try:
                from apps.modules.justedit import stop_justedit_server
                stop_justedit_server()
                self._server_running = False
                self.win.after(0, lambda: self._server_status.configure(
                    text="Stopped", fg=TEXT_DIM))
                self.win.after(0, lambda: self.set_status("Server stopped"))
            except Exception as e:
                self.win.after(0, lambda: self.set_status(f"Stop failed: {e}"))
        self._run_async(_do, "Stopping server...")

    def _open_browser(self):
        try:
            import webbrowser
            webbrowser.open("http://localhost:5173")
            self.set_status("Opened in browser")
        except Exception as e:
            self.set_status(f"Failed: {e}")

    def _create_empty_project(self):
        name = self._proj_name.get().strip() or "Onyx Edit"

        def _do():
            try:
                from apps.modules.justedit import JustEditProject
                proj = JustEditProject(name)
                proj.add_track("Video", "video")
                proj.add_track("Audio", "audio")
                proj.add_track("Titles", "text")
                out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                       "output")
                os.makedirs(out_dir, exist_ok=True)
                path = proj.save(os.path.join(out_dir, f"{name.lower().replace(' ', '_')}.justedit.json"))
                self.win.after(0, lambda: self._append_output(
                    self._import_output, f"✅ Created: {path}"))
                self.win.after(0, lambda: self.set_status(f"Project saved"))
            except Exception as e:
                self.win.after(0, lambda: self._append_output(
                    self._import_output, f"❌ {e}"))
        self._run_async(_do, f"Creating project '{name}'...")

    def _import_recordings(self, limit: int = 0):
        def _do():
            try:
                rec_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                       "data", "recordings")
                if not os.path.isdir(rec_dir):
                    self.win.after(0, lambda: self._append_output(
                        self._import_output, "No recordings directory found."))
                    return
                files = sorted([
                    os.path.join(rec_dir, f) for f in os.listdir(rec_dir)
                    if f.endswith(".mp4")
                ], key=os.path.getmtime, reverse=True)
                if limit > 0:
                    files = files[:limit]
                if not files:
                    self.win.after(0, lambda: self._append_output(
                        self._import_output, "No .mp4 recordings found."))
                    return

                from apps.modules.justedit import project_from_recordings
                proj = project_from_recordings(files, "Onyx Recordings")
                out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                       "output")
                os.makedirs(out_dir, exist_ok=True)
                path = proj.save(os.path.join(out_dir, "onyx_recordings.justedit.json"))
                self.win.after(0, lambda: self._append_output(
                    self._import_output,
                    f"✅ Imported {len(files)} recording(s)\n   Saved: {path}"))
                self.win.after(0, lambda: self.set_status(
                    f"Imported {len(files)} recordings"))
            except Exception as e:
                self.win.after(0, lambda: self._append_output(
                    self._import_output, f"❌ {e}"))
        self._run_async(_do, "Importing recordings...")

    def _import_latest(self):
        self._import_recordings(limit=5)

    def _demo_reel(self):
        def _do():
            try:
                rec_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                       "data", "recordings")
                files = sorted([
                    os.path.join(rec_dir, f) for f in os.listdir(rec_dir)
                    if f.endswith(".mp4") and "demo_" in f
                ], key=os.path.getmtime, reverse=True)
                if not files:
                    self.win.after(0, lambda: self._append_output(
                        self._quick_output, "No demo recordings found."))
                    return
                from apps.modules.justedit import project_from_recordings
                proj = project_from_recordings(files[:10], "Onyx Demo Reel")
                out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                       "output")
                os.makedirs(out_dir, exist_ok=True)
                path = proj.save(os.path.join(out_dir, "demo_reel.justedit.json"))
                self.win.after(0, lambda: self._append_output(
                    self._quick_output,
                    f"✅ Demo reel: {len(files[:10])} clips\n   {path}"))
                self.win.after(0, lambda: self.set_status("Demo reel created"))
            except Exception as e:
                self.win.after(0, lambda: self._append_output(
                    self._quick_output, f"❌ {e}"))
        self._run_async(_do, "Building demo reel...")


# ---------------------------------------------------------------------------
# Extension Registry
# ---------------------------------------------------------------------------

EXTENSION_REGISTRY: list[ExtensionInfo] = [
    ExtensionInfo(
        name="smartengine",
        display_name="SmartEngine",
        icon="📝",
        description="AI-powered story writing engine. Create books, scripts, and stories with discovery, architecture, and writing pipelines.",
        color=EXT_COLORS["smartengine"],
        remote_class=SmartEngineRemote,
        module_path="apps.modules.smartengine",
    ),
    ExtensionInfo(
        name="evera",
        display_name="EVERA",
        icon="🎵",
        description="AI music generation studio. Create songs, albums, and artist profiles with genre-aware composition.",
        color=EXT_COLORS["evera"],
        remote_class=EveraRemote,
        module_path="apps.modules.evera",
    ),
    ExtensionInfo(
        name="justedit",
        display_name="JustEdit",
        icon="🎬",
        description="Browser-based video editor. Import Onyx recordings, build timelines, add titles and effects.",
        color=EXT_COLORS["justedit"],
        remote_class=JustEditRemote,
        module_path="apps.modules.justedit",
    ),
]


def get_extension(name: str) -> Optional[ExtensionInfo]:
    """Get an extension by name."""
    for ext in EXTENSION_REGISTRY:
        if ext.name == name:
            return ext
    return None


def open_extension_remote(parent: tk.Tk, name: str, backend=None,
                          on_close: Optional[Callable] = None) -> Optional[ExtensionRemote]:
    """Open the remote control window for a named extension."""
    ext = get_extension(name)
    if not ext:
        _log.warning("Unknown extension: %s", name)
        return None
    return ext.remote_class(parent, ext, backend=backend, on_close=on_close)
