"""Test that the JSON repair handles the exact malformed output from the LLM."""

from agent.actions import parse_action


def test_repair_adjacent_string_values():
    """Exact malformed output the LLM produced for Grok."""
    raw = '''{"thought": "Type 'What is the meaning of life?'," "action": "type", "target": "Chat input", "target_type": "Edit", "fallback_coords": [960, 539], "params": {"text": "What is the meaning of life?"}}'''
    result = parse_action(raw)
    assert result is not None, "Failed to parse malformed JSON"
    assert result["action"] == "type"
    assert result["target"] == "Chat input"
    assert result["params"]["text"] == "What is the meaning of life?"
    assert result.get("fallback_coords") == [960, 539]


def test_repair_markdown_fenced():
    """LLM wraps JSON in markdown code fence."""
    raw = '```json\n{"thought": "x", "action": "click", "target": "OK", "params": {}}\n```'
    result = parse_action(raw)
    assert result is not None
    assert result["action"] == "click"


def test_repair_trailing_text():
    """LLM adds explanation after JSON."""
    raw = '{"thought": "x", "action": "done", "target": "", "params": {"reason": "finished"}} I hope this helps!'
    result = parse_action(raw)
    assert result is not None
    assert result["action"] == "done"
