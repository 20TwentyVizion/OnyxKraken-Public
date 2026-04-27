"""Smoke test — verify all core components work."""

import pytest
import config
from log import setup_logging
setup_logging(config.LOG_LEVEL)

from agent.actions import parse_action, validate_action, check_safety
from agent.orchestrator import _classify_step
from desktop.controller import list_windows, find_window, get_accessibility_tree, format_accessibility_tree


# ---------------------------------------------------------------------------
# Action parsing
# ---------------------------------------------------------------------------

def test_parse_valid_json():
    raw = '{"thought": "test", "action": "click", "target": "File", "target_type": "MenuItem", "fallback_coords": [100,200], "params": {}}'
    a = parse_action(raw)
    assert a is not None
    assert a["action"] == "click"
    assert a["target"] == "File"
    valid, err = validate_action(a)
    assert valid, err


def test_parse_malformed_markdown():
    broken = parse_action('Sure! Here is some text ```json {"action": "click"} ``` done')
    assert broken is not None
    assert broken["action"] == "click"


def test_validate_unknown_action():
    invalid = {"thought": "x", "action": "explode", "target": "everything", "params": {}}
    valid, err = validate_action(invalid)
    assert not valid
    assert "explode" in err


# ---------------------------------------------------------------------------
# Safety rules
# ---------------------------------------------------------------------------

def test_safety_allow_notepad():
    a = parse_action('{"thought": "t", "action": "click", "target": "File", "target_type": "MenuItem", "fallback_coords": [100,200], "params": {}}')
    assert check_safety("notepad", a) == "allow"


def test_safety_block_powershell():
    a = parse_action('{"thought": "t", "action": "click", "target": "File", "target_type": "MenuItem", "fallback_coords": [100,200], "params": {}}')
    assert check_safety("powershell", a) == "block"


def test_safety_block_alt_f4():
    bad = parse_action('{"thought": "x", "action": "key_press", "target": "alt+f4", "params": {"key": "alt+f4"}}')
    assert check_safety("notepad", bad) == "block"


# ---------------------------------------------------------------------------
# Step classification
# ---------------------------------------------------------------------------

def test_classify_launch():
    assert _classify_step("Open Grok")["type"] == "launch"
    assert _classify_step("Launch Notepad")["type"] == "launch"


def test_classify_interact():
    assert _classify_step("Type the question and press Enter")["type"] == "interact"
    assert _classify_step("Scroll down and click Submit")["type"] == "interact"


def test_classify_chat_wait():
    assert _classify_step("Wait for the response and read it")["type"] == "chat_wait"
    assert _classify_step("Read the response")["type"] == "chat_wait"


# ---------------------------------------------------------------------------
# Desktop / accessibility tree (live, may vary)
# ---------------------------------------------------------------------------

def test_list_windows():
    windows = list_windows()
    assert isinstance(windows, list)
    assert len(windows) > 0, "Expected at least one visible window"


def test_accessibility_tree():
    windows = list_windows()
    if not windows:
        pytest.skip("No windows found")
    win = find_window(windows[0]["title"])
    if not win:
        pytest.skip("Could not attach to window")
    tree = get_accessibility_tree(win, max_depth=2)
    assert isinstance(tree, list)
    formatted = format_accessibility_tree(tree[:10])
    assert isinstance(formatted, str)
