"""Unified Animation Catalog.

Bridges three previously-disjoint systems:
  - Face emotions (onyx-web/src/lib/face_spec.json — TypeScript renderer)
  - Body poses (face/stage/animation_presets.py CINEMA_POSES)
  - Body animations (face/stage/animation_presets.py BODY_ANIMATIONS)

The catalog adds an *emotion -> pose -> body_anim* triplet so a single intent
("excited") drives the face, body posture, and gesture together. This was
previously hard-coded across multiple files with no link between them.

Used by:
  - REST routes (/animation/play, /face/emotion, /character/pose)
  - MCP tools (drive_emotion, drive_pose)
  - Chat dispatch pipeline (intent -> catalog -> face+body+voice)
  - TypeScript codegen (scripts/codegen_catalog.py)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


_ROOT = Path(__file__).resolve().parent.parent.parent
_FACE_SPEC = _ROOT / "onyx-web" / "src" / "lib" / "face_spec.json"


@dataclass(frozen=True)
class Emotion:
    """Face emotion — driven by face_spec.json emotion_presets."""
    id: str
    accent_color: str
    squint: float
    brow_raise: float
    eye_widen: float
    mouth_curve: float
    pupil_size: float
    gaze_speed: float
    blink_rate: float
    intensity: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Pose:
    """Static body pose — joint angle snapshot."""
    id: str
    description: str
    joints: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "description": self.description, "joints": dict(self.joints)}


@dataclass(frozen=True)
class BodyAnimDescriptor:
    """Lightweight descriptor for a named body animation in BODY_ANIMATIONS."""
    id: str
    fps: int
    duration_frames: int
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# Default emotion -> pose -> body_anim coupling. Anyone can override at
# runtime via AnimationCatalog.set_emotion_links() but this gives every
# emotion a sensible default body language out of the box.
_EMOTION_LINKS: dict[str, tuple[str, str]] = {
    # emotion_id    : (pose_id,        body_anim_id)
    "neutral":        ("neutral",       "idle_breathe"),
    "thinking":       ("thinking",      "think_scratch"),
    "curious":        ("neutral",       "look_around"),
    "satisfied":      ("confident",     "nod"),
    "confused":       ("shrug",         "shrug_anim"),
    "determined":     ("confident",     "confident_stance"),
    "amused":         ("hip",           "talk_gesture"),
    "surprised":      ("neutral",       "startle"),
    "listening":      ("neutral",       "listen_sway"),
    "working":        ("thinking",      "talk_gesture"),
    "focused":        ("crossed",       "idle_breathe"),
    "happy":          ("confident",     "celebrate"),
    "sad":            ("neutral",       "sad_slump"),
    "excited":        ("excited",       "excited_bounce"),
    "skeptical":      ("crossed",       "crossed_arms"),
    "proud":          ("confident",     "confident_stance"),
    "sleep":          ("neutral",       "idle_breathe"),
}


class AnimationCatalog:
    """The unified catalog. Lazy-loads from face_spec.json + animation_presets."""

    def __init__(self) -> None:
        self._emotions: dict[str, Emotion] = {}
        self._poses: dict[str, Pose] = {}
        self._body_anims: dict[str, BodyAnimDescriptor] = {}
        self._links: dict[str, tuple[str, str]] = dict(_EMOTION_LINKS)
        self._loaded = False

    # ------------------------------------------------------------------ load
    def load(self) -> None:
        if self._loaded:
            return
        self._load_emotions()
        self._load_poses_and_anims()
        self._loaded = True

    def reload(self) -> None:
        self._loaded = False
        self._emotions.clear()
        self._poses.clear()
        self._body_anims.clear()
        self.load()

    def _load_emotions(self) -> None:
        if not _FACE_SPEC.exists():
            return
        spec = json.loads(_FACE_SPEC.read_text(encoding="utf-8"))
        accents = spec.get("emotion_accents", {})
        for eid, params in spec.get("emotion_presets", {}).items():
            self._emotions[eid] = Emotion(
                id=eid,
                accent_color=accents.get(eid, "#00d4ff"),
                squint=float(params.get("squint", 0.0)),
                brow_raise=float(params.get("brow_raise", 0.0)),
                eye_widen=float(params.get("eye_widen", 0.0)),
                mouth_curve=float(params.get("mouth_curve", 0.0)),
                pupil_size=float(params.get("pupil_size", 1.0)),
                gaze_speed=float(params.get("gaze_speed", 1.0)),
                blink_rate=float(params.get("blink_rate", 1.0)),
                intensity=float(params.get("intensity", 0.0)),
            )

    def _load_poses_and_anims(self) -> None:
        try:
            from face.stage.animation_presets import CINEMA_POSES, BODY_ANIMATIONS
        except Exception:
            return
        for pid, data in CINEMA_POSES.items():
            joints = {k: float(v) for k, v in data.items() if k != "description"}
            self._poses[pid] = Pose(
                id=pid,
                description=str(data.get("description", "")),
                joints=joints,
            )
        for aid, anim in BODY_ANIMATIONS.items():
            self._body_anims[aid] = BodyAnimDescriptor(
                id=aid,
                fps=int(anim.fps),
                duration_frames=int(anim.duration_frames),
            )

    # ------------------------------------------------------------------ get
    def emotion(self, eid: str) -> Optional[Emotion]:
        self.load()
        return self._emotions.get(eid)

    def pose(self, pid: str) -> Optional[Pose]:
        self.load()
        return self._poses.get(pid)

    def body_anim(self, aid: str) -> Optional[BodyAnimDescriptor]:
        self.load()
        return self._body_anims.get(aid)

    def emotions(self) -> list[Emotion]:
        self.load()
        return list(self._emotions.values())

    def poses(self) -> list[Pose]:
        self.load()
        return list(self._poses.values())

    def body_anims(self) -> list[BodyAnimDescriptor]:
        self.load()
        return list(self._body_anims.values())

    def link_for(self, emotion_id: str) -> tuple[Optional[str], Optional[str]]:
        """Return (pose_id, body_anim_id) for an emotion, or (None, None)."""
        return self._links.get(emotion_id, (None, None))

    def set_emotion_links(self, links: dict[str, tuple[str, str]]) -> None:
        self._links.update(links)

    def to_dict(self) -> dict:
        self.load()
        return {
            "emotions": [e.to_dict() for e in self._emotions.values()],
            "poses": [p.to_dict() for p in self._poses.values()],
            "body_anims": [b.to_dict() for b in self._body_anims.values()],
            "emotion_links": {k: {"pose": v[0], "body_anim": v[1]} for k, v in self._links.items()},
        }


_singleton: Optional[AnimationCatalog] = None


def get_catalog() -> AnimationCatalog:
    global _singleton
    if _singleton is None:
        _singleton = AnimationCatalog()
        _singleton.load()
    return _singleton
