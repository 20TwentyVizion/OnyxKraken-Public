"""Action schema, parser, validator, and safety checker."""

import json
import logging
import re
from typing import Optional

import config

_log = logging.getLogger("agent.actions")

# ---------------------------------------------------------------------------
# Valid action types
# ---------------------------------------------------------------------------
VALID_ACTIONS = {
    "click",        # click an element by name or coords
    "type",         # type text into the focused element
    "scroll",       # scroll up or down
    "key_press",    # press a key combo (e.g. "ctrl+s")
    "launch_app",   # launch an application by name or command
    "read_screen",  # analyze/read visible screen content and report findings
    "wait",         # wait for a duration
    "screenshot",   # take a new screenshot and re-analyze
    "run_command",  # execute a terminal/shell command
    "read_file",    # read contents of a file
    "write_file",   # write/create a file
    "search_files",    # search for files by name or content
    "copy_clipboard",  # select + copy to clipboard (Ctrl+C)
    "paste_clipboard", # paste from clipboard (Ctrl+V)
    "get_clipboard",   # read current clipboard contents
    "focus_window",    # bring a specific window to the foreground
    "run_python",      # execute a Python script in a sandbox
    "blender_python",  # execute a bpy script inside Blender's Python interpreter
    "blender_query",   # query Blender scene state via bpy script (returns structured data)
    "done",            # task is complete
    "fail",            # task cannot be completed
}

# ---------------------------------------------------------------------------
# Action schema
# ---------------------------------------------------------------------------
ACTION_SCHEMA_DESCRIPTION = """\
Respond with ONLY a JSON object. No markdown, no explanation, no extra text.

Actions: click, type, key_press, scroll, launch_app, read_screen, wait, screenshot, run_command, read_file, write_file, search_files, copy_clipboard, paste_clipboard, get_clipboard, focus_window, run_python, blender_python, blender_query, done, fail

Example — click a button:
{"thought": "I need to click File menu", "action": "click", "target": "File", "target_type": "MenuItem", "fallback_coords": [30, 12], "params": {}}

Example — type text:
{"thought": "Typing hello", "action": "type", "target": "Text Editor", "target_type": "Edit", "fallback_coords": [400, 300], "params": {"text": "Hello World"}}

Example — launch an app:
{"thought": "Need to open Notepad", "action": "launch_app", "target": "notepad.exe", "target_type": "", "fallback_coords": [0, 0], "params": {}}

Example — press keys:
{"thought": "Save the file", "action": "key_press", "target": "", "target_type": "", "fallback_coords": [0, 0], "params": {"key": "ctrl+s"}}

Example — read what's on screen:
{"thought": "I need to read Grok's response", "action": "read_screen", "target": "", "target_type": "", "fallback_coords": [0, 0], "params": {"summary": "Grok responded with a list of 4 points about the meaning of life. The down arrow is visible so there is more text below."}}

Example — done:
{"thought": "Task is complete", "action": "done", "target": "", "target_type": "", "fallback_coords": [0, 0], "params": {"reason": "Successfully typed text"}}

Example — run a terminal command (shell built-ins like dir, echo, type are auto-wrapped with cmd /c):
{"thought": "List files on Desktop", "action": "run_command", "target": "", "target_type": "", "fallback_coords": [0, 0], "params": {"command": "dir C:\\Users\\pyrav\\Desktop", "timeout": 10}}

Example — read a file:
{"thought": "Read the config file", "action": "read_file", "target": "", "target_type": "", "fallback_coords": [0, 0], "params": {"path": "C:\\Users\\pyrav\\Desktop\\notes.txt"}}

Example — write a file:
{"thought": "Save response to file", "action": "write_file", "target": "", "target_type": "", "fallback_coords": [0, 0], "params": {"path": "C:\\Users\\pyrav\\Desktop\\output.txt", "content": "Hello World"}}

Example — search for files:
{"thought": "Find Python files", "action": "search_files", "target": "", "target_type": "", "fallback_coords": [0, 0], "params": {"directory": "C:\\Users\\pyrav\\Documents", "pattern": "*.py"}}

Example — copy selected text to clipboard:
{"thought": "Copy the selected text", "action": "copy_clipboard", "target": "", "target_type": "", "fallback_coords": [0, 0], "params": {}}

Example — paste from clipboard:
{"thought": "Paste text into editor", "action": "paste_clipboard", "target": "", "target_type": "", "fallback_coords": [0, 0], "params": {}}

Example — switch to another window:
{"thought": "Switch to Notepad", "action": "focus_window", "target": "Notepad", "target_type": "", "fallback_coords": [0, 0], "params": {"title": "Notepad"}}

Example — run a Python script (for computation, data processing, etc.):
{"thought": "Calculate the result", "action": "run_python", "target": "", "target_type": "", "fallback_coords": [0, 0], "params": {"code": "import math\nresult = math.factorial(10)\nprint(f'10! = {result}')", "timeout": 10}}

Example — run a Blender Python (bpy) script to create/modify 3D objects (onyx_bpy is auto-imported):
{"thought": "Build a simple house", "action": "blender_python", "target": "", "target_type": "", "fallback_coords": [0, 0], "params": {"code": "from onyx_bpy import *\nresult = build_simple_house(width=8, depth=10, roof_style='gable')\nrender_preview()", "save_after": true, "verify_after": true, "goal": "Build a house with walls, roof, windows, door", "timeout": 60}}

Example — build in open Blender (live mode, user watches objects appear):
{"thought": "Build house in live mode", "action": "blender_python", "target": "", "target_type": "", "fallback_coords": [0, 0], "params": {"code": "from onyx_bpy import *\nclear_scene()\nsetup_scene()\nbuild_simple_house(width=8, depth=10)\nrender_preview()", "live_mode": true, "timeout": 120}}

Example — query Blender scene state (list objects, get dimensions, etc.):
{"thought": "Check what objects exist in the scene", "action": "blender_query", "target": "", "target_type": "", "fallback_coords": [0, 0], "params": {"code": "import bpy\nfor obj in bpy.data.objects:\n    print(f'{obj.name}: type={obj.type}, loc={tuple(round(v,2) for v in obj.location)}, dim={tuple(round(v,2) for v in obj.dimensions)}')", "blend_file": ""}}

Param rules: type needs {"text": "..."}, key_press needs {"key": "..."}, scroll needs {"clicks": -3}, wait needs {"seconds": 2}, done/fail need {"reason": "..."}, read_screen needs {"summary": "what you see on screen"}, run_command needs {"command": "...", "timeout": 10}, read_file needs {"path": "..."}, write_file needs {"path": "...", "content": "..."}, search_files needs {"directory": "...", "pattern": "..."}, focus_window needs {"title": "..."}, run_python needs {"code": "...", "timeout": 10}, blender_python needs {"code": "...(bpy script)", "blend_file": "(optional .blend path)", "save_after": true/false, "verify_after": true/false, "goal": "(description for visual check)", "live_mode": true/false, "timeout": 60}, blender_query needs {"code": "...(bpy query script)", "blend_file": "(optional .blend path)"}. copy_clipboard/paste_clipboard/get_clipboard need no params.
Use element names from the accessibility tree in "target" when available.
"""


def _repair_json(s: str) -> str:
    """Attempt common fixes on malformed JSON from LLMs."""
    # Fix 1: trailing comma inside string before next key
    #   '," "action"  →  '", "action"
    s = re.sub(r'(\w[?!.\'\"]*),"\s+"', r'\1", "', s)

    # Fix 2: missing comma between key-value pairs
    #   "value" "key"  →  "value", "key"
    s = re.sub(r'"\s+"(?=[a-z_])', '", "', s)

    # Fix 3: single quotes used instead of double quotes (for keys/values)
    #   {'thought': 'hello'}  →  {"thought": "hello"}
    # Only do this if no double quotes are present (avoid breaking mixed strings)
    if '"' not in s:
        s = s.replace("'", '"')

    # Fix 4: trailing comma before closing brace
    s = re.sub(r',\s*}', '}', s)

    # Fix 5: trailing comma before closing bracket
    s = re.sub(r',\s*]', ']', s)

    # Fix 6: escape unescaped backslashes in Windows paths
    # LLMs write C:\Users\... instead of C:\\Users\\...
    # Match single backslash NOT already escaped (not preceded by another backslash)
    s = re.sub(r'(?<!\\)\\(?![\\"/bfnrtu])', r'\\\\', s)

    return s


def parse_action(raw_text: str) -> Optional[dict]:
    """Parse an action JSON from raw LLM output.

    Handles common issues: markdown fences, extra text before/after JSON,
    and common LLM JSON malformations (misplaced commas, missing separators).
    Returns the parsed dict or None if unparseable.
    """
    # Strip markdown code fences if present
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Try to find a JSON object in the text
    # Look for the outermost { ... }
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start == -1 or brace_end == -1 or brace_end <= brace_start:
        return None

    json_str = text[brace_start:brace_end + 1]

    # Attempt 1: parse as-is
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass  # expected — try repair next

    # Attempt 2: repair common issues and retry
    repaired = _repair_json(json_str)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass  # repaired JSON also invalid — try regex extraction

    # Attempt 3: aggressive regex extraction of known fields
    try:
        thought = re.search(r'"thought"\s*:\s*"((?:[^"\\]|\\.)*)"', json_str)
        action = re.search(r'"action"\s*:\s*"((?:[^"\\]|\\.)*)"', json_str)
        target = re.search(r'"target"\s*:\s*"((?:[^"\\]|\\.)*)"', json_str)
        target_type = re.search(r'"target_type"\s*:\s*"((?:[^"\\]|\\.)*)"', json_str)
        coords = re.search(r'"fallback_coords"\s*:\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]', json_str)
        params_match = re.search(r'"params"\s*:\s*(\{[^}]*\})', json_str)

        if action:
            result = {
                "thought": thought.group(1) if thought else "",
                "action": action.group(1),
                "target": target.group(1) if target else "",
                "target_type": target_type.group(1) if target_type else "",
                "fallback_coords": [int(coords.group(1)), int(coords.group(2))] if coords else [0, 0],
                "params": json.loads(params_match.group(1)) if params_match else {},
            }
            return result
    except Exception:
        pass  # regex extraction failed — give up

    return None


def validate_action(action: dict) -> tuple[bool, str]:
    """Validate a parsed action dict against the schema.

    Returns (is_valid, error_message).
    """
    if not isinstance(action, dict):
        return False, "Action must be a JSON object."

    # Required fields
    for field in ("thought", "action", "target"):
        if field not in action:
            return False, f"Missing required field: '{field}'."

    if action["action"] not in VALID_ACTIONS:
        return False, f"Invalid action '{action['action']}'. Must be one of: {VALID_ACTIONS}"

    # Validate params for specific actions
    params = action.get("params", {})
    act = action["action"]

    if act == "type" and "text" not in params:
        return False, "Action 'type' requires params.text"

    if act == "key_press" and "key" not in params:
        return False, "Action 'key_press' requires params.key"

    if act == "scroll" and "clicks" not in params:
        return False, "Action 'scroll' requires params.clicks"

    if act == "wait" and "seconds" not in params:
        return False, "Action 'wait' requires params.seconds"

    if act in ("done", "fail") and "reason" not in params:
        return False, "Action 'done'/'fail' requires params.reason"

    if act in ("blender_python", "blender_query") and "code" not in params:
        return False, f"Action '{act}' requires params.code (a bpy Python script)"

    return True, ""


# ---------------------------------------------------------------------------
# Safety checker
# ---------------------------------------------------------------------------

def _matches_rule(rule: dict, app: str, action: str, target: str) -> bool:
    """Check if a safety rule matches the given action context."""
    rule_app = rule.get("app", "*")
    rule_action = rule.get("action", "*")
    rule_target = rule.get("target", "*")

    if rule_app != "*" and rule_app.lower() != app.lower():
        return False
    if rule_action != "*" and rule_action.lower() != action.lower():
        return False
    if rule_target != "*" and rule_target.lower() != target.lower():
        return False
    return True


def check_safety(app_name: str, action: dict) -> str:
    """Check an action against safety rules.

    Args:
        app_name: Name of the current application.
        action: The parsed action dict.

    Returns:
        "allow" — action is explicitly allowed (skip confirmation)
        "block" — action is blocked (do not execute)
        "neutral" — not in any list (follow autonomy mode)
    """
    rules = config.load_safety_rules()
    act = action.get("action", "")
    target = action.get("target", "")
    # For key_press, the actual key is in params — use that for safety matching
    if act == "key_press":
        target = action.get("params", {}).get("key", target)

    # Check block list first (takes priority)
    for rule in rules.get("block", []):
        if _matches_rule(rule, app_name, act, target):
            return "block"

    # Check allow list
    for rule in rules.get("allow", []):
        if _matches_rule(rule, app_name, act, target):
            return "allow"

    # Default-deny: if the app has NO app-specific allow rules, block it.
    # Wildcard rules (app="*") don't count — the app must be explicitly listed.
    # This prevents the agent from automating unknown/untrusted applications.
    app_has_specific_rules = any(
        rule.get("app", "*").lower() == app_name.lower()
        for rule in rules.get("allow", [])
    )
    if not app_has_specific_rules:
        _log.warning("Default-deny: app '%s' has no allow rules - blocking %s",
                      app_name, act)
        return "block"

    return "neutral"


def should_confirm(app_name: str, action: dict) -> bool:
    """Determine if the user should be asked to confirm this action.

    Based on autonomy mode and safety rules.
    """
    mode = config.AUTONOMY_MODE

    if mode == "auto":
        return False
    if mode == "confirm":
        return True

    # smart mode
    safety = check_safety(app_name, action)
    if safety == "allow":
        return False
    if safety == "block":
        return True  # will be blocked, but confirm shows the user why
    return True  # neutral = ask in smart mode


def format_action_for_display(action: dict) -> str:
    """Format an action dict as a human-readable string."""
    act = action.get("action", "?")
    target = action.get("target", "?")
    params = action.get("params", {})
    thought = action.get("thought", "")

    parts = [f"[{act.upper()}] → {target}"]
    if params:
        parts.append(f"  params: {json.dumps(params)}")
    if thought:
        parts.append(f"  reason: {thought}")
    return "\n".join(parts)
