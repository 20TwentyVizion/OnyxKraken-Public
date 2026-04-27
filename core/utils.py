"""Shared utility functions for OnyxKraken core modules.

Extracts commonly duplicated helpers into a single location.
"""

import json
from typing import Optional


def extract_json(raw: str) -> Optional[dict]:
    """Extract the first JSON object from raw text.

    Uses balanced-brace matching to handle nested objects correctly.
    Returns None if no valid JSON object is found.
    """
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None
