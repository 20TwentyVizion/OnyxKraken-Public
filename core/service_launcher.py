"""Service Launcher — Onyx's ability to autonomously start its own engines.

Provides a unified API to ensure any required service is running before
a workflow or Hand begins. If a service is not running, Onyx will
attempt to start it automatically.

Supported services:
  - Ollama (LLM inference)
  - ACE-Step (AI music generation)
  - JustEdit (video editor dev server)
  - Blender (3D modeling — process launch)
  - ffmpeg (media tool — PATH check only, cannot auto-start)

Usage:
    from core.service_launcher import ensure_services, ensure_service

    # Ensure multiple services are ready (auto-starts what's missing)
    ok, failures = ensure_services(["Ollama", "ACE-Step", "JustEdit"])

    # Ensure a single service
    ok, msg = ensure_service("ACE-Step")

CLI:
    python -m core.service_launcher Ollama ACE-Step JustEdit
    python -m core.service_launcher --all
"""

import logging
import os
import shutil
import socket
import subprocess
import time
from typing import Optional

_log = logging.getLogger("core.service_launcher")


# ---------------------------------------------------------------------------
# Port / health helpers
# ---------------------------------------------------------------------------

def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError):
        return False


def _http_ok(url: str, timeout: float = 3.0) -> bool:
    try:
        import urllib.request
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Individual service launchers
# ---------------------------------------------------------------------------

def _is_ollama_running() -> bool:
    return _port_open(11434)


def _start_ollama(timeout: float = 30.0) -> tuple[bool, str]:
    """Start Ollama if not already running."""
    if _is_ollama_running():
        return True, "Ollama already running"

    _log.info("Auto-starting Ollama...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    except FileNotFoundError:
        return False, "Ollama not found on PATH"
    except Exception as exc:
        return False, f"Failed to start Ollama: {exc}"

    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_ollama_running():
            _log.info("Ollama is ready")
            return True, "Ollama started successfully"
        time.sleep(1.0)

    return False, f"Ollama did not start within {timeout:.0f}s"


def _is_acestep_running() -> bool:
    # ACE-Step can be on port 8001 (evera_service) or 7860 (Gradio default)
    return _port_open(8001) or _port_open(7860)


def _start_acestep(timeout: float = 180.0) -> tuple[bool, str]:
    """Start ACE-Step music generation server via EVERA service manager."""
    if _is_acestep_running():
        return True, "ACE-Step already running"

    _log.info("Auto-starting ACE-Step (this takes ~90-120s for model loading)...")

    # Use the existing EVERA service manager which handles VRAM,
    # model loading, Ollama unloading, and log management
    try:
        from apps.evera_service import ensure_evera
        ok = ensure_evera(
            need_lyrics=False,  # Don't start Ollama — just ACE-Step
            acestep_model="acestep-v15-sft",
            timeout_ace=timeout,
        )
        if ok:
            _log.info("ACE-Step ready via EVERA service manager")
            return True, "ACE-Step started successfully"
        else:
            return False, "ACE-Step failed to start (ensure_evera returned False)"
    except ImportError:
        return False, "EVERA service module not found (apps/evera_service.py)"
    except Exception as exc:
        return False, f"ACE-Step start failed: {exc}"


def _is_justedit_running() -> bool:
    return _port_open(5173)


def _start_justedit(timeout: float = 15.0) -> tuple[bool, str]:
    """Start JustEdit Vite dev server."""
    if _is_justedit_running():
        return True, "JustEdit already running"

    _log.info("Auto-starting JustEdit dev server...")
    try:
        from apps.modules.justedit import justedit
        ok = justedit.start_server()
        if ok:
            _log.info("JustEdit server started")
            return True, "JustEdit started successfully"
        return False, "JustEdit server failed to start"
    except ImportError:
        # Fallback: try direct npm launch
        try:
            justedit_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "tools", "JustEdit"
            )
            # Also check ecosystem location
            from config.paths import ECOSYSTEM_ROOT
            ecosystem_justedit = ECOSYSTEM_ROOT / "03_TOOLS" / "JustEdit"
            
            candidates = [
                justedit_path,
                str(ecosystem_justedit),
            ]
            for path in candidates:
                if os.path.isdir(path) and os.path.isfile(os.path.join(path, "package.json")):
                    # Use npm.cmd on Windows (npm is a .cmd wrapper)
                    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
                    subprocess.Popen(
                        [npm_cmd, "run", "dev"],
                        cwd=path,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    deadline = time.time() + timeout
                    while time.time() < deadline:
                        if _is_justedit_running():
                            return True, "JustEdit started via npm"
                        time.sleep(1.0)
                    return False, f"JustEdit npm dev did not start within {timeout:.0f}s"
            return False, "JustEdit project directory not found"
        except Exception as exc:
            return False, f"JustEdit start failed: {exc}"
    except Exception as exc:
        return False, f"JustEdit start failed: {exc}"


def _is_blender_running() -> bool:
    try:
        import psutil
        for proc in psutil.process_iter(["name"]):
            if proc.info["name"] and "blender" in proc.info["name"].lower():
                return True
    except ImportError:
        # Fallback: tasklist
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq blender.exe"],
                capture_output=True, text=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if "blender.exe" in result.stdout.lower():
                return True
        except Exception:
            pass
    except Exception:
        pass
    return False


def _start_blender(timeout: float = 15.0) -> tuple[bool, str]:
    """Start Blender."""
    if _is_blender_running():
        return True, "Blender already running"

    _log.info("Auto-starting Blender...")
    try:
        from config import find_blender_exe
        exe = find_blender_exe()
        subprocess.Popen(
            [exe],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            if _is_blender_running():
                _log.info("Blender is running")
                return True, "Blender started successfully"
            time.sleep(1.0)
        return False, f"Blender did not start within {timeout:.0f}s"
    except Exception as exc:
        return False, f"Blender start failed: {exc}"


def _is_ffmpeg_available() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode == 0
    except Exception:
        return False


def _ensure_ffmpeg() -> tuple[bool, str]:
    """ffmpeg can't be auto-started — just check if it's on PATH."""
    if _is_ffmpeg_available():
        return True, "ffmpeg available on PATH"
    return False, "ffmpeg not found on PATH — install from https://ffmpeg.org"


# ---------------------------------------------------------------------------
# Service registry
# ---------------------------------------------------------------------------

# Canonical name -> (is_running_fn, start_fn)
_SERVICE_REGISTRY: dict[str, tuple] = {
    "ollama":   (_is_ollama_running,   _start_ollama),
    "ace-step": (_is_acestep_running,  _start_acestep),
    "acestep":  (_is_acestep_running,  _start_acestep),
    "justedit": (_is_justedit_running, _start_justedit),
    "blender":  (_is_blender_running,  _start_blender),
    "ffmpeg":   (_is_ffmpeg_available, _ensure_ffmpeg),
}


def _normalize_name(name: str) -> str:
    """Normalize service name for lookup."""
    return name.strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def _lookup(name: str) -> tuple:
    """Find service entry by name (fuzzy match)."""
    low = name.strip().lower()
    # Direct lookup
    if low in _SERVICE_REGISTRY:
        return _SERVICE_REGISTRY[low]
    # Fuzzy
    norm = _normalize_name(name)
    for key, val in _SERVICE_REGISTRY.items():
        if _normalize_name(key) == norm:
            return val
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_service_running(name: str) -> bool:
    """Check if a service is currently running (no auto-start)."""
    entry = _lookup(name)
    if entry is None:
        _log.warning("Unknown service: %s", name)
        return False
    is_running_fn, _ = entry
    return is_running_fn()


def ensure_service(name: str) -> tuple[bool, str]:
    """Ensure a single service is running. Auto-starts if needed.

    Returns (success, message).
    """
    entry = _lookup(name)
    if entry is None:
        return False, f"Unknown service: {name}"

    is_running_fn, start_fn = entry

    # Already running?
    if is_running_fn():
        return True, f"{name} already running"

    # Auto-start
    _log.info("Service '%s' not running — attempting auto-start...", name)
    ok, msg = start_fn()
    return ok, msg


def ensure_services(names: list[str]) -> tuple[bool, list[str]]:
    """Ensure multiple services are running. Auto-starts what's missing.

    Returns (all_ok, list_of_failure_messages).
    """
    failures = []
    for name in names:
        ok, msg = ensure_service(name)
        if not ok:
            failures.append(f"{name}: {msg}")
            _log.error("Failed to ensure service '%s': %s", name, msg)
        else:
            _log.info("Service '%s': %s", name, msg)

    all_ok = len(failures) == 0
    return all_ok, failures


def get_service_status() -> dict[str, bool]:
    """Get running status of all known services (no auto-start)."""
    status = {}
    seen = set()
    for key, (is_running_fn, _) in _SERVICE_REGISTRY.items():
        # Avoid duplicate checks for aliases
        fn_id = id(is_running_fn)
        if fn_id in seen:
            continue
        seen.add(fn_id)
        status[key] = is_running_fn()
    return status


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    args = sys.argv[1:]
    if not args or "--help" in args:
        print("Usage: python -m core.service_launcher [service ...] [--all] [--check]")
        print("  Services: Ollama, ACE-Step, JustEdit, Blender, ffmpeg")
        print("  --all     Ensure all services are ready")
        print("  --check   Check status only (no auto-start)")
        sys.exit(0)

    if "--check" in args:
        print("Service Status:")
        for name, running in get_service_status().items():
            dot = "\u25cf" if running else "\u25cb"
            print(f"  {dot} {name}: {'RUNNING' if running else 'STOPPED'}")
        sys.exit(0)

    if "--all" in args:
        names = ["Ollama", "ACE-Step", "JustEdit", "Blender", "ffmpeg"]
    else:
        names = args

    print(f"Ensuring services: {', '.join(names)}")
    all_ok, failures = ensure_services(names)

    if all_ok:
        print("\n\u2713 All services ready!")
    else:
        print(f"\n\u2717 {len(failures)} service(s) failed:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
