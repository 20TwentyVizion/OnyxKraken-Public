"""Episode schema — declarative beats with branching, guards, and state.

Example episode (data/episodes/demo_intro.yaml)::

    id: demo_intro
    title: "Onyx Introduces Himself"
    cast: [onyx]
    scene: studio_dark
    vars:
      mood: ready
    beats:
      - emotion: focused
        who: onyx
      - say: "Welcome to OnyxKraken. *smiles* Ready to build?"
        who: onyx
      - pose: present
        who: onyx
      - choice:
          prompt: "What brings you here?"
          options:
            - text: "Show me the ecosystem."
              goto: tour
            - text: "Just exploring."
              goto: idle
      - label: tour
      - say: "Let's tour the BlakCloud."
      - goto: end
      - label: idle
      - say: "Take your time. *nods*"
      - label: end

Beats are dispatched in order; goto/label/choice enable branching.
`set` mutates state; `if`/`unless` on any beat acts as a guard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union


# ---------------------------------------------------------------------------
# Beat types
# ---------------------------------------------------------------------------

@dataclass
class Beat:
    """Base beat — common metadata."""
    if_: Optional[str] = None     # python expression evaluated against vars
    unless: Optional[str] = None
    label: Optional[str] = None   # makes this beat a goto target


@dataclass
class DialogueBeat(Beat):
    say: str = ""
    who: str = "onyx"
    mood: str = "ready"
    auto_pose: bool = True


@dataclass
class EmotionBeat(Beat):
    emotion: str = "neutral"
    who: str = "onyx"
    intensity: float = 1.0
    mix: dict[str, float] = field(default_factory=dict)


@dataclass
class PoseBeat(Beat):
    pose: str = "neutral"
    who: str = "onyx"
    transition_ms: int = 300


@dataclass
class AnimBeat(Beat):
    anim: str = ""
    who: str = "onyx"
    loop: bool = False


@dataclass
class WaitBeat(Beat):
    wait_ms: int = 500


@dataclass
class SceneBeat(Beat):
    scene: str = ""
    transition: str = "cut"


@dataclass
class GotoBeat(Beat):
    goto: str = ""


@dataclass
class SetBeat(Beat):
    set: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChoiceOption:
    text: str
    goto: str
    if_: Optional[str] = None


@dataclass
class ChoiceBeat(Beat):
    prompt: str = ""
    who: str = "onyx"
    options: list[ChoiceOption] = field(default_factory=list)


@dataclass
class MusicBeat(Beat):
    """Play background music or change music state."""
    track: str = ""           # track name or path
    action: str = "play"      # play, stop, fade_in, fade_out, pause, resume
    volume: float = 1.0       # 0.0 to 1.0
    fade_ms: int = 1000       # fade duration for fade_in/fade_out


@dataclass
class SfxBeat(Beat):
    """Play a sound effect."""
    sound: str = ""           # sound name or path
    volume: float = 1.0       # 0.0 to 1.0
    delay_ms: int = 0         # delay before playing


@dataclass
class CameraBeat(Beat):
    """Camera movement or framing change."""
    action: str = "cut"       # cut, pan, zoom, dolly, shake
    target: str = ""          # character or position to focus on
    duration_ms: int = 1000   # movement duration
    easing: str = "ease"      # ease, linear, ease_in, ease_out, bounce


@dataclass
class LightingBeat(Beat):
    """Lighting change or effect."""
    preset: str = "neutral"   # neutral, dramatic, warm, cool, spotlight, dim
    intensity: float = 1.0    # 0.0 to 1.0
    color: str = ""           # hex color override (optional)
    transition_ms: int = 500  # fade duration


@dataclass
class GazeBeat(Beat):
    """Direct a character's gaze at another character or position."""
    who: str = "onyx"
    target: str = ""          # character name to look at, or empty to clear gaze
    x: float = 0.0            # world-space x (if target is empty)
    y: float = 0.0            # world-space y (if target is empty)


@dataclass
class Episode:
    id: str
    title: str = ""
    cast: list[str] = field(default_factory=list)
    scene: str = ""
    vars: dict[str, Any] = field(default_factory=dict)
    beats: list[Beat] = field(default_factory=list)
    description: str = ""

    def labels(self) -> dict[str, int]:
        """Return label -> beat index map for goto resolution."""
        return {b.label: i for i, b in enumerate(self.beats) if b.label}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_BeatLike = Union[
    DialogueBeat, EmotionBeat, PoseBeat, AnimBeat,
    WaitBeat, SceneBeat, GotoBeat, SetBeat, ChoiceBeat,
    MusicBeat, SfxBeat, CameraBeat, LightingBeat, GazeBeat, Beat,
]


def _parse_beat(raw: dict) -> _BeatLike:
    if not isinstance(raw, dict):
        raise ValueError(f"Beat must be a mapping, got {type(raw).__name__}")
    common = {
        "if_": raw.get("if"),
        "unless": raw.get("unless"),
        "label": raw.get("label"),
    }
    if "say" in raw:
        return DialogueBeat(
            say=str(raw["say"]),
            who=str(raw.get("who", "onyx")),
            mood=str(raw.get("mood", "ready")),
            auto_pose=bool(raw.get("auto_pose", True)),
            **common,
        )
    if "emotion" in raw or "emotion_mix" in raw:
        raw_mix = raw.get("emotion_mix") or {}
        if not isinstance(raw_mix, dict):
            raise ValueError("emotion_mix must be a mapping of emotion -> weight")
        mix = {str(k): float(v) for k, v in raw_mix.items()}
        return EmotionBeat(
            emotion=str(raw.get("emotion", "neutral")),
            who=str(raw.get("who", "onyx")),
            intensity=float(raw.get("intensity", 1.0)),
            mix=mix,
            **common,
        )
    if "pose" in raw:
        return PoseBeat(
            pose=str(raw["pose"]),
            who=str(raw.get("who", "onyx")),
            transition_ms=int(raw.get("transition_ms", 300)),
            **common,
        )
    if "anim" in raw:
        return AnimBeat(
            anim=str(raw["anim"]),
            who=str(raw.get("who", "onyx")),
            loop=bool(raw.get("loop", False)),
            **common,
        )
    if "wait_ms" in raw or "wait" in raw:
        return WaitBeat(
            wait_ms=int(raw.get("wait_ms", raw.get("wait", 500))),
            **common,
        )
    if "scene" in raw:
        return SceneBeat(
            scene=str(raw["scene"]),
            transition=str(raw.get("transition", "cut")),
            **common,
        )
    if "goto" in raw:
        return GotoBeat(goto=str(raw["goto"]), **common)
    if "set" in raw:
        return SetBeat(set=dict(raw["set"]), **common)
    if "choice" in raw:
        ch = raw["choice"] or {}
        opts = [
            ChoiceOption(
                text=str(o.get("text", "")),
                goto=str(o.get("goto", "")),
                if_=o.get("if"),
            )
            for o in ch.get("options", [])
        ]
        return ChoiceBeat(
            prompt=str(ch.get("prompt", "")),
            who=str(ch.get("who", "onyx")),
            options=opts,
            **common,
        )
    if "music" in raw:
        return MusicBeat(
            track=str(raw.get("music", "")),
            action=str(raw.get("action", "play")),
            volume=float(raw.get("volume", 1.0)),
            fade_ms=int(raw.get("fade_ms", 1000)),
            **common,
        )
    if "sfx" in raw:
        return SfxBeat(
            sound=str(raw.get("sfx", "")),
            volume=float(raw.get("volume", 1.0)),
            delay_ms=int(raw.get("delay_ms", 0)),
            **common,
        )
    if "camera" in raw:
        return CameraBeat(
            action=str(raw.get("camera", "cut")),
            target=str(raw.get("target", "")),
            duration_ms=int(raw.get("duration_ms", 1000)),
            easing=str(raw.get("easing", "ease")),
            **common,
        )
    if "lighting" in raw:
        return LightingBeat(
            preset=str(raw.get("lighting", "neutral")),
            intensity=float(raw.get("intensity", 1.0)),
            color=str(raw.get("color", "")),
            transition_ms=int(raw.get("transition_ms", 500)),
            **common,
        )
    if "gaze" in raw:
        return GazeBeat(
            who=str(raw.get("who", "onyx")),
            target=str(raw.get("gaze", "")),
            x=float(raw.get("x", 0.0)),
            y=float(raw.get("y", 0.0)),
            **common,
        )
    if common["label"]:
        return Beat(**common)
    raise ValueError(f"Unrecognised beat keys: {sorted(raw.keys())}")


def parse_episode(raw: dict) -> Episode:
    if not isinstance(raw, dict):
        raise ValueError("Episode must be a mapping")
    if "id" not in raw:
        raise ValueError("Episode is missing required field 'id'")
    beats = [_parse_beat(b) for b in raw.get("beats", []) or []]
    return Episode(
        id=str(raw["id"]),
        title=str(raw.get("title", raw["id"])),
        cast=[str(x) for x in raw.get("cast", []) or []],
        scene=str(raw.get("scene", "")),
        vars=dict(raw.get("vars", {}) or {}),
        beats=beats,
        description=str(raw.get("description", "")),
    )


def load_episode(path: Path) -> Episode:
    """Load episode from a YAML or JSON file."""
    text = path.read_text(encoding="utf-8")
    data: dict
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as e:
            raise RuntimeError("pyyaml is required to load YAML episodes") from e
        data = yaml.safe_load(text)
    else:
        import json
        data = json.loads(text)
    return parse_episode(data)
