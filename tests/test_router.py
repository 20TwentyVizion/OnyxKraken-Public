"""Test the ModelRouter configuration and compilation."""

import config
from log import setup_logging
setup_logging(config.LOG_LEVEL)

from agent.model_router import router


def test_router_has_all_task_types():
    for task_type in ("vision", "planner", "reasoning", "filesystem"):
        primary = router.get_primary(task_type)
        assert primary, f"No primary model for {task_type}"


def test_router_fallbacks_exist():
    for task_type in ("vision", "planner", "reasoning"):
        fallback = router.get_fallback(task_type)
        assert fallback, f"No fallback model for {task_type}"


def test_orchestrator_imports():
    from agent.orchestrator import run, TaskResult
    assert callable(run)
    assert TaskResult is not None
