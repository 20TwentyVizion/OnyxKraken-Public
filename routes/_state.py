"""Shared agent state and goal-execution helpers used across route modules."""

import logging
import threading
import time
from typing import Optional

_log = logging.getLogger("server")


class AgentState:
    """Tracks current agent status across async requests."""

    def __init__(self):
        self.running = False
        self.current_goal: str = ""
        self.current_step: str = ""
        self.started_at: float = 0.0
        self.last_result: Optional[dict] = None
        self._lock = threading.Lock()

    def start(self, goal: str):
        with self._lock:
            self.running = True
            self.current_goal = goal
            self.current_step = "planning"
            self.started_at = time.time()

    def finish(self, result: dict):
        with self._lock:
            self.running = False
            self.current_step = ""
            self.last_result = result

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "current_goal": self.current_goal,
                "current_step": self.current_step,
                "uptime": round(time.time() - self.started_at, 1) if self.running else 0,
                "last_result": self.last_result,
            }


state = AgentState()


def run_goal_sync(goal: str, app_name: str):
    """Run the orchestrator synchronously in a background thread."""
    try:
        from agent.orchestrator import run
        result = run(goal, app_name=app_name, headless=True)
        state.finish({
            "goal": result.goal,
            "app_name": result.app_name,
            "steps_planned": result.steps_planned,
            "steps_completed": result.steps_completed,
            "total_actions": result.total_actions,
            "total_time": round(result.total_time, 1),
            "success": not result.aborted and result.steps_completed == result.steps_planned,
            "aborted": result.aborted,
            "failure_reason": result.failure_reason,
            "success_rate": round(result.success_rate, 2),
        })
    except Exception as e:
        state.finish({
            "goal": goal,
            "error": str(e),
            "success": False,
        })


def run_task_sync(task: str) -> dict:
    """Execute a task synchronously. Called from a thread to avoid blocking the event loop."""
    state.start(task)
    try:
        from agent.orchestrator import run  # noqa: E402

        # Infer app name
        app_name = "unknown"
        try:
            from apps.registry import discover_modules, list_modules
            discover_modules()
            for mod_name in list_modules():
                if mod_name.lower() in task.lower():
                    app_name = mod_name
                    break
        except Exception as e:
            _log.debug(f"Module discovery failed (non-critical): {e}")

        result = run(task, app_name=app_name, headless=True)
        success = not result.aborted and result.steps_completed == result.steps_planned

        result_dict = {
            "goal": result.goal,
            "app_name": result.app_name,
            "steps_planned": result.steps_planned,
            "steps_completed": result.steps_completed,
            "total_actions": result.total_actions,
            "total_time": round(result.total_time, 1),
            "success": success,
            "failure_reason": result.failure_reason,
        }
        state.finish(result_dict)

        if success:
            return {"result": f"Goal completed in {result.total_time:.1f}s ({result.total_actions} actions, {result.steps_completed}/{result.steps_planned} steps)"}
        else:
            reason = result.failure_reason or f"{result.steps_completed}/{result.steps_planned} steps completed"
            return {"result": f"Goal failed: {reason}"}

    except Exception as e:
        state.finish({"goal": task, "error": str(e), "success": False})
        return {"result": f"Error: {str(e)}"}
