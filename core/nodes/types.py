"""Type system for Onyx node connections.

Every output/input socket has a type. Connections are only valid between
matching types. Colors are used in the frontend for visual clarity.

Extended from EVERA's type system to include cross-app data types.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Dict


# ---------------------------------------------------------------------------
# NodeType enum — all data types that can flow between nodes
# ---------------------------------------------------------------------------

class NodeType(str, Enum):
    """All data types that can flow between nodes in the Onyx ecosystem."""

    # ── Primitives ──
    STRING = "STRING"
    INT = "INT"
    FLOAT = "FLOAT"
    BOOL = "BOOL"

    # ── Filesystem ──
    FILE_PATH = "FILE_PATH"

    # ── Cross-app ──
    AUDIO_FILE = "AUDIO_FILE"       # path to audio (WAV/MP3) — EVERA ↔ JustEdit
    VIDEO_FILE = "VIDEO_FILE"       # path to video — JustEdit ↔ Onyx recordings
    TEXT_DOCUMENT = "TEXT_DOCUMENT"  # structured text — SmartEngine ↔ JustEdit/Onyx
    PROJECT_REF = "PROJECT_REF"     # reference to any app project
    AGENT_RESULT = "AGENT_RESULT"   # result from Onyx agent task

    # ── EVERA domain ──
    ARTIST = "ARTIST"
    GENRE_PROFILE = "GENRE_PROFILE"
    CONCEPT = "CONCEPT"
    LYRICS = "LYRICS"
    TRACK_INFO = "TRACK_INFO"

    # ── SmartEngine domain ──
    SE_PROJECT = "SE_PROJECT"
    SCENE_TEXT = "SCENE_TEXT"
    MANUSCRIPT = "MANUSCRIPT"

    # ── JustEdit domain ──
    JE_PROJECT = "JE_PROJECT"
    TIMELINE = "TIMELINE"

    # ── Wildcard ──
    ANY = "ANY"


# Color map for frontend rendering
TYPE_COLORS: Dict[str, str] = {
    # Primitives
    NodeType.STRING: "#bdc3c7",
    NodeType.INT: "#bdc3c7",
    NodeType.FLOAT: "#bdc3c7",
    NodeType.BOOL: "#bdc3c7",
    NodeType.FILE_PATH: "#95a5a6",

    # Cross-app
    NodeType.AUDIO_FILE: "#e74c3c",
    NodeType.VIDEO_FILE: "#e67e22",
    NodeType.TEXT_DOCUMENT: "#2ecc71",
    NodeType.PROJECT_REF: "#9b59b6",
    NodeType.AGENT_RESULT: "#1abc9c",

    # EVERA
    NodeType.ARTIST: "#9b59b6",
    NodeType.GENRE_PROFILE: "#1abc9c",
    NodeType.CONCEPT: "#3498db",
    NodeType.LYRICS: "#2ecc71",
    NodeType.TRACK_INFO: "#e74c3c",

    # SmartEngine
    NodeType.SE_PROJECT: "#f39c12",
    NodeType.SCENE_TEXT: "#27ae60",
    NodeType.MANUSCRIPT: "#8e44ad",

    # JustEdit
    NodeType.JE_PROJECT: "#2980b9",
    NodeType.TIMELINE: "#d35400",

    # Wildcard
    NodeType.ANY: "#7f8c8d",
}


def types_compatible(output_type: NodeType, input_type: NodeType) -> bool:
    """Check if an output type can connect to an input type."""
    if input_type == NodeType.ANY or output_type == NodeType.ANY:
        return True
    return output_type == input_type


def hash_value(value: Any) -> str:
    """Create a deterministic hash for any node output value (for caching)."""
    if isinstance(value, dict):
        return hashlib.md5(
            json.dumps(value, sort_keys=True, default=str).encode()
        ).hexdigest()[:12]
    if isinstance(value, (list, tuple)):
        return hashlib.md5(
            json.dumps(value, default=str).encode()
        ).hexdigest()[:12]
    return hashlib.md5(str(value).encode()).hexdigest()[:12]
