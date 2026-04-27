"""OnyxKraken Platform Abstraction — OS detection + capability checks.

Cross-platform helpers so core code never imports platform-specific
modules directly. Extensions register their availability here.
"""

import importlib
import logging
import os
import sys
from typing import Optional

_log = logging.getLogger("core.platform")

# ---------------------------------------------------------------------------
# OS detection
# ---------------------------------------------------------------------------

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

PLATFORM_NAME = "windows" if IS_WINDOWS else "mac" if IS_MAC else "linux"


# ---------------------------------------------------------------------------
# Common paths (cross-platform)
# ---------------------------------------------------------------------------

def home_dir() -> str:
    """User home directory — works on all platforms."""
    return os.path.expanduser("~")


def desktop_dir() -> str:
    """User desktop directory — works on all platforms."""
    return os.path.join(home_dir(), "Desktop")


def data_dir() -> str:
    """OnyxKraken data directory (next to this file's grandparent)."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


# ---------------------------------------------------------------------------
# Extension capability registry
# ---------------------------------------------------------------------------

_AVAILABLE_EXTENSIONS: dict[str, bool] = {}


def _probe_extension(name: str) -> bool:
    """Check if an extension's key dependency is importable."""
    probes = {
        "desktop": "pywinauto",
        "pyautogui": "pyautogui",
        "screenshots": "mss",
        "ssim": "skimage",
        "voice_stt": "sounddevice",
        "voice_tts_edge": "edge_tts",
        "voice_tts_system": "pyttsx3",
        "voice_playback": "pygame",
        "discord": "discord",
        "server": "fastapi",
        "knowledge_rag": "networkx",
        "vision_cv": "cv2",
        "audio_analysis": "librosa",
        "social_reddit": "praw",
        "mediapipe": "mediapipe",
    }
    module_name = probes.get(name)
    if module_name is None:
        return False
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def has_extension(name: str) -> bool:
    """Check if an extension's dependencies are available (cached)."""
    if name not in _AVAILABLE_EXTENSIONS:
        _AVAILABLE_EXTENSIONS[name] = _probe_extension(name)
    return _AVAILABLE_EXTENSIONS[name]


def has_desktop_automation() -> bool:
    """True if full desktop automation is available (Windows + pywinauto)."""
    return IS_WINDOWS and has_extension("desktop") and has_extension("pyautogui")


def available_extensions() -> dict[str, bool]:
    """Return a dict of all known extensions and their availability."""
    names = [
        "desktop", "pyautogui", "screenshots", "ssim",
        "voice_stt", "voice_tts_edge", "voice_tts_system", "voice_playback",
        "discord", "server", "knowledge_rag", "vision_cv",
        "audio_analysis", "social_reddit", "mediapipe",
    ]
    return {name: has_extension(name) for name in names}


# ---------------------------------------------------------------------------
# Blender executable discovery (cross-platform)
# ---------------------------------------------------------------------------

def find_blender_exe() -> str:
    """Locate the Blender executable on the current platform.

    Checks common install paths (newest first). Returns the first match,
    or the bare string ``"blender"`` hoping it is on PATH.
    """
    candidates: list[str] = []

    if IS_WINDOWS:
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        for ver in ["5.0", "4.2", "4.1", "4.0", "3.6", "3.4", "3.2", ""]:
            folder = f"Blender {ver}" if ver else "Blender"
            candidates.append(os.path.join(pf, "Blender Foundation", folder, "blender.exe"))
    elif IS_MAC:
        for ver in ["5.0", "4.2", "4.1", "4.0", "3.6"]:
            candidates.append(f"/Applications/Blender {ver}.app/Contents/MacOS/Blender")
        candidates.append("/Applications/Blender.app/Contents/MacOS/Blender")
    else:  # Linux
        candidates.extend([
            "/usr/bin/blender",
            "/snap/bin/blender",
            os.path.expanduser("~/blender/blender"),
        ])

    for path in candidates:
        if os.path.exists(path):
            return path
    return "blender"


# ---------------------------------------------------------------------------
# Window handle helper (cross-platform safe)
# ---------------------------------------------------------------------------

def get_window_handle(tk_root) -> Optional[int]:
    """Get the native window handle from a tkinter root, or None on failure."""
    try:
        tk_root.update_idletasks()
        if IS_WINDOWS:
            import ctypes
            frame_id = int(tk_root.winfo_id())
            hwnd = ctypes.windll.user32.GetParent(frame_id)
            return hwnd if hwnd else frame_id
        elif IS_MAC:
            # On Mac, winfo_id() returns an NSView pointer — not directly usable
            # but we return it for consistency; callers should check platform
            return int(tk_root.winfo_id())
        else:
            return int(tk_root.winfo_id())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Log platform info at import time
# ---------------------------------------------------------------------------

_log.info("Platform: %s (Python %s)", PLATFORM_NAME, sys.version.split()[0])
