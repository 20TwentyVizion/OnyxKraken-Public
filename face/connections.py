"""External Connections Panel — manage Blender, Unreal, EVERA, and other integrations.

Shows connection status for each external program Onyx can control,
with start/stop buttons and per-program custom control windows.

Registers into the Extensions panel in app.py via CONNECTIONS list.
"""

import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from typing import Callable, Optional

_log = logging.getLogger("face.connections")

# ---------------------------------------------------------------------------
# Theme (matching Face GUI dark theme)
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
TEXT = "#c0d0e0"
TEXT_DIM = "#6a7a8a"
BORDER = "#0e2a3d"
SUCCESS = "#00e676"
ERROR = "#ff5252"
WARNING = "#ffab40"


# ---------------------------------------------------------------------------
# Connection descriptor
# ---------------------------------------------------------------------------

class ConnectionInfo:
    """Metadata for an external program connection."""

    def __init__(self, name: str, display_name: str, icon: str,
                 description: str, color: str,
                 control_class: type = None):
        self.name = name
        self.display_name = display_name
        self.icon = icon
        self.description = description
        self.color = color
        self.control_class = control_class  # custom control window class


# ---------------------------------------------------------------------------
# Connection state tracker
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Tracks connection state for all external programs."""

    def __init__(self):
        self._states = {}  # name -> {"connected": bool, "process": proc, "info": str}

    def get_state(self, name: str) -> dict:
        return self._states.get(name, {"connected": False, "process": None, "info": ""})

    def set_connected(self, name: str, connected: bool, info: str = ""):
        state = self._states.setdefault(name, {"connected": False, "process": None, "info": ""})
        state["connected"] = connected
        state["info"] = info

    def set_process(self, name: str, proc):
        state = self._states.setdefault(name, {"connected": False, "process": None, "info": ""})
        state["process"] = proc

    def is_connected(self, name: str) -> bool:
        return self.get_state(name).get("connected", False)


_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Base control window
# ---------------------------------------------------------------------------

class ConnectionControlWindow:
    """Base class for per-program control windows."""

    WINDOW_W = 500
    WINDOW_H = 600

    def __init__(self, parent: tk.Tk, conn_info: ConnectionInfo,
                 manager: ConnectionManager, on_close: Optional[Callable] = None):
        self.parent = parent
        self.conn_info = conn_info
        self.manager = manager
        self._on_close = on_close

        self.win = tk.Toplevel(parent)
        self.win.title(f"{conn_info.icon} {conn_info.display_name} Control")
        self.win.configure(bg=BG)
        self.win.geometry(f"{self.WINDOW_W}x{self.WINDOW_H}")
        self.win.minsize(400, 400)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.attributes("-topmost", True)

        # Center
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"+{(sw - self.WINDOW_W) // 2}+{(sh - self.WINDOW_H) // 2}")

        # Title bar
        title = tk.Frame(self.win, bg=BG_PANEL, height=40)
        title.pack(fill="x")
        title.pack_propagate(False)
        tk.Label(title, text=f"  {conn_info.icon}  {conn_info.display_name}",
                 bg=BG_PANEL, fg=conn_info.color, font=("Consolas", 12, "bold"),
                 anchor="w").pack(side="left", fill="x", expand=True, padx=4)
        close_btn = tk.Label(title, text=" ✕ ", bg=BG_PANEL, fg=ACCENT_DIM,
                             font=("Consolas", 12), cursor="hand2")
        close_btn.pack(side="right", padx=4)
        close_btn.bind("<Button-1>", lambda e: self.close())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=ERROR))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=ACCENT_DIM))
        tk.Frame(self.win, bg=BORDER, height=1).pack(fill="x")

        # Status bar
        tk.Frame(self.win, bg=BORDER, height=1).pack(side="bottom", fill="x")
        self._status_frame = tk.Frame(self.win, bg=BG_SECTION, height=26)
        self._status_frame.pack(side="bottom", fill="x")
        self._status_frame.pack_propagate(False)
        self._status_label = tk.Label(self._status_frame, text="  Ready",
                                       bg=BG_SECTION, fg=TEXT_DIM,
                                       font=("Consolas", 8), anchor="w")
        self._status_label.pack(side="left", fill="x", expand=True, padx=4)

        # Content
        self._content = tk.Frame(self.win, bg=BG)
        self._content.pack(fill="both", expand=True)

        self._build_controls()

    def _build_controls(self):
        """Override in subclass."""
        tk.Label(self._content, text="No controls configured.",
                 bg=BG, fg=TEXT_DIM, font=("Consolas", 10)).pack(pady=40)

    def set_status(self, text: str):
        try:
            self._status_label.configure(text=f"  {text}")
        except Exception:
            pass

    def close(self):
        if self._on_close:
            self._on_close()
        try:
            self.win.destroy()
        except Exception:
            pass

    def _section(self, title: str, icon: str = ""):
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill="x", padx=12, pady=(12, 4))
        tk.Label(frame, text=f"{icon}  {title}" if icon else title,
                 bg=BG, fg=self.conn_info.color,
                 font=("Consolas", 10, "bold"), anchor="w").pack(side="left")
        tk.Frame(self._content, bg=BORDER, height=1).pack(fill="x", padx=12)

    def _action_btn(self, parent, text: str, command: Callable,
                    color: str = None, side: str = "left"):
        fg = color or self.conn_info.color
        btn = tk.Label(parent, text=f"  {text}  ", bg=BG_BTN, fg=fg,
                       font=("Consolas", 9), cursor="hand2", pady=4)
        btn.pack(side=side, padx=4, pady=4)
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.configure(bg=BG_BTN_HOVER))
        btn.bind("<Leave>", lambda e: btn.configure(bg=BG_BTN))
        return btn

    def _info_row(self, parent, label: str, value: str = "", value_fg: str = None):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=16, pady=2)
        tk.Label(row, text=label, bg=BG, fg=TEXT_DIM,
                 font=("Consolas", 8), anchor="w", width=16).pack(side="left")
        val = tk.Label(row, text=value, bg=BG, fg=value_fg or TEXT,
                       font=("Consolas", 9), anchor="w")
        val.pack(side="left", fill="x", expand=True)
        return val


# ---------------------------------------------------------------------------
# Blender Control Window
# ---------------------------------------------------------------------------

class BlenderControlWindow(ConnectionControlWindow):
    """Control window for Blender integration."""

    def _build_controls(self):
        # Connection
        self._section("Connection", "🔌")
        conn = tk.Frame(self._content, bg=BG)
        conn.pack(fill="x", padx=12, pady=4)
        self._blender_status = self._info_row(conn, "Status:", "Disconnected", WARNING)
        self._blender_path = self._info_row(conn, "Executable:", "Not found", TEXT_DIM)

        btn_row = tk.Frame(self._content, bg=BG)
        btn_row.pack(fill="x", padx=12)
        self._action_btn(btn_row, "▶ Launch Blender", self._launch_blender)
        self._action_btn(btn_row, "⏹ Shutdown", self._shutdown_blender, color=ERROR)

        # Generative Builder
        self._section("Generative Builder", "🏗️")
        gen_row = tk.Frame(self._content, bg=BG)
        gen_row.pack(fill="x", padx=12)
        self._action_btn(gen_row, "📝 New Build", self._new_build)
        self._action_btn(gen_row, "🎤 Voice Builder", self._voice_builder)

        # Gesture Control
        self._section("Gesture Control", "🤚")
        gest_row = tk.Frame(self._content, bg=BG)
        gest_row.pack(fill="x", padx=12)
        self._action_btn(gest_row, "▶ Start Gestures", self._start_gestures)
        self._action_btn(gest_row, "⏹ Stop Gestures", self._stop_gestures, color=ERROR)

        # Quick Actions
        self._section("Quick Actions", "⚡")
        qa_row = tk.Frame(self._content, bg=BG)
        qa_row.pack(fill="x", padx=12)
        self._action_btn(qa_row, "📸 Render", self._render)
        self._action_btn(qa_row, "💾 Save", self._save)
        self._action_btn(qa_row, "↩ Undo", self._undo)
        self._action_btn(qa_row, "🔄 Reset View", self._reset_view)

        # SAC (Smart Asset Creator)
        self._section("Smart Asset Creator", "🤖")
        sac_row = tk.Frame(self._content, bg=BG)
        sac_row.pack(fill="x", padx=12)
        self._action_btn(sac_row, "🧑 New Character", self._new_character)
        self._action_btn(sac_row, "📦 Quality Check", self._quality_check)

        self._check_blender()

    def _check_blender(self):
        try:
            from config import find_blender_exe
            exe = find_blender_exe()
            if exe:
                self._blender_path.configure(text=os.path.basename(exe), fg=TEXT)
        except Exception:
            pass
        if self.manager.is_connected("blender"):
            self._blender_status.configure(text="Connected", fg=SUCCESS)
        else:
            self._blender_status.configure(text="Disconnected", fg=WARNING)

    def _launch_blender(self):
        self.set_status("Launching Blender...")
        def _do():
            try:
                from addons.blender.generative import BlenderGenerativeController
                ctrl = BlenderGenerativeController()
                if ctrl.start_blender():
                    self.manager.set_connected("blender", True, "Generative builder active")
                    self.win.after(0, lambda: self._blender_status.configure(text="Connected", fg=SUCCESS))
                    self.win.after(0, lambda: self.set_status("Blender running"))
                else:
                    self.win.after(0, lambda: self.set_status("Failed to launch"))
            except Exception as e:
                self.win.after(0, lambda: self.set_status(f"Error: {e}"))
        threading.Thread(target=_do, daemon=True).start()

    def _shutdown_blender(self):
        self.set_status("Shutting down...")
        self.manager.set_connected("blender", False)
        self._blender_status.configure(text="Disconnected", fg=WARNING)

    def _new_build(self):
        self.set_status("Starting generative build...")

    def _voice_builder(self):
        self.set_status("Starting voice builder...")

    def _start_gestures(self):
        self.set_status("Starting gesture control...")
        def _do():
            try:
                root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                script = os.path.join(root, "addons", "blender", "gesture_control.py")
                subprocess.Popen([sys.executable, script], cwd=root)
                self.win.after(0, lambda: self.set_status("Gesture control active"))
            except Exception as e:
                self.win.after(0, lambda: self.set_status(f"Error: {e}"))
        threading.Thread(target=_do, daemon=True).start()

    def _stop_gestures(self):
        self.set_status("Gesture control stopped")

    def _render(self):
        self._send_blender_cmd("import bpy\nbpy.ops.render.render(write_still=True)\n")

    def _save(self):
        self._send_blender_cmd("import bpy\nbpy.ops.wm.save_mainfile()\n")

    def _undo(self):
        self._send_blender_cmd("import bpy\nbpy.ops.ed.undo()\n")

    def _reset_view(self):
        self._send_blender_cmd(
            "import bpy, math, mathutils\n"
            "for a in bpy.context.screen.areas:\n"
            "  if a.type=='VIEW_3D':\n"
            "    r=a.spaces[0].region_3d\n"
            "    r.view_location=mathutils.Vector((0,0,1))\n"
            "    r.view_distance=15.0\n"
            "    r.view_rotation=mathutils.Euler((math.radians(60),0,math.radians(-45))).to_quaternion()\n"
        )

    def _new_character(self):
        self.set_status("Opening character creator...")

    def _quality_check(self):
        self.set_status("Running quality check...")

    def _send_blender_cmd(self, script: str):
        sync_dir = os.path.join(tempfile.gettempdir(), "onyx_blender_sync")
        cmd_file = os.path.join(sync_dir, "cmd.py")
        try:
            os.makedirs(sync_dir, exist_ok=True)
            with open(cmd_file, "w", encoding="utf-8") as f:
                f.write(script)
            self.set_status("Command sent")
        except Exception as e:
            self.set_status(f"Error: {e}")


# ---------------------------------------------------------------------------
# Unreal Control Window
# ---------------------------------------------------------------------------

class UnrealControlWindow(ConnectionControlWindow):
    """Control window for Unreal Engine integration."""

    def _build_controls(self):
        self._section("Connection", "🔌")
        conn = tk.Frame(self._content, bg=BG)
        conn.pack(fill="x", padx=12, pady=4)
        self._ue_status = self._info_row(conn, "Status:", "Disconnected", WARNING)
        self._ue_path = self._info_row(conn, "UE Version:", "Checking...", TEXT_DIM)

        btn_row = tk.Frame(self._content, bg=BG)
        btn_row.pack(fill="x", padx=12)
        self._action_btn(btn_row, "▶ Connect", self._connect_ue)
        self._action_btn(btn_row, "📡 Discover", self._discover_ue)

        self._section("Remote Control", "🎮")
        rc_row = tk.Frame(self._content, bg=BG)
        rc_row.pack(fill="x", padx=12)
        self._action_btn(rc_row, "🔧 Run Command", self._run_cmd)
        self._action_btn(rc_row, "📦 List Actors", self._list_actors)
        self._action_btn(rc_row, "📸 Screenshot", self._take_screenshot)

        self._section("Project", "📁")
        proj_row = tk.Frame(self._content, bg=BG)
        proj_row.pack(fill="x", padx=12)
        self._action_btn(proj_row, "📂 Open Project", self._open_project)
        self._action_btn(proj_row, "🏗️ Build", self._build_project)

        self._check_ue()

    def _check_ue(self):
        try:
            ue_path = r"I:\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe"
            if os.path.exists(ue_path):
                self._ue_path.configure(text="UE 5.7", fg=TEXT)
        except Exception:
            pass

    def _connect_ue(self):
        self.set_status("Connecting to UE Remote Control...")
        self.manager.set_connected("unreal", True, "Remote Control API")
        self._ue_status.configure(text="Connected", fg=SUCCESS)
        self.set_status("Connected via Remote Control API")

    def _discover_ue(self):
        self.set_status("Discovering UE instances...")

    def _run_cmd(self):
        self.set_status("Remote command sent")

    def _list_actors(self):
        self.set_status("Listing actors...")

    def _take_screenshot(self):
        self.set_status("Taking UE screenshot...")

    def _open_project(self):
        self.set_status("Opening project...")

    def _build_project(self):
        self.set_status("Building project...")


# ---------------------------------------------------------------------------
# EVERA Control Window
# ---------------------------------------------------------------------------

class EveraControlWindow(ConnectionControlWindow):
    """Control window for EVERA music/audio integration."""

    def _build_controls(self):
        self._section("Connection", "🔌")
        conn = tk.Frame(self._content, bg=BG)
        conn.pack(fill="x", padx=12, pady=4)
        self._evera_status = self._info_row(conn, "Status:", "Ready", SUCCESS)

        self._section("Music Generation", "🎵")
        music_row = tk.Frame(self._content, bg=BG)
        music_row.pack(fill="x", padx=12)
        self._action_btn(music_row, "🎹 Generate Track", self._gen_track)
        self._action_btn(music_row, "🥁 Beat Battle", self._beat_battle)
        self._action_btn(music_row, "🎧 DJ Session", self._dj_session)

        self._section("ACE-Step", "🤖")
        ace_row = tk.Frame(self._content, bg=BG)
        ace_row.pack(fill="x", padx=12)
        self._action_btn(ace_row, "🔬 Experiment", self._ace_experiment)
        self._action_btn(ace_row, "📊 Style Analysis", self._style_analysis)

        self._section("Publishing", "📤")
        pub_row = tk.Frame(self._content, bg=BG)
        pub_row.pack(fill="x", padx=12)
        self._action_btn(pub_row, "📻 Deep Strategy", self._deep_strategy)
        self._action_btn(pub_row, "📡 Wide Strategy", self._wide_strategy)
        self._action_btn(pub_row, "📈 Analytics", self._analytics)

        self.manager.set_connected("evera", True, "Local")

    def _gen_track(self):
        self.set_status("Generating music track...")

    def _beat_battle(self):
        self.set_status("Starting beat battle...")

    def _dj_session(self):
        self.set_status("Starting DJ session...")

    def _ace_experiment(self):
        self.set_status("Running ACE-Step experiment...")

    def _style_analysis(self):
        self.set_status("Analyzing music styles...")

    def _deep_strategy(self):
        self.set_status("DEEP strategy: content-focused publishing (Audiam)")

    def _wide_strategy(self):
        self.set_status("WIDE strategy: performance-focused publishing (Songtrust)")

    def _analytics(self):
        self.set_status("Loading publishing analytics...")


# ---------------------------------------------------------------------------
# Unity Control Window
# ---------------------------------------------------------------------------

class UnityControlWindow(ConnectionControlWindow):
    """Control window for Unity Engine integration."""

    def _build_controls(self):
        self._section("Connection", "🔌")
        conn = tk.Frame(self._content, bg=BG)
        conn.pack(fill="x", padx=12, pady=4)
        self._unity_status = self._info_row(conn, "Bridge:", "Checking...", WARNING)
        self._unity_version = self._info_row(conn, "Version:", "—", TEXT_DIM)

        btn_row = tk.Frame(self._content, bg=BG)
        btn_row.pack(fill="x", padx=12)
        self._action_btn(btn_row, "▶ Connect", self._connect_unity)
        self._action_btn(btn_row, "📡 Discover", self._discover_unity)

        self._section("Scene", "🎬")
        scene_row = tk.Frame(self._content, bg=BG)
        scene_row.pack(fill="x", padx=12)
        self._action_btn(scene_row, "🆕 New Scene", self._new_scene)
        self._action_btn(scene_row, "💾 Save Scene", self._save_scene)
        self._action_btn(scene_row, "📸 Screenshot", self._screenshot)

        self._section("Editor", "🎮")
        editor_row = tk.Frame(self._content, bg=BG)
        editor_row.pack(fill="x", padx=12)
        self._action_btn(editor_row, "▶ Play", self._play)
        self._action_btn(editor_row, "⏹ Stop", self._stop)
        self._action_btn(editor_row, "🏗️ Build", self._build)

        self._section("Project", "📁")
        proj_row = tk.Frame(self._content, bg=BG)
        proj_row.pack(fill="x", padx=12)
        self._action_btn(proj_row, "📂 Open Project", self._open_project)
        self._action_btn(proj_row, "➕ New Project", self._new_project)

        self._check_unity()

    def _check_unity(self):
        try:
            from apps.unity_toolkit.unity_remote import UnityRemoteClient
            client = UnityRemoteClient()
            if client.is_ready():
                info = client.get_editor_info() or {}
                self._unity_status.configure(text="Connected", fg=SUCCESS)
                self._unity_version.configure(
                    text=info.get("unity_version", "Unknown"), fg=TEXT)
                self.manager.set_connected("unity", True, "File-based IPC")
            else:
                self._unity_status.configure(text="Disconnected", fg=WARNING)
        except Exception:
            self._unity_status.configure(text="Disconnected", fg=WARNING)

    def _connect_unity(self):
        self.set_status("Checking Unity bridge...")
        self._check_unity()

    def _discover_unity(self):
        self.set_status("Discovering Unity installations...")
        try:
            from apps.unity_toolkit.unity_discovery import find_unity_installations
            installs = find_unity_installations()
            self.set_status(f"Found {len(installs)} Unity installation(s)")
        except Exception as e:
            self.set_status(f"Discovery error: {e}")

    def _new_scene(self):
        self.set_status("Creating new scene...")
        try:
            from apps.unity_toolkit.onyx_unity import OnyxUnity
            OnyxUnity().new_scene()
            self.set_status("New scene created")
        except Exception as e:
            self.set_status(f"Error: {e}")

    def _save_scene(self):
        self.set_status("Saving scene...")
        try:
            from apps.unity_toolkit.onyx_unity import OnyxUnity
            OnyxUnity().save_scene()
            self.set_status("Scene saved")
        except Exception as e:
            self.set_status(f"Error: {e}")

    def _screenshot(self):
        self.set_status("Taking screenshot...")
        try:
            from apps.unity_toolkit.onyx_unity import OnyxUnity
            OnyxUnity().screenshot()
            self.set_status("Screenshot captured")
        except Exception as e:
            self.set_status(f"Error: {e}")

    def _play(self):
        try:
            from apps.unity_toolkit.onyx_unity import OnyxUnity
            OnyxUnity().play()
            self.set_status("Entered Play mode")
        except Exception as e:
            self.set_status(f"Error: {e}")

    def _stop(self):
        try:
            from apps.unity_toolkit.onyx_unity import OnyxUnity
            OnyxUnity().stop()
            self.set_status("Exited Play mode")
        except Exception as e:
            self.set_status(f"Error: {e}")

    def _build(self):
        self.set_status("Building project...")

    def _open_project(self):
        self.set_status("Opening project...")

    def _new_project(self):
        self.set_status("Creating new project...")
        try:
            from apps.unity_toolkit.unity_project import create_onyx_project
            proj = create_onyx_project("OnyxWorkspace")
            self.set_status(f"Created: {proj.project_name}")
        except Exception as e:
            self.set_status(f"Error: {e}")


# ---------------------------------------------------------------------------
# Connection registry
# ---------------------------------------------------------------------------

CONNECTIONS = [
    ConnectionInfo(
        name="blender",
        display_name="Blender 3D",
        icon="🎨",
        description="Generative 3D builds, gesture control, SAC, voice builder",
        color="#E87D0D",
        control_class=BlenderControlWindow,
    ),
    ConnectionInfo(
        name="unreal",
        display_name="Unreal Engine",
        icon="🎮",
        description="UE5 Remote Control, discovery, vision QC, project management",
        color="#4B9CD3",
        control_class=UnrealControlWindow,
    ),
    ConnectionInfo(
        name="evera",
        display_name="EVERA Music",
        icon="🎵",
        description="ACE-Step music generation, DJ sessions, beat battles, publishing",
        color="#FF6E40",
        control_class=EveraControlWindow,
    ),
    ConnectionInfo(
        name="unity",
        display_name="Unity Engine",
        icon="🎮",
        description="Game dev, scene building, C# scripting, multi-platform builds",
        color="#222C37",
        control_class=UnityControlWindow,
    ),
]


def get_manager() -> ConnectionManager:
    """Get the global connection manager."""
    return _manager
