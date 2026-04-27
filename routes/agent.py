"""Agent routes — goal submission, status, history, run, queue, skills, memory."""

import asyncio
import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from routes._state import state, run_goal_sync, run_task_sync

router = APIRouter()


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class GoalRequest(BaseModel):
    goal: str = Field(..., description="The high-level goal for OnyxKraken to accomplish")
    app_name: str = Field(default="unknown", description="Target application name")


class GoalResponse(BaseModel):
    status: str
    goal: str
    message: str


class TaskHistoryItem(BaseModel):
    goal: str
    app: str
    steps_planned: int
    steps_completed: int
    total_time: float
    success: bool
    notes: str = ""
    timestamp: float = 0.0


class RunRequest(BaseModel):
    task: str
    context: str = ""
    channel_id: str = "default"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    return {"status": "ok", "agent": "OnyxKraken", "version": "2.0.0"}


@router.post("/goal", response_model=GoalResponse)
async def submit_goal(req: GoalRequest):
    """Submit a goal for the agent to execute (async — returns immediately)."""
    if state.running:
        raise HTTPException(
            status_code=409,
            detail=f"Agent is busy with: {state.current_goal}"
        )

    state.start(req.goal)
    threading.Thread(
        target=run_goal_sync,
        args=(req.goal, req.app_name),
        daemon=True,
    ).start()

    return GoalResponse(
        status="accepted",
        goal=req.goal,
        message="Goal submitted. Check /status for progress.",
    )


@router.get("/status")
async def get_status():
    """Get current agent status."""
    return state.to_dict()


@router.get("/history")
async def get_history(limit: int = 20):
    """Get task history from memory."""
    from memory.store import MemoryStore
    memory = MemoryStore()
    tasks = memory.get_all().get("task_history", [])
    return {
        "total": len(tasks),
        "tasks": tasks[-limit:],
    }


@router.post("/run")
async def run_task(req: RunRequest):
    """Execute a task and return the result.

    This is the endpoint the Discord bot calls. Runs the orchestrator in a
    background thread so the FastAPI event loop stays responsive.
    """
    if state.running:
        return {"result": f"Agent is busy with: {state.current_goal}"}

    return await asyncio.to_thread(run_task_sync, req.task)


@router.get("/queue")
async def get_queue():
    """Get queued goals from the autonomy daemon."""
    try:
        from core.autonomy import get_daemon
        daemon = get_daemon()
        stats = daemon.get_stats()
        return {"tasks": stats.get("recent_log", []), "queue_size": stats.get("queue_size", 0)}
    except Exception as e:
        import logging
        logging.getLogger("server").debug(f"Could not fetch daemon queue: {e}")
        return {"tasks": [], "queue_size": 0}


@router.get("/skills")
async def get_skills():
    """List available agent capabilities."""
    from agent.action_dispatch import get_registered_actions
    actions = get_registered_actions()
    skills = [
        {"name": a, "description": f"Execute '{a}' action on the desktop"}
        for a in sorted(actions)
    ]
    return {"skills": skills}


@router.get("/memory")
async def get_memory():
    """Get full memory store contents."""
    from memory.store import MemoryStore
    memory = MemoryStore()
    return memory.get_all()
