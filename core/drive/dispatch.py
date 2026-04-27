"""High-level chat → drive dispatcher.

Single entry point that takes a spoken line and publishes face emotion,
body pose, and body animation events on the DriveBus. Used by:
  - face/backend.py BackendBridge (when TTS speaks)
  - REST POST /drive/speak
  - MCP drive_speak tool
  - EpisodePlayer DialogueBeat handler

Keeps every channel speaking the same vocabulary so adding a new chat
surface (e.g. Discord, Slack) is one function call, not a re-implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.animation import get_catalog
from core.drive import DriveEvent, get_bus
from core.intent import classify, IntentResult


@dataclass
class DispatchResult:
    clean_text: str
    primary_emotion: str | None
    emotions: list[str]
    poses: list[str]
    body_anims: list[str]


def dispatch_line(
    text: str,
    character: str = "onyx",
    mood: str = "ready",
    auto_pose: bool = True,
    source: str = "chat",
    publish_speak: bool = True,
) -> DispatchResult:
    """Classify text and publish face/body/speak events.

    Args:
        text: Raw line (may contain *action* roleplay tags).
        character: Character id whose channel to drive.
        mood: TTS voice mood.
        auto_pose: Pull pose+anim from emotion link if no explicit cue.
        source: Tag for the drive event (chat, episode, mcp, rest...).
        publish_speak: If False, skip the "speak" event (caller will TTS).

    Returns: DispatchResult so the caller can use the clean text for TTS.
    """
    result: IntentResult = classify(text)
    bus = get_bus()
    catalog = get_catalog()
    cid = character.lower()

    if publish_speak:
        bus.publish(DriveEvent(
            kind="speak", character=cid, source=source,
            payload={"text": result.clean_text, "mood": mood, "original": text},
        ))

    primary = result.primary_emotion
    if primary:
        bus.publish(DriveEvent(
            kind="emotion", character=cid, source=source,
            payload={"emotion": primary, "intensity": 1.0, "hold_ms": 0},
        ))
        if auto_pose:
            link_pose, link_anim = catalog.link_for(primary)
            if link_pose and not result.poses:
                result.poses.append(link_pose)
            if link_anim and not result.body_anims:
                result.body_anims.append(link_anim)

    for p in result.poses:
        if catalog.pose(p):
            bus.publish(DriveEvent(
                kind="pose", character=cid, source=source,
                payload={"pose": p, "transition_ms": 300},
            ))
    for a in result.body_anims:
        if catalog.body_anim(a):
            bus.publish(DriveEvent(
                kind="body_anim", character=cid, source=source,
                payload={"animation": a, "loop": False},
            ))

    return DispatchResult(
        clean_text=result.clean_text,
        primary_emotion=primary,
        emotions=result.emotions,
        poses=result.poses,
        body_anims=result.body_anims,
    )
