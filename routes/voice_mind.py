"""Voice & Mind routes — speech I/O and mind state/reflection."""

import threading

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from routes._state import state, run_goal_sync

router = APIRouter()


# ---------------------------------------------------------------------------
# Voice endpoints
# ---------------------------------------------------------------------------

@router.post("/voice/listen")
async def voice_listen(duration: float = 5.0):
    """Record from microphone and transcribe."""
    from core.voice import listen
    text = listen(duration=duration)
    if text:
        return {"text": text, "status": "ok"}
    return {"text": None, "status": "no_speech_detected"}


class SpeakRequest(BaseModel):
    text: str


@router.post("/voice/speak")
async def voice_speak(req: SpeakRequest, background_tasks: BackgroundTasks):
    """Synthesize and play speech."""
    from core.voice import speak
    background_tasks.add_task(speak, req.text)
    return {"status": "speaking", "text": req.text[:100]}


@router.post("/voice/goal")
async def voice_goal(duration: float = 5.0):
    """Listen for a voice command and submit it as a goal."""
    from core.voice import listen
    text = listen(duration=duration)
    if not text:
        return {"status": "no_speech_detected", "text": None}

    if state.running:
        raise HTTPException(status_code=409, detail=f"Agent busy with: {state.current_goal}")

    state.start(text)
    threading.Thread(
        target=run_goal_sync,
        args=(text, "unknown"),
        daemon=True,
    ).start()

    return {"status": "accepted", "goal": text, "message": "Voice goal submitted."}


# ---------------------------------------------------------------------------
# Mind endpoints
# ---------------------------------------------------------------------------

@router.get("/mind")
async def get_mind_state():
    """Get the Mind's current state — identity, mood, focus, strengths/weaknesses."""
    from core.mind import get_mind
    mind = get_mind()
    return mind.get_stats()


@router.post("/mind/reflect")
async def mind_reflect():
    """Trigger a reflection cycle."""
    def _run():
        from core.mind import get_mind
        return get_mind().reflect()
    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started", "message": "Reflection cycle initiated."}


@router.post("/mind/goal")
async def mind_proactive_goal():
    """Ask the Mind to generate a proactive goal."""
    from core.mind import get_mind
    mind = get_mind()
    goal = mind.generate_proactive_goal()
    if goal:
        return {"goal": goal, "status": "generated"}
    return {"goal": None, "status": "rest", "message": "Mind decided to rest."}
