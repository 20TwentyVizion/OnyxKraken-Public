"""Shared utilities for the agent package."""

import json
import logging

_log = logging.getLogger("agent.utils")


def summarize_history(history: list[dict], max_entries: int = 6) -> str:
    """Build a human-readable summary of recent action history.

    Used by both _request_action and ErrorDiagnoser to avoid duplication.
    """
    lines = []
    for entry in history[-max_entries:]:
        if entry["role"] == "assistant":
            try:
                a = json.loads(entry["content"])
                lines.append(f"  Action: {a.get('action', '?')}: {a.get('target', '')} {a.get('params', {})}")
            except (json.JSONDecodeError, TypeError):
                pass
        elif entry["role"] == "user":
            content = entry.get("content", "")
            if "Result:" in content:
                lines.append(f"  Result: {content.split('Result:')[1].strip()[:150]}")
    return "\n".join(lines)
