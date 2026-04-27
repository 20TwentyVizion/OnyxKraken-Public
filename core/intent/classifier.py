"""Intent / emotion classifier — pluggable backends.

Replaces the hardcoded `_ACTION_EMOTION_MAP` in face/backend.py with an
abstraction that any subsystem (chat, episode player, MCP) can call.

Three backends ship out of the box:
  - RegexClassifier — fast, deterministic, the legacy mapping (default).
  - OllamaClassifier — local LLM-driven, context-aware (qwen3-coder-64k).
  - CompositeClassifier — try LLM first, fall back to regex.

Pick at runtime via set_classifier() or env var ONYX_INTENT_BACKEND
(values: regex|ollama|composite).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional, Protocol


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class IntentResult:
    """Output of classification — clean speech text plus dispatched cues."""
    clean_text: str
    emotions: list[str] = field(default_factory=list)   # ordered, deduped
    poses: list[str] = field(default_factory=list)      # explicit pose cues
    body_anims: list[str] = field(default_factory=list) # explicit anim cues
    raw_actions: list[str] = field(default_factory=list)

    @property
    def primary_emotion(self) -> Optional[str]:
        return self.emotions[0] if self.emotions else None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class IntentClassifier(Protocol):
    def classify(self, text: str) -> IntentResult: ...


# ---------------------------------------------------------------------------
# Regex backend (default — fast, no external deps)
# ---------------------------------------------------------------------------

# Migrated from face/backend.py:_ACTION_EMOTION_MAP. Edit here, not there.
_ACTION_EMOTION_MAP: dict[str, str] = {
    "glow": "satisfied", "glows": "satisfied", "bright": "satisfied",
    "smile": "happy", "smiles": "happy", "grin": "amused", "grins": "amused",
    "laugh": "amused", "laughs": "amused", "chuckle": "amused", "giggle": "amused",
    "think": "thinking", "thinks": "thinking", "ponder": "thinking", "considers": "thinking",
    "curious": "curious", "tilts": "curious", "tilt": "curious", "hmm": "curious",
    "nod": "satisfied", "nods": "satisfied", "agrees": "satisfied",
    "surprised": "surprised", "blink": "surprised", "gasp": "surprised", "wow": "surprised",
    "confused": "confused", "frown": "confused", "puzzled": "confused", "scratches": "confused",
    "determined": "determined", "focus": "determined", "narrows": "determined",
    "sad": "sad", "sigh": "sad", "sighs": "sad", "frowns": "sad", "droops": "sad",
    "excited": "excited", "bounces": "excited", "beams": "excited", "jumps": "excited",
    "wink": "amused", "winks": "amused",
    "proud": "proud", "puffs": "proud", "stands": "proud",
    "skeptical": "skeptical", "raises": "skeptical", "eyebrow": "skeptical", "doubt": "skeptical",
    "happy": "happy", "joy": "happy", "delighted": "happy", "pleased": "happy",
    "listen": "listening", "listens": "listening", "attentive": "listening",
    "work": "working", "works": "working", "typing": "working", "coding": "working",
}

# Direct *cue:value* extraction — episode authors can write *pose:wave* or
# *anim:celebrate* and the classifier will dispatch them as explicit cues.
_CUE_RE = re.compile(r"^\s*(pose|anim|emotion|body)\s*[:=]\s*(\w+)\s*$", re.IGNORECASE)
_ACTION_RE = re.compile(r"\*([^*]+)\*")


class RegexClassifier:
    """Legacy regex-based classifier. Deterministic, fast, offline."""

    def __init__(self, action_map: Optional[dict[str, str]] = None) -> None:
        self._map = dict(action_map) if action_map else dict(_ACTION_EMOTION_MAP)

    def classify(self, text: str) -> IntentResult:
        emotions: list[str] = []
        poses: list[str] = []
        anims: list[str] = []
        actions: list[str] = []
        seen_emotions: set[str] = set()

        for match in _ACTION_RE.finditer(text):
            raw = match.group(1).strip()
            actions.append(raw)
            cue = _CUE_RE.match(raw)
            if cue:
                kind, value = cue.group(1).lower(), cue.group(2).lower()
                if kind == "pose":
                    poses.append(value)
                elif kind in ("anim", "body"):
                    anims.append(value)
                elif kind == "emotion" and value not in seen_emotions:
                    emotions.append(value)
                    seen_emotions.add(value)
                continue
            lowered = raw.lower()
            for keyword, emotion in self._map.items():
                if keyword in lowered and emotion not in seen_emotions:
                    emotions.append(emotion)
                    seen_emotions.add(emotion)
                    break

        clean = _ACTION_RE.sub("", text).strip()
        clean = re.sub(r"\s{2,}", " ", clean).strip()
        return IntentResult(
            clean_text=clean,
            emotions=emotions,
            poses=poses,
            body_anims=anims,
            raw_actions=actions,
        )


# ---------------------------------------------------------------------------
# Ollama backend (context-aware)
# ---------------------------------------------------------------------------

_OLLAMA_PROMPT = (
    "Classify the speaker's emotional intent for facial animation. "
    "Reply with ONE word from this set: "
    "neutral, thinking, curious, satisfied, confused, determined, amused, "
    "surprised, listening, working, focused, happy, sad, excited, skeptical, "
    "proud. No punctuation. Just the word.\n\nText: "
)


class OllamaClassifier:
    """Local LLM classifier. Falls back gracefully if Ollama is unreachable."""

    def __init__(
        self,
        model: str = "qwen3-coder-64k",
        base_url: str = "http://localhost:11434",
        fallback: Optional[IntentClassifier] = None,
        timeout: float = 4.0,
    ) -> None:
        self._model = model
        self._base = base_url.rstrip("/")
        self._fallback = fallback or RegexClassifier()
        self._timeout = timeout

    def classify(self, text: str) -> IntentResult:
        # Always start from regex so explicit cues (*pose:wave*) are honored.
        result = self._fallback.classify(text)
        if not result.clean_text:
            return result
        try:
            import urllib.request
            import json as _json
            req = urllib.request.Request(
                f"{self._base}/api/generate",
                data=_json.dumps({
                    "model": self._model,
                    "prompt": _OLLAMA_PROMPT + result.clean_text,
                    "stream": False,
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            label = (data.get("response") or "").strip().lower().split()[0]
            if label and label not in result.emotions:
                result.emotions.insert(0, label)
        except Exception:
            pass
        return result


# ---------------------------------------------------------------------------
# Singleton & factory
# ---------------------------------------------------------------------------

_classifier: Optional[IntentClassifier] = None


def _build_default() -> IntentClassifier:
    backend = os.environ.get("ONYX_INTENT_BACKEND", "regex").strip().lower()
    if backend == "ollama":
        return OllamaClassifier()
    if backend == "composite":
        return OllamaClassifier(fallback=RegexClassifier())
    return RegexClassifier()


def get_classifier() -> IntentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = _build_default()
    return _classifier


def set_classifier(classifier: IntentClassifier) -> None:
    global _classifier
    _classifier = classifier


def classify(text: str) -> IntentResult:
    """Module-level convenience — uses the active classifier."""
    return get_classifier().classify(text)
