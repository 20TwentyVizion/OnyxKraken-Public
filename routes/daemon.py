"""Daemon routes — start/stop/pause/resume, focus, goal queue, stats, improve."""

import threading
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


# ---------------------------------------------------------------------------
# Daemon control
# ---------------------------------------------------------------------------

@router.post("/daemon/start")
async def daemon_start():
    """Start the autonomy daemon."""
    from core.autonomy import get_daemon
    daemon = get_daemon()
    daemon.start()
    return {"status": daemon.state}


@router.post("/daemon/stop")
async def daemon_stop():
    """Stop the autonomy daemon."""
    from core.autonomy import get_daemon
    daemon = get_daemon()
    daemon.stop()
    return {"status": daemon.state}


@router.post("/daemon/pause")
async def daemon_pause():
    """Pause the autonomy daemon."""
    from core.autonomy import get_daemon
    daemon = get_daemon()
    daemon.pause()
    return {"status": daemon.state}


@router.post("/daemon/resume")
async def daemon_resume():
    """Resume the autonomy daemon."""
    from core.autonomy import get_daemon
    daemon = get_daemon()
    daemon.resume()
    return {"status": daemon.state}


class DaemonGoalRequest(BaseModel):
    goal: str
    app_name: str = "unknown"
    priority: int = 0


@router.post("/daemon/goal")
async def daemon_queue_goal(req: DaemonGoalRequest):
    """Queue a goal for background execution."""
    from core.autonomy import get_daemon
    daemon = get_daemon()
    daemon.queue_goal(req.goal, app_name=req.app_name, priority=req.priority)
    return {"status": "queued", "queue_size": daemon.queue_size()}


@router.get("/daemon/stats")
async def daemon_stats():
    """Get autonomy daemon statistics."""
    from core.autonomy import get_daemon
    daemon = get_daemon()
    return daemon.get_stats()


class TrainingFocusRequest(BaseModel):
    focus: Optional[str] = Field(
        None,
        description="Training focus domain (e.g. 'blender'). Null to clear.",
    )


@router.post("/daemon/focus")
async def daemon_set_focus(req: TrainingFocusRequest):
    """Set or clear the daemon's training focus."""
    from core.autonomy import get_daemon
    daemon = get_daemon()
    daemon.set_training_focus(req.focus)
    return {
        "training_focus": daemon.training_focus,
        "status": "focus_set" if daemon.training_focus else "focus_cleared",
    }


@router.get("/daemon/focus")
async def daemon_get_focus():
    """Get the current training focus."""
    from core.autonomy import get_daemon
    daemon = get_daemon()
    return {"training_focus": daemon.training_focus}


# ---------------------------------------------------------------------------
# Self-improvement
# ---------------------------------------------------------------------------

@router.post("/improve")
async def run_improvement():
    """Trigger a self-improvement cycle."""
    def _run():
        from core.self_improvement import get_improvement_engine
        engine = get_improvement_engine()
        return engine.run_improvement_cycle()

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started", "message": "Self-improvement cycle initiated."}


@router.get("/improve/stats")
async def improvement_stats():
    """Get self-improvement statistics."""
    from core.self_improvement import get_improvement_engine
    engine = get_improvement_engine()
    return engine.get_stats()


@router.get("/improve/gaps")
async def improvement_gaps():
    """Get unresolved capability gaps."""
    from core.self_improvement import get_improvement_engine
    engine = get_improvement_engine()
    return {"gaps": engine.get_unresolved_gaps()}
