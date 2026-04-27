"""Action Dispatch — registry-based action execution.

Replaces the monolithic if/elif chain with a clean dispatch pattern.
Each action handler is a function registered by name.

Usage:
    from agent.action_dispatch import execute_action

    result = execute_action(action, window=win, tree=tree, app_module=mod)
"""

import glob
import json
import os
import shlex
import subprocess
import tempfile
import time
from typing import Callable, Optional

from log import get_logger

_log = get_logger("dispatch")

try:
    from desktop.controller import (
        click_coords,
        click_element,
        find_window,
        get_accessibility_tree,
        press_key,
        scroll,
        type_text,
        type_text_direct,
    )
except (ImportError, RuntimeError):
    click_coords = click_element = find_window = None
    get_accessibility_tree = press_key = scroll = None
    type_text = type_text_direct = None
    _log.info("Desktop automation deps missing — action dispatch limited to non-desktop actions")


# ---------------------------------------------------------------------------
# WebVisionEngine — lazy singleton for vision-only modules
# ---------------------------------------------------------------------------

_web_vision_engine = None


def _get_web_vision_engine():
    """Lazy-load the WebVisionEngine singleton."""
    global _web_vision_engine
    if _web_vision_engine is None:
        try:
            from vision.web_vision_engine import WebVisionEngine
            _web_vision_engine = WebVisionEngine()
            _log.info("WebVisionEngine initialized for vision-only modules")
        except Exception as e:
            _log.warning("Could not initialize WebVisionEngine: %s", e)
    return _web_vision_engine


def _is_vision_only(app_module) -> bool:
    """Check if the app module requires vision-only interaction."""
    return app_module is not None and getattr(app_module, "vision_only", False)


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

_ACTION_HANDLERS: dict[str, Callable] = {}


def register_action(name: str):
    """Decorator to register an action handler function."""
    def decorator(fn):
        _ACTION_HANDLERS[name] = fn
        return fn
    return decorator


def get_registered_actions() -> list[str]:
    """Return list of all registered action names."""
    return list(_ACTION_HANDLERS.keys())


def execute_action(action: dict, window=None, tree=None, app_module=None) -> str:
    """Execute a validated action via the handler registry.

    Args:
        action: The parsed action dict.
        window: pywinauto window wrapper (optional).
        tree: Pre-fetched accessibility tree list (optional).
        app_module: App module instance (optional).
    """
    act = action["action"]
    handler = _ACTION_HANDLERS.get(act)
    if handler is None:
        return f"Unknown action: {act}"

    # Pre-action delay — modules can define human-like timing
    pre_delay = getattr(app_module, "pre_action_delay", None)
    if callable(pre_delay):
        pre_delay(act)

    result = handler(action, window=window, tree=tree, app_module=app_module)

    # Post-action delay — e.g. Reddit needs pauses after clicks/typing
    post_delay = getattr(app_module, "post_action_delay", None)
    if callable(post_delay):
        post_delay(act)

    return result


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _find_element_by_name(tree: list[dict], target: str) -> Optional[dict]:
    """Find an element in the accessibility tree by name or automation_id."""
    if not target or not target.strip():
        return None
    target_lower = target.lower()
    for el in tree:
        if target_lower in el["name"].lower() or target_lower in el["automation_id"].lower():
            return el
    return None


_PYWINAUTO_MODIFIERS = {"shift": "+", "ctrl": "^", "alt": "%"}
_PYWINAUTO_SPECIAL = {
    "enter": "{ENTER}", "return": "{ENTER}",
    "escape": "{ESC}", "esc": "{ESC}",
    "tab": "{TAB}", "space": " ",
    "delete": "{DELETE}", "del": "{DELETE}",
    "backspace": "{BACKSPACE}", "back": "{BACKSPACE}",
    "up": "{UP}", "down": "{DOWN}", "left": "{LEFT}", "right": "{RIGHT}",
    "home": "{HOME}", "end": "{END}",
    "pageup": "{PGUP}", "pagedown": "{PGDN}",
    "insert": "{INSERT}",
}


def _to_pywinauto_keys(key_combo: str) -> str:
    """Convert our key format ('shift+a', 'ctrl+s') to pywinauto type_keys format."""
    parts = [k.strip().lower() for k in key_combo.split("+")]
    result = ""
    for part in parts[:-1]:
        if part in _PYWINAUTO_MODIFIERS:
            result += _PYWINAUTO_MODIFIERS[part]
    main_key = parts[-1]
    if main_key.startswith("f") and main_key[1:].isdigit():
        result += "{" + main_key.upper() + "}"
    elif main_key in _PYWINAUTO_SPECIAL:
        result += _PYWINAUTO_SPECIAL[main_key]
    else:
        result += main_key
    return result


# Windows shell built-ins that need cmd /c wrapping
_CMD_BUILTINS = frozenset({
    "dir", "echo", "type", "copy", "move", "ren", "rename",
    "md", "mkdir", "rd", "rmdir", "cls", "set", "ver", "vol",
    "path", "assoc", "ftype", "mklink", "pushd", "popd",
})

# Blocked imports/operations in sandboxed Python execution
_PYTHON_BLOCKED = frozenset({
    "ctypes", "winreg", "subprocess", "shutil.rmtree",
    "socket", "http.server", "xmlrpc", "multiprocessing",
    "signal", "pty", "resource",
})


# ---------------------------------------------------------------------------
# Desktop interaction handlers
# ---------------------------------------------------------------------------

@register_action("click")
def _handle_click(action, window=None, tree=None, app_module=None, **_):
    target = action.get("target", "")
    fallback = action.get("fallback_coords", [0, 0])

    # Strategy 1: Accessibility tree (works for native apps)
    if window is not None:
        try:
            if tree is None:
                tree = get_accessibility_tree(window, max_depth=3)
            el = _find_element_by_name(tree, target)
            if el:
                click_element(el)
                return f"Clicked element '{el['name']}'"
        except Exception as e:
            _log.debug(f"Accessibility tree click failed: {e}")

    # Strategy 2: WebVisionEngine (for vision-only modules like Reddit, Twitter)
    # Uses OpenCV element detection + vision model identification for precise coords
    if _is_vision_only(app_module) and target:
        engine = _get_web_vision_engine()
        if engine:
            try:
                element_type = action.get("target_type", "")
                result = engine.find_and_click(
                    target,
                    element_type=element_type,
                    verify=True,
                    expected_change=f"screen should change after clicking '{target}'",
                )
                if result.ok:
                    cx, cy = result.coords
                    method = "vision_verified" if result.verified else "vision_unverified"
                    return f"Clicked '{target}' at ({cx}, {cy}) [{method}]"
                _log.info(f"WebVisionEngine could not find '{target}': {result.error}")
            except Exception as e:
                _log.warning(f"WebVisionEngine click failed: {e}")

    # Strategy 3: Raw fallback coordinates (LLM's coordinate guess — least reliable)
    if fallback and fallback != [0, 0]:
        click_coords(fallback[0], fallback[1])
        return f"Clicked coordinates ({fallback[0]}, {fallback[1]}) [fallback]"
    return "Could not find element to click and no valid fallback coords"


@register_action("type")
def _handle_type(action, window=None, tree=None, app_module=None, **_):
    target = action.get("target", "")
    params = action.get("params", {})
    text = params.get("text", "")

    if not text:
        return "No text specified to type"

    # Strategy 1: Accessibility tree focus (native apps)
    if window is not None:
        try:
            if not window.has_keyboard_focus():
                window.set_focus()
                time.sleep(0.1)
        except Exception as e:
            _log.debug(f"Could not set keyboard focus before typing: {e}")
    focused = False
    if target and window is not None:
        try:
            if tree is None:
                tree = get_accessibility_tree(window, max_depth=3)
            el = _find_element_by_name(tree, target)
            if el:
                click_element(el)
                time.sleep(0.15)
                focused = True
        except Exception as e:
            _log.debug(f"Could not focus target for typing: {e}")

    # Strategy 2: WebVisionEngine find-and-type (vision-only modules)
    if not focused and _is_vision_only(app_module) and target:
        engine = _get_web_vision_engine()
        if engine:
            try:
                result = engine.find_and_type(
                    target, text,
                    clear_first=False,
                    verify=True,
                )
                if result.ok:
                    method = "vision_verified" if result.verified else "vision_unverified"
                    return f"Typed into '{target}': {text[:50]}{'...' if len(text) > 50 else ''} [{method}]"
                _log.info(f"WebVisionEngine type failed for '{target}': {result.error}")
            except Exception as e:
                _log.warning(f"WebVisionEngine type failed: {e}")

    # Strategy 3: Fallback — focus window and type
    if not focused and window is not None:
        try:
            window.set_focus()
            time.sleep(0.15)
        except Exception as e:
            _log.debug(f"Fallback window focus failed: {e}")
    if app_module and getattr(app_module, "use_direct_typing", False):
        type_text_direct(text)
    else:
        type_text(text)
    return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"


@register_action("key_press")
def _handle_key_press(action, window=None, **_):
    params = action.get("params", {})
    key = params.get("key", "")

    if window is not None:
        try:
            if not window.has_keyboard_focus():
                window.set_focus()
                time.sleep(0.1)
        except Exception as e:
            _log.debug(f"Could not set keyboard focus before key_press: {e}")
    is_combo = "+" in key and len(key.split("+")) > 1
    if is_combo and window is not None:
        try:
            pwa_keys = _to_pywinauto_keys(key)
            window.type_keys(pwa_keys)
            return f"Pressed: {key}"
        except Exception as e:
            _log.debug(f"pywinauto type_keys failed ({e}), falling back to pyautogui")
    press_key(key)
    return f"Pressed: {key}"


@register_action("scroll")
def _handle_scroll(action, **_):
    params = action.get("params", {})
    clicks = params.get("clicks", -3)
    scroll(clicks)
    return f"Scrolled {clicks} clicks"


@register_action("launch_app")
def _handle_launch_app(action, **_):
    cmd = action.get("target", "")
    try:
        subprocess.Popen([cmd])
        return f"Launched: {cmd}"
    except Exception as e:
        return f"Failed to launch '{cmd}': {e}"


@register_action("wait")
def _handle_wait(action, **_):
    params = action.get("params", {})
    seconds = params.get("seconds", 2)
    time.sleep(seconds)
    return f"Waited {seconds}s"


@register_action("read_screen")
def _handle_read_screen(action, **_):
    params = action.get("params", {})
    summary = params.get("summary", "No summary provided")
    return f"Screen reading: {summary}"


@register_action("screenshot")
def _handle_screenshot(action, **_):
    return "Taking new screenshot for re-analysis"


# ---------------------------------------------------------------------------
# Filesystem / shell handlers
# ---------------------------------------------------------------------------

@register_action("run_command")
def _handle_run_command(action, **_):
    params = action.get("params", {})
    command = params.get("command", "")
    timeout = params.get("timeout", 10)
    if not command:
        return "No command specified"
    command = os.path.expandvars(command)
    blocked = ("format", "shutdown", "restart", "del /s", "del /q", "rm -rf",
               "rmdir /s", "rmdir /q", "reg delete", "bcdedit", "diskpart",
               "remove-item", "new-service", "set-executionpolicy",
               "taskkill", "net stop", "net user", "cipher /w",
               "schtasks", "wmic", "icacls", "takeown")
    cmd_lower = command.lower()
    if any(b in cmd_lower for b in blocked):
        return f"BLOCKED: dangerous command '{command}'"
    # Block direct shell invocations (cmd, powershell) to prevent escapes
    first_word = cmd_lower.split()[0].rstrip(".exe") if cmd_lower.split() else ""
    if first_word in ("cmd", "powershell", "pwsh", "wscript", "cscript", "mshta"):
        return f"BLOCKED: direct shell invocation '{first_word}' not allowed"
    if any(c in command for c in ("|", "&&", "||", ";", "`", "$(")):
        return f"BLOCKED: shell metacharacters not allowed in '{command}'"
    try:
        first_token = command.split()[0].lower().rstrip(".exe")
        if first_token in _CMD_BUILTINS:
            command = f"cmd /c {command}"
        cmd_parts = shlex.split(command, posix=False)
        result = subprocess.run(
            cmd_parts, capture_output=True, text=True,
            timeout=timeout, cwd=os.path.expanduser("~"),
        )
        output = result.stdout[:2000] if result.stdout else ""
        error = result.stderr[:500] if result.stderr else ""
        status = f"exit={result.returncode}"
        if output:
            return f"Command [{status}]: {output}"
        if error:
            return f"Command [{status}] stderr: {error}"
        return f"Command completed [{status}] (no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except Exception as e:
        return f"Command failed: {e}"


@register_action("read_file")
def _handle_read_file(action, **_):
    params = action.get("params", {})
    file_path = params.get("path", "")
    if not file_path:
        return "No file path specified"
    file_path = os.path.expandvars(os.path.expanduser(file_path))
    blocked_prefixes = ("C:\\Windows", "C:\\Program Files", "C:\\ProgramData")
    if any(file_path.startswith(p) for p in blocked_prefixes):
        return f"BLOCKED: cannot read system path '{file_path}'"
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(10000)
        lines = content.count("\n") + 1
        return f"File ({lines} lines, {len(content)} chars):\n{content}"
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        return f"Failed to read '{file_path}': {e}"


@register_action("write_file")
def _handle_write_file(action, **_):
    params = action.get("params", {})
    file_path = params.get("path", "")
    content = params.get("content", "")
    if not file_path:
        return "No file path specified"
    file_path = os.path.expandvars(os.path.expanduser(file_path))
    # Block system paths
    blocked_prefixes = ("C:\\Windows", "C:\\Program Files", "C:\\ProgramData",
                        "C:\\Users\\Default", "C:\\Recovery")
    if any(file_path.startswith(p) for p in blocked_prefixes):
        return f"BLOCKED: cannot write to system path '{file_path}'"
    # Only allow writes under known safe directories
    home = os.path.expanduser("~")
    safe_dirs = (
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "OnyxProjects"),
        os.path.join(home, "Downloads"),
    )
    norm = os.path.normpath(file_path)
    if not any(norm.startswith(os.path.normpath(d)) for d in safe_dirs):
        return f"BLOCKED: write_file only allowed under Desktop, Documents, OnyxProjects, or Downloads — got '{file_path}'"
    try:
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} chars to {file_path}"
    except Exception as e:
        return f"Failed to write '{file_path}': {e}"


@register_action("search_files")
def _handle_search_files(action, **_):
    params = action.get("params", {})
    directory = params.get("directory", "")
    pattern = params.get("pattern", "*")
    if not directory:
        return "No directory specified"
    directory = os.path.expandvars(os.path.expanduser(directory))
    if not os.path.isdir(directory):
        return f"Directory not found: {directory}"
    try:
        search_pattern = os.path.join(directory, "**", pattern)
        matches = glob.glob(search_pattern, recursive=True)[:50]
        if not matches:
            return f"No files matching '{pattern}' in {directory}"
        result_lines = [os.path.relpath(m, directory) for m in matches]
        return f"Found {len(matches)} files:\n" + "\n".join(result_lines)
    except Exception as e:
        return f"Search failed: {e}"


# ---------------------------------------------------------------------------
# Clipboard handlers
# ---------------------------------------------------------------------------

@register_action("copy_clipboard")
def _handle_copy_clipboard(action, **_):
    press_key("ctrl+c")
    time.sleep(0.3)
    try:
        import pyperclip
        text = pyperclip.paste()
        return f"Copied to clipboard: {text[:500]}" if text else "Clipboard is empty after copy"
    except Exception as e:
        return f"Copy attempted but couldn't read clipboard: {e}"


@register_action("paste_clipboard")
def _handle_paste_clipboard(action, **_):
    press_key("ctrl+v")
    time.sleep(0.3)
    return "Pasted from clipboard"


@register_action("get_clipboard")
def _handle_get_clipboard(action, **_):
    try:
        import pyperclip
        text = pyperclip.paste()
        return f"Clipboard contents: {text[:1000]}" if text else "Clipboard is empty"
    except Exception as e:
        return f"Failed to read clipboard: {e}"


@register_action("focus_window")
def _handle_focus_window(action, **_):
    params = action.get("params", {})
    target = action.get("target", "")
    window_title = params.get("title", target)
    if not window_title:
        return "No window title specified"
    try:
        win = find_window(window_title)
        if win:
            win.set_focus()
            time.sleep(0.3)
            return f"Focused window: {win.window_text()}"
        return f"Window not found: {window_title}"
    except Exception as e:
        return f"Failed to focus window '{window_title}': {e}"


# ---------------------------------------------------------------------------
# Python sandbox handler
# ---------------------------------------------------------------------------

@register_action("run_python")
def _handle_run_python(action, **_):
    params = action.get("params", {})
    code = params.get("code", "")
    timeout = params.get("timeout", 10)
    if not code:
        return "No code specified"
    code_lower = code.lower()
    for blocked in _PYTHON_BLOCKED:
        if blocked in code_lower:
            return f"BLOCKED: import/use of '{blocked}' not allowed in sandbox"
    if "os.system" in code_lower or "os.popen" in code_lower:
        return "BLOCKED: os.system/os.popen not allowed in sandbox"
    if "__import__" in code_lower or "exec(" in code_lower or "eval(" in code_lower:
        return "BLOCKED: dynamic code execution not allowed in sandbox"
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            script_path = f.name
        try:
            result = subprocess.run(
                ["python", script_path],
                capture_output=True, text=True,
                timeout=timeout,
                cwd=os.path.expanduser("~"),
            )
            output = result.stdout[:3000] if result.stdout else ""
            error = result.stderr[:1000] if result.stderr else ""
            status = f"exit={result.returncode}"
            parts = []
            if output:
                parts.append(f"Output:\n{output}")
            if error:
                parts.append(f"Stderr:\n{error}")
            if not parts:
                parts.append("(no output)")
            return f"Python [{status}]: " + "\n".join(parts)
        finally:
            try:
                os.remove(script_path)
            except Exception as e:
                _log.debug(f"Could not remove temp script {script_path}: {e}")
    except subprocess.TimeoutExpired:
        return f"Python script timed out after {timeout}s"
    except Exception as e:
        return f"Python execution failed: {e}"


# ---------------------------------------------------------------------------
# Window management
# ---------------------------------------------------------------------------

@register_action("close_window")
def _handle_close_window(action, window=None, **_):
    """Close a window by title or the current window."""
    params = action.get("params", {})
    target = action.get("target", "") or params.get("title", "")
    try:
        if target:
            win = find_window(target)
        else:
            win = window
        if win:
            title = win.window_text()
            win.close()
            time.sleep(0.5)
            return f"Closed window: {title}"
        return f"Window not found: {target or '(current)'}"
    except Exception as e:
        return f"Failed to close window: {e}"


# ---------------------------------------------------------------------------
# Self-built tool launching
# ---------------------------------------------------------------------------

@register_action("launch_tool")
def _handle_launch_tool(action, **_):
    """Launch one of Onyx's self-built tools."""
    params = action.get("params", {})
    tool_name = action.get("target", "") or params.get("name", "")
    if not tool_name:
        return "No tool name specified"
    try:
        from core.toolsmith import launch_tool, get_tool
        tool = get_tool(tool_name)
        if tool is None:
            return f"Tool not found: {tool_name}"
        proc = launch_tool(tool_name)
        if proc:
            return f"Launched self-built tool: {tool.display_name} (PID={proc.pid})"
        return f"Failed to launch tool: {tool_name}"
    except Exception as e:
        return f"Failed to launch tool '{tool_name}': {e}"


# ---------------------------------------------------------------------------
# Terminal actions
# ---------------------------------------------------------------------------

@register_action("done")
def _handle_done(action, **_):
    return f"Task complete: {action.get('params', {}).get('reason', '')}"


@register_action("fail")
def _handle_fail(action, **_):
    return f"Task failed: {action.get('params', {}).get('reason', '')}"


# ---------------------------------------------------------------------------
# Onyx Ecosystem — module-routed actions
# ---------------------------------------------------------------------------

# Lazy singletons for ecosystem modules
_ecosystem_modules: dict[str, object] = {}

_ECOSYSTEM_PREFIXES = {
    "blakvision_": "blakvision",
    "gamekree8r_": "gamekree8r",
    "worldbuild_": "worldbuild",
    "evera_": "evera",
    "justedit_": "justedit",
}


def _get_ecosystem_module(module_name: str):
    """Lazy-load an ecosystem module singleton."""
    if module_name in _ecosystem_modules:
        return _ecosystem_modules[module_name]
    try:
        from apps.registry import get_module
        mod = get_module(module_name)
        if mod and hasattr(mod, "execute_action"):
            _ecosystem_modules[module_name] = mod
            return mod
    except Exception as e:
        _log.warning("Could not load ecosystem module '%s': %s", module_name, e)
    return None


def _handle_ecosystem_action(action, **_):
    """Route ecosystem-prefixed actions to their module's execute_action()."""
    act = action["action"]
    params = action.get("params", {})

    for prefix, module_name in _ECOSYSTEM_PREFIXES.items():
        if act.startswith(prefix):
            mod = _get_ecosystem_module(module_name)
            if mod is None:
                return f"Ecosystem module '{module_name}' not available. Is the service running?"
            try:
                result = mod.execute_action(act, params)
                if isinstance(result, dict):
                    if result.get("ok"):
                        # Compact summary for the LLM
                        msg = result.get("message", "")
                        data_keys = [k for k in result if k not in ("ok", "message", "error")]
                        summary = msg or f"{act} completed. Keys: {', '.join(data_keys)}"
                        return summary
                    else:
                        return f"{act} failed: {result.get('error', 'unknown error')}"
                return str(result)
            except Exception as e:
                _log.error("Ecosystem action %s failed: %s", act, e, exc_info=True)
                return f"{act} error: {e}"

    return f"No ecosystem module found for action: {act}"


# Register all known ecosystem action names so they appear in get_registered_actions()
_ECOSYSTEM_ACTIONS = [
    # BlakVision
    "blakvision_generate", "blakvision_img2img", "blakvision_inpaint",
    "blakvision_upscale", "blakvision_enhance_prompt", "blakvision_critique",
    "blakvision_status", "blakvision_gallery", "blakvision_load_model",
    # GameKree8r
    "gamekree8r_new_game", "gamekree8r_start", "gamekree8r_stop",
    "gamekree8r_pause", "gamekree8r_resume", "gamekree8r_status",
    "gamekree8r_games", "gamekree8r_metrics", "gamekree8r_feedback",
    "gamekree8r_activity",
    # WorldBuild
    "worldbuild_outline", "worldbuild_chapter", "worldbuild_book",
    "worldbuild_world", "worldbuild_character", "worldbuild_script",
    "worldbuild_article", "worldbuild_copy", "worldbuild_projects",
    "worldbuild_read",
]

for _act_name in _ECOSYSTEM_ACTIONS:
    _ACTION_HANDLERS[_act_name] = _handle_ecosystem_action
