"""Drive routes — programmatic control over face emotion, body pose, and
animation playback.

Endpoints:
  POST /drive/face/emotion         body: {character, emotion, intensity, hold_ms}
  POST /drive/character/pose       body: {character, pose, transition_ms}
  POST /drive/animation/play       body: {character, animation, loop}
  POST /drive/speak                body: {character, text, mood, classify}
  POST /drive/episode/play         body: {episode_id, vars?}
  POST /drive/stop                 body: {character?}
  GET  /drive/catalog              full catalog (emotions, poses, anims, characters)
  GET  /drive/recent                last drive events (debug)
  WS   /drive/stream                live stream of drive events for renderers

Other ecosystem projects can call these endpoints to drive an Onyx character
in their own UI without depending on the desktop GUI.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from core.animation import get_catalog
from core.characters import get_registry
from core.drive import DriveEvent, get_bus
from core.intent import classify

router = APIRouter(prefix="/drive", tags=["drive"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class EmotionRequest(BaseModel):
    character: str = "onyx"
    emotion: str = "neutral"
    intensity: float = Field(default=1.0, ge=0.0, le=1.0)
    hold_ms: int = Field(default=0, ge=0)
    mix: Optional[dict[str, float]] = None  # blend multiple emotions by weight


class PoseRequest(BaseModel):
    character: str = "onyx"
    pose: str
    transition_ms: int = Field(default=300, ge=0)


class AnimRequest(BaseModel):
    character: str = "onyx"
    animation: str
    loop: bool = False


class SpeakRequest(BaseModel):
    character: str = "onyx"
    text: str
    mood: str = "ready"
    classify: bool = True   # if True, pass text through intent classifier
    auto_pose: bool = True  # if True, dispatch pose+anim from emotion link


class EpisodeRequest(BaseModel):
    episode_id: str
    vars: Optional[dict] = None


class StopRequest(BaseModel):
    character: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_character(name: str) -> str:
    char = get_registry().get(name)
    if char is None:
        raise HTTPException(404, f"Unknown character: {name!r}")
    return char.id


def _publish(kind: str, character: str, source: str, **payload) -> dict:
    event = DriveEvent(kind=kind, character=character, payload=payload, source=source)
    get_bus().publish(event)
    return {"ok": True, "event": event.to_dict()}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/face/emotion")
async def drive_face_emotion(req: EmotionRequest) -> dict:
    cid = _require_character(req.character)
    catalog = get_catalog()
    payload: dict = {
        "emotion": req.emotion,
        "intensity": req.intensity,
        "hold_ms": req.hold_ms,
    }
    if req.mix:
        unknown = [e for e in req.mix if catalog.emotion(e) is None]
        if unknown:
            raise HTTPException(400, f"Unknown emotion(s) in mix: {unknown}")
        payload["mix"] = {k: float(v) for k, v in req.mix.items() if v > 0}
        # dominant becomes the announced emotion name
        payload["emotion"] = max(payload["mix"], key=payload["mix"].get)
    elif catalog.emotion(req.emotion) is None:
        raise HTTPException(400, f"Unknown emotion: {req.emotion!r}")
    return _publish("emotion", cid, "rest", **payload)


@router.post("/character/pose")
async def drive_character_pose(req: PoseRequest) -> dict:
    cid = _require_character(req.character)
    if get_catalog().pose(req.pose) is None:
        raise HTTPException(400, f"Unknown pose: {req.pose!r}")
    return _publish(
        "pose", cid, "rest",
        pose=req.pose, transition_ms=req.transition_ms,
    )


@router.post("/animation/play")
async def drive_animation_play(req: AnimRequest) -> dict:
    cid = _require_character(req.character)
    if get_catalog().body_anim(req.animation) is None:
        raise HTTPException(400, f"Unknown animation: {req.animation!r}")
    return _publish(
        "body_anim", cid, "rest",
        animation=req.animation, loop=req.loop,
    )


@router.post("/speak")
async def drive_speak(req: SpeakRequest) -> dict:
    cid = _require_character(req.character)
    text = req.text
    emotions: list[str] = []
    poses: list[str] = []
    anims: list[str] = []

    if req.classify:
        result = classify(text)
        text = result.clean_text
        emotions = result.emotions
        poses = result.poses
        anims = result.body_anims

    # Publish a speak event first; renderers pair it with mouth phonemes.
    _publish("speak", cid, "rest", text=text, mood=req.mood, original=req.text)

    # Then dispatch face/body cues. Auto-pose pulls pose+anim from the
    # emotion link if no explicit cue was given.
    catalog = get_catalog()
    primary = emotions[0] if emotions else None
    if primary:
        _publish("emotion", cid, "rest", emotion=primary, intensity=1.0, hold_ms=0)
        if req.auto_pose:
            link_pose, link_anim = catalog.link_for(primary)
            if link_pose and not poses:
                poses = [link_pose]
            if link_anim and not anims:
                anims = [link_anim]
    for p in poses:
        if catalog.pose(p):
            _publish("pose", cid, "rest", pose=p, transition_ms=300)
    for a in anims:
        if catalog.body_anim(a):
            _publish("body_anim", cid, "rest", animation=a, loop=False)

    return {
        "ok": True,
        "clean_text": text,
        "emotions": emotions,
        "poses": poses,
        "body_anims": anims,
    }


@router.post("/episode/play")
async def drive_episode_play(req: EpisodeRequest) -> dict:
    try:
        from core.episode.player import play_episode
    except Exception as e:
        raise HTTPException(503, f"Episode player unavailable: {e}")
    return play_episode(req.episode_id, vars=req.vars or {})


@router.post("/stop")
async def drive_stop(req: StopRequest) -> dict:
    return _publish("stop", req.character or "*", "rest")


@router.get("/catalog")
async def drive_catalog() -> dict:
    return {
        "catalog": get_catalog().to_dict(),
        "characters": [c.to_dict() for c in get_registry().all()],
    }


@router.get("/recent")
async def drive_recent(limit: int = 20) -> dict:
    return {"events": [e.to_dict() for e in get_bus().recent(limit)]}


@router.websocket("/stream")
async def drive_stream(ws: WebSocket) -> None:
    await ws.accept()
    queue, unsub = get_bus().subscribe_async()
    try:
        # Send a hello so clients know they're connected.
        await ws.send_json({"kind": "hello", "ts": 0, "payload": {}})
        while True:
            event = await queue.get()
            await ws.send_json(event.to_dict())
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        unsub()
