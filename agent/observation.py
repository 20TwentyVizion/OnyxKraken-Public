"""Observation and action-request helpers for the orchestrator.

_build_observation  — assembles context string from accessibility tree + screenshot
_request_action     — asks the vision model to decide the next action
"""

import os

import config
from log import get_logger

_log = get_logger("agent.observation")

from agent.model_router import router
from agent.actions import (
    ACTION_SCHEMA_DESCRIPTION,
    parse_action,
    validate_action,
)
from agent.utils import summarize_history
try:
    from core.input_sanitizer import sanitize as _sanitize_input
except ImportError:
    def _sanitize_input(t, **kw): return t
try:
    from desktop.controller import (
        format_accessibility_tree,
        get_accessibility_tree,
        list_windows,
    )
except (ImportError, RuntimeError):
    format_accessibility_tree = get_accessibility_tree = list_windows = None

try:
    from vision.analyzer import image_to_base64
except ImportError:
    def image_to_base64(img): return ""


# Chat apps that support the chat_wait step type
_CHAT_APP_NAMES = frozenset({"grok", "chatgpt", "claude", "copilot"})

# Apps where post-type verification via accessibility tree is reliable
_VERIFIABLE_APPS = frozenset({"notepad", "unknown"})


def _build_observation(window, screenshot_img, app_module=None) -> tuple:
    """Build the observation context string from accessibility tree + screenshot info.

    Returns:
        (observation_string, accessibility_tree_list) — tree is reusable by execute_action.
    """
    parts = []
    tree = []

    # App module context (domain knowledge)
    if app_module is not None:
        ctx = app_module.get_context_prompt()
        if ctx:
            parts.append(f"## App-Specific Knowledge ({app_module.app_name})\n{ctx}")
        scripting_ctx = getattr(app_module, "get_scripting_prompt", None)
        if callable(scripting_ctx):
            scripting = scripting_ctx()
            if scripting:
                parts.append(f"## Scripting API Reference\n{scripting}")
        known = app_module.get_known_elements()
        if known:
            el_lines = "\n".join(
                f"  - [{e['control_type']}] \"{e['name']}\" — {e['description']}"
                for e in known
            )
            parts.append(f"## Known Elements\n{el_lines}")

    # Vision-only modules skip the accessibility tree entirely — they rely
    # on screenshots + coordinates for all interactions (e.g. web apps).
    vision_only = getattr(app_module, "vision_only", False)

    if vision_only:
        parts.append(
            "## Accessibility Tree\n"
            "SKIPPED — this app is vision-only. Use the screenshot and "
            "fallback_coords for ALL interactions. Do NOT attempt to target "
            "elements by name (they won't be found). Look at the screenshot, "
            "identify what you need to click/type, and use pixel coordinates."
        )
    elif window is not None:
        try:
            tree = get_accessibility_tree(window, max_depth=3)
            formatted = format_accessibility_tree(tree)
            parts.append("## Accessibility Tree (current window)\n" + formatted)
        except Exception as e:
            parts.append(f"## Accessibility Tree\n(error reading tree: {e})")
    else:
        parts.append("## Accessibility Tree\nNo active window found.")

    visible_windows = list_windows()
    win_list = "\n".join(f"  - {w['title']}" for w in visible_windows[:15])
    parts.append(f"## Visible Windows\n{win_list}")

    parts.append(
        "## Screenshot\nA screenshot of the current screen state is attached as an image."
    )

    return "\n\n".join(parts), tree


def _request_action(
    observation: str,
    current_step: str,
    overall_goal: str,
    screenshot_img,
    history: list[dict],
) -> dict:
    """Ask the vision model to decide the next action.

    Retries up to ACTION_RETRY_LIMIT on malformed output.
    """
    history_summary = ""
    if history:
        summary_text = summarize_history(history, max_entries=6)
        if summary_text:
            history_summary = "\n--- ACTIONS ALREADY TAKEN THIS STEP ---\n" + summary_text + "\n"

    home_dir = os.path.expanduser("~")
    desktop_dir = os.path.join(home_dir, "Desktop")
    instruction = (
        f"You are OnyxKraken, a Windows desktop automation agent.\n"
        f"System: Home={home_dir}, Desktop={desktop_dir}\n"
        f"Overall goal: {_sanitize_input(overall_goal)}\n"
        f"Current step: {_sanitize_input(current_step)}\n\n"
        f"CRITICAL RULES:\n"
        f"1. ONLY do what the current step says. Nothing more. Do NOT add extra actions like saving, closing, or cleanup.\n"
        f"2. If the current step has ALREADY been completed (check the actions taken below and the screenshot), "
        f"you MUST output a \"done\" action IMMEDIATELY.\n"
        f"3. After a successful type or click action that fulfills the step, your NEXT action MUST be \"done\".\n"
        f"4. NEVER save files, close windows, or press keyboard shortcuts unless the step EXPLICITLY asks for it.\n\n"
        f"{ACTION_SCHEMA_DESCRIPTION}\n"
        f"{history_summary}"
        f"--- CURRENT STATE ---\n"
        f"{observation}\n\n"
        f"Based on the screenshot and the information above, output your next action as a single JSON object. "
        f"If this step is already done, output a done action. Output ONLY the JSON, nothing else."
    )

    b64 = image_to_base64(screenshot_img)

    messages = []
    for entry in history[-4:]:
        messages.append(entry)

    messages.append({
        "role": "user",
        "content": instruction,
        "images": [b64],
    })

    for attempt in range(config.ACTION_RETRY_LIMIT):
        _log.debug(f"Requesting action (attempt {attempt + 1})...")
        response = router.chat("vision", messages)
        raw = response["message"]["content"]
        _log.debug(f"Raw LLM response ({len(raw)} chars):")
        preview = raw[:500] + ("..." if len(raw) > 500 else "")
        for line in preview.split("\n"):
            _log.debug(f"  | {line}")

        action = parse_action(raw)
        if action is None:
            _log.debug(f"Failed to parse JSON from response.")
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": (
                    "IMPORTANT: Your previous response was not valid JSON. "
                    "You MUST respond with ONLY a raw JSON object like this example:\n"
                    '{"thought": "I see Notepad is open", "action": "click", '
                    '"target": "File", "target_type": "MenuItem", '
                    '"fallback_coords": [50, 30], "params": {}}\n'
                    "No markdown fences, no explanation, just the JSON object."
                ),
            })
            continue

        valid, error = validate_action(action)
        if not valid:
            _log.debug(f"Parsed JSON but validation failed: {error}")
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": (
                    f"Your JSON was parsed but invalid: {error}\n"
                    f"Fix the issue and respond with ONLY the corrected JSON object."
                ),
            })
            continue

        _log.debug(f"Valid action parsed: {action['action']} → {action.get('target', '')}")
        return action

    return {
        "thought": f"Failed to get valid action after {config.ACTION_RETRY_LIMIT} attempts",
        "action": "fail",
        "target": "",
        "target_type": "",
        "fallback_coords": [0, 0],
        "params": {"reason": f"LLM output was malformed after {config.ACTION_RETRY_LIMIT} retries"},
    }
