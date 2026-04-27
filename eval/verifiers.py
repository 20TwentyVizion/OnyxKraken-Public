"""Verifiers — check whether a task outcome matches expectations.

Each verifier is a function that takes the TaskResult and returns (passed, detail).
"""

import logging
import os
from typing import Callable

try:
    from desktop.controller import find_window, get_accessibility_tree, list_windows
except (ImportError, RuntimeError):
    find_window = get_accessibility_tree = None
    def list_windows(): return []

_log = logging.getLogger("eval.verifiers")


def window_exists(title_contains: str):
    """Verify that a window with the given title substring is open."""
    def check(result) -> tuple[bool, str]:
        for w in list_windows():
            if title_contains.lower() in w["title"].lower():
                return True, f"Window found: {w['title']}"
        return False, f"No window containing '{title_contains}'"
    check.__name__ = f"window_exists('{title_contains}')"
    return check


def window_text_contains(title_contains: str, text: str):
    """Verify that ANY window matching the title contains specific text."""
    def check(result) -> tuple[bool, str]:
        from pywinauto import Desktop
        matching_windows = []
        for win in Desktop(backend="uia").windows():
            try:
                if title_contains.lower() in win.window_text().lower():
                    matching_windows.append(win)
            except Exception:
                continue
        if not matching_windows:
            return False, f"Window '{title_contains}' not found"
        for win in matching_windows:
            try:
                tree = get_accessibility_tree(win, max_depth=3)
                all_text = " ".join(el["name"] for el in tree).lower()
                if text.lower() in all_text:
                    return True, f"Text '{text}' found in window"
            except Exception:
                continue
        return False, f"Text '{text}' not found in any of {len(matching_windows)} matching windows"
    check.__name__ = f"window_text_contains('{title_contains}', '{text}')"
    return check


def file_exists(path: str):
    """Verify that a file exists at the given path."""
    def check(result) -> tuple[bool, str]:
        expanded = os.path.expandvars(os.path.expanduser(path))
        if os.path.exists(expanded):
            return True, f"File exists: {expanded}"
        return False, f"File not found: {expanded}"
    check.__name__ = f"file_exists('{path}')"
    return check


def task_not_aborted():
    """Verify the task completed without aborting."""
    def check(result) -> tuple[bool, str]:
        if result.aborted:
            return False, f"Task aborted: {result.failure_reason}"
        return True, "Task completed without aborting"
    check.__name__ = "task_not_aborted()"
    return check


def all_steps_completed():
    """Verify all planned steps were completed."""
    def check(result) -> tuple[bool, str]:
        if result.steps_completed == result.steps_planned:
            return True, f"All {result.steps_planned} steps completed"
        return False, f"Only {result.steps_completed}/{result.steps_planned} steps completed"
    check.__name__ = "all_steps_completed()"
    return check


def final_window_title_contains(text: str):
    """Verify the final active window title contains specific text."""
    def check(result) -> tuple[bool, str]:
        if text.lower() in result.final_window_title.lower():
            return True, f"Final window: {result.final_window_title}"
        return False, f"Final window '{result.final_window_title}' doesn't contain '{text}'"
    check.__name__ = f"final_window_title_contains('{text}')"
    return check


def file_contains(path: str, text: str):
    """Verify that a file exists and contains specific text."""
    def check(result) -> tuple[bool, str]:
        expanded = os.path.expandvars(os.path.expanduser(path))
        if not os.path.exists(expanded):
            return False, f"File not found: {expanded}"
        try:
            with open(expanded, "r", encoding="utf-8") as f:
                content = f.read()
            if text in content:
                return True, f"File contains '{text}'"
            return False, f"File exists but doesn't contain '{text}' (has: {content[:100]})"
        except Exception as e:
            return False, f"Error reading file: {e}"
    check.__name__ = f"file_contains('{path}', '{text}')"
    return check


def completed_within(max_seconds: float):
    """Verify the task completed within a time limit."""
    def check(result) -> tuple[bool, str]:
        if result.total_time <= max_seconds:
            return True, f"Completed in {result.total_time:.1f}s (limit: {max_seconds}s)"
        return False, f"Took {result.total_time:.1f}s (limit: {max_seconds}s)"
    check.__name__ = f"completed_within({max_seconds}s)"
    return check


# Registry for building verifiers from task JSON
VERIFIER_BUILDERS = {
    "window_exists": lambda params: window_exists(params["title_contains"]),
    "window_text_contains": lambda params: window_text_contains(
        params["title_contains"], params["text"]
    ),
    "file_exists": lambda params: file_exists(params["path"]),
    "file_contains": lambda params: file_contains(params["path"], params["text"]),
    "task_not_aborted": lambda params: task_not_aborted(),
    "all_steps_completed": lambda params: all_steps_completed(),
    "final_window_title_contains": lambda params: final_window_title_contains(params["text"]),
    "completed_within": lambda params: completed_within(params["max_seconds"]),
}


def build_verifiers(verifier_defs: list[dict]) -> list[Callable]:
    """Build verifier functions from JSON definitions."""
    verifiers = []
    for vdef in verifier_defs:
        vtype = vdef["type"]
        params = {k: v for k, v in vdef.items() if k != "type"}
        builder = VERIFIER_BUILDERS.get(vtype)
        if builder is None:
            raise ValueError(f"Unknown verifier type: {vtype}")
        verifiers.append(builder(params))
    return verifiers
