"""Scene adapter — bridge legacy SceneDocument files to the Episode DSL.

The animation_studio.py GUI authors scenes as SceneDocument JSON; this
adapter converts them to Episode beats so the same headless EpisodePlayer
can run them. Lets the desktop GUI author content while letting REST,
MCP, and chat dispatch consume it without depending on Tk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.episode.schema import (
    Episode, DialogueBeat, EmotionBeat, PoseBeat, AnimBeat,
    WaitBeat, SceneBeat,
)


def scene_to_episode(scene_dict: dict[str, Any]) -> Episode:
    """Convert a SceneDocument dict into an Episode."""
    sid = str(scene_dict.get("id") or scene_dict.get("name") or "scene")
    title = str(scene_dict.get("name") or sid)
    cast_raw = scene_dict.get("characters") or []
    cast = [str(c.get("id") if isinstance(c, dict) else c) for c in cast_raw]
    scene_id = str(scene_dict.get("environment", {}).get("id") if isinstance(scene_dict.get("environment"), dict) else "")

    beats: list[Any] = []
    if scene_id:
        beats.append(SceneBeat(scene=scene_id, transition="cut"))

    for clip in scene_dict.get("clips", []) or []:
        if not clip.get("enabled", True):
            continue
        cam = clip.get("camera", {}) or {}
        if cam.get("transition") and cam.get("transition") != "cut":
            beats.append(SceneBeat(scene=scene_id, transition=str(cam["transition"])))
        for beat in clip.get("beats", []) or []:
            target = str(beat.get("target", "onyx"))
            if beat.get("emotion"):
                beats.append(EmotionBeat(emotion=str(beat["emotion"]), who=target))
            if beat.get("pose"):
                beats.append(PoseBeat(pose=str(beat["pose"]), who=target))
            if beat.get("body_anim"):
                beats.append(AnimBeat(anim=str(beat["body_anim"]), who=target))
            if beat.get("dialogue"):
                beats.append(DialogueBeat(say=str(beat["dialogue"]), who=target))
            elif beat.get("duration", 0):
                ms = int(float(beat["duration"]) * 1000)
                beats.append(WaitBeat(wait_ms=ms))

    return Episode(
        id=sid,
        title=title,
        cast=cast,
        scene=scene_id,
        beats=beats,
        description=str(scene_dict.get("description", "")),
    )


def load_scene_as_episode(path: Path) -> Episode:
    """Load a .pen / .json SceneDocument file and adapt it to Episode."""
    import json
    text = path.read_text(encoding="utf-8")
    # SceneDocument files may be wrapped; try direct JSON first.
    data = json.loads(text)
    return scene_to_episode(data)
