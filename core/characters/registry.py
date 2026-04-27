"""Unified Character Registry.

Single source of truth for character metadata across face, body, voice, and
episode systems. Replaces scattered definitions in:
  - face/stage/animation_studio.py     (8 hardcoded character cards)
  - face/stage/dialogue_track.py       (CHARACTER_VOICES)
  - face/stage/character_library.py    (body types)
  - core/voice.py                      (CHARACTER_EDGE_VOICES)

A Character bundles identity + visual theme + voice + body type + default pose
set so any subsystem (chat, episode player, MCP tool) can resolve a character
by name and get everything it needs in one lookup.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


_REGISTRY_PATH = Path(__file__).resolve().parent / "characters.json"


@dataclass(frozen=True)
class Character:
    """Unified character definition."""

    id: str                              # canonical lowercase id ("onyx", "xyno")
    name: str                            # display name ("Onyx", "Xyno")
    role: str                            # short role/archetype description
    voice_edge: str                      # Edge TTS voice id
    voice_fish: str = ""                 # Fish Audio S2 voice id (optional)
    theme_color: str = "#00d4ff"         # primary accent color (hex)
    accent_color: str = "#005580"        # secondary color
    body_type: str = "humanoid"          # body_types.py key
    default_pose: str = "neutral"        # CINEMA_POSES key
    default_emotion: str = "neutral"     # face_spec.json emotion key
    pose_aliases: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    bio: str = ""

    # Personality — used by Duo / conversation / dispatch_line to shape voice.
    personality: str = ""                # one-paragraph who-they-are
    voice_style: str = ""                # how they sound when speaking
    speech_patterns: list[str] = field(default_factory=list)  # phrasing tics
    do_say: list[str] = field(default_factory=list)           # in-character examples
    dont_say: list[str] = field(default_factory=list)         # anti-examples

    def to_dict(self) -> dict:
        return asdict(self)

    def llm_persona_block(self) -> str:
        """Render a system-prompt block that captures this character's voice."""
        lines = [f"You are {self.name} — {self.role}."]
        if self.personality:
            lines.append(self.personality)
        if self.voice_style:
            lines.append(f"Voice: {self.voice_style}")
        if self.speech_patterns:
            patterns = "; ".join(self.speech_patterns)
            lines.append(f"Speech patterns: {patterns}.")
        if self.do_say:
            examples = " / ".join(f'"{s}"' for s in self.do_say)
            lines.append(f"In character, you might say: {examples}")
        if self.dont_say:
            examples = " / ".join(f'"{s}"' for s in self.dont_say)
            lines.append(f"You would never say: {examples}")
        return "\n".join(lines)


class CharacterRegistry:
    """Loads and serves Character definitions from characters.json."""

    def __init__(self, source: Optional[Path] = None) -> None:
        self._path = source or _REGISTRY_PATH
        self._chars: dict[str, Character] = {}
        self.reload()

    def reload(self) -> None:
        if not self._path.exists():
            self._chars = {}
            return
        data = json.loads(self._path.read_text(encoding="utf-8"))
        self._chars = {
            entry["id"].lower(): Character(**entry)
            for entry in data.get("characters", [])
        }

    def get(self, name: str) -> Optional[Character]:
        return self._chars.get(name.strip().lower())

    def require(self, name: str) -> Character:
        char = self.get(name)
        if char is None:
            raise KeyError(f"Unknown character: {name!r}")
        return char

    def all(self) -> list[Character]:
        return list(self._chars.values())

    def ids(self) -> list[str]:
        return sorted(self._chars.keys())

    def voice_for(self, name: str, backend: str = "edge") -> str:
        char = self.get(name)
        if char is None:
            return "en-US-GuyNeural" if backend == "edge" else ""
        return char.voice_fish if backend == "fish" else char.voice_edge


_singleton: Optional[CharacterRegistry] = None


def get_registry() -> CharacterRegistry:
    global _singleton
    if _singleton is None:
        _singleton = CharacterRegistry()
    return _singleton


def get_character(name: str) -> Optional[Character]:
    return get_registry().get(name)


def list_characters() -> list[Character]:
    return get_registry().all()
