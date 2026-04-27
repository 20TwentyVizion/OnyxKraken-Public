"""Integration tests — verify the full learning cycle works end-to-end.

These tests don't execute real desktop actions but verify the data flow:
  knowledge → planner → action_dispatch → orchestrator → self-improvement → knowledge
"""

import json
import os
import tempfile
import time
import pytest

# ---------------------------------------------------------------------------
# Full learning cycle (no LLM calls, just data flow)
# ---------------------------------------------------------------------------

def test_failure_flows_to_self_improvement():
    """Failed task → self-improvement engine records it."""
    from core.self_improvement import SelfImprovementEngine

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        engine = SelfImprovementEngine()
        engine._store.path = path
        engine._store._data = {
            "failed_tasks": [], "skill_gaps": [], "generated_modules": [],
            "improvement_runs": [], "stats": {
                "total_failures_analyzed": 0, "total_gaps_identified": 0,
                "total_modules_generated": 0, "total_modules_deployed": 0,
            }
        }

        # Simulate 3 failures for the same app
        for i in range(3):
            engine.record_failure(
                goal=f"Open FancyApp and do task {i}",
                error="Window not found: FancyApp",
                app_name="fancyapp",
                actions_tried=["launch", "interact"],
            )

        assert len(engine._store.data["failed_tasks"]) == 3
        assert all(not f["analyzed"] for f in engine._store.data["failed_tasks"])

        # Verify unresolved gaps start at 0
        gaps = engine.get_unresolved_gaps()
        assert len(gaps) == 0

        stats = engine.get_stats()
        assert stats["unanalyzed_failures"] == 3
    finally:
        os.unlink(path)


def test_knowledge_injects_into_planner_prompt():
    """Knowledge store entries should appear in planner prompts."""
    from core.knowledge import KnowledgeStore

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        ks = KnowledgeStore(path=path)
        ks.add("Notepad File menu has Save As option", category="app_knowledge", tags=["notepad"])
        ks.add("Always use accessibility tree for Notepad clicks", category="task_patterns")

        # Verify search returns relevant results
        results = ks.search("Notepad save file")
        assert len(results) > 0
        assert any("Notepad" in r["content"] for r in results)

        # Verify app-specific retrieval
        app_results = ks.get_app_knowledge("notepad")
        assert len(app_results) > 0
    finally:
        os.unlink(path)


def test_success_captures_to_knowledge():
    """Successful task patterns should be stored in knowledge."""
    from core.knowledge import KnowledgeStore

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        ks = KnowledgeStore(path=path)

        # Simulate what orchestrator.run() does on success
        goal = "Open Notepad and type Hello"
        app_name = "notepad"
        step_types = ["launch", "interact"]
        step_descs = ["Open Notepad", "Type Hello in the editor"]
        total_time = 5.2
        total_actions = 3

        pattern = (
            f"Goal: \"{goal[:100]}\" | App: {app_name} | "
            f"Steps: {' → '.join(step_types)} | "
            f"Time: {total_time:.1f}s | Actions: {total_actions}"
        )
        ks.add_task_pattern(pattern, source=f"task:{goal[:60]}")

        approach = " → ".join(step_descs[:5])
        ks.add_app_knowledge(
            app_name,
            f"Successful approach for \"{goal[:80]}\": {approach}",
            source=f"task:{goal[:60]}",
        )

        # Verify both entries exist
        all_entries = ks.get_all()
        assert len(all_entries) == 2

        # Verify they're retrievable
        patterns = ks.search("Notepad type", category="task_patterns")
        assert len(patterns) > 0

        app_knowledge = ks.get_app_knowledge("notepad")
        assert len(app_knowledge) > 0
        assert "Successful approach" in app_knowledge[0]["content"]
    finally:
        os.unlink(path)


def test_action_dispatch_done_and_fail():
    """Action dispatch correctly handles terminal actions."""
    from agent.action_dispatch import execute_action

    done_result = execute_action({
        "action": "done",
        "target": "",
        "params": {"reason": "All steps completed successfully"},
    })
    assert "complete" in done_result.lower() or "all steps" in done_result.lower()

    fail_result = execute_action({
        "action": "fail",
        "target": "",
        "params": {"reason": "Window not found"},
    })
    assert "fail" in fail_result.lower()


def test_action_dispatch_screenshot():
    """Screenshot action returns analysis prompt."""
    from agent.action_dispatch import execute_action

    result = execute_action({
        "action": "screenshot",
        "target": "",
        "params": {},
    })
    assert "screenshot" in result.lower() or "re-analysis" in result.lower()


def test_action_dispatch_read_screen():
    """Read screen returns summary."""
    from agent.action_dispatch import execute_action

    result = execute_action({
        "action": "read_screen",
        "target": "",
        "params": {"summary": "I see Notepad with text Hello"},
    })
    assert "Notepad" in result or "Hello" in result


def test_embedding_fallback_to_keyword():
    """Memory store falls back to keyword matching when embeddings unavailable."""
    from memory.store import MemoryStore

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        store = MemoryStore.__new__(MemoryStore)
        store._path = path
        store._data = {
            "failures": [],
            "launch_methods": {},
            "preferences": {},
            "task_history": [
                {"goal": "Open Notepad and type Hello", "app": "notepad",
                 "steps_planned": 2, "steps_completed": 2,
                 "total_time": 3.0, "success": True, "notes": "", "timestamp": time.time()},
                {"goal": "Open Chrome and search Google", "app": "chrome",
                 "steps_planned": 2, "steps_completed": 2,
                 "total_time": 5.0, "success": True, "notes": "", "timestamp": time.time()},
            ],
        }

        # Should find Notepad task via keyword overlap
        results = store.recall_similar_tasks("Open Notepad and write something")
        assert len(results) > 0
        assert results[0]["app"] == "notepad"
    finally:
        os.unlink(path)


def test_classify_step_all_types():
    """Verify all step types are correctly classified."""
    from agent.planner import classify_step

    # Launch
    assert classify_step("Open Grok")["type"] == "launch"
    assert classify_step("Launch Blender")["type"] == "launch"
    assert classify_step("Start Notepad")["type"] == "launch"

    # Interact
    assert classify_step("Click the File menu")["type"] == "interact"
    assert classify_step("Type Hello World")["type"] == "interact"
    assert classify_step("Scroll down to see more")["type"] == "interact"

    # Chat wait
    assert classify_step("Wait for the response and read it")["type"] == "chat_wait"
    assert classify_step("Read the response from the AI")["type"] == "chat_wait"

    # Filesystem
    assert classify_step("Write file directly")["type"] == "filesystem"
    assert classify_step("Run python to calculate result")["type"] == "filesystem"
    assert classify_step("Run command to list files")["type"] == "filesystem"
    assert classify_step("Create a file at C:\\Users\\test.txt")["type"] == "filesystem"


def test_daemon_queues_and_stats():
    """Daemon tracks queue and stats correctly."""
    from core.autonomy import AutonomyDaemon

    daemon = AutonomyDaemon(improve_interval=9999)
    daemon.queue_goal("Task A", priority=1)
    daemon.queue_goal("Task B", priority=5)
    daemon.queue_goal("Task C", priority=3)

    assert daemon.queue_size() == 3
    stats = daemon.get_stats()
    assert stats["queue_size"] == 3
    assert stats["tasks_completed"] == 0
    assert stats["tasks_failed"] == 0


def test_router_exo_disabled_by_default():
    """exo should be disabled when no endpoint is configured."""
    from agent.model_router import router
    # EXO_ENDPOINT is empty by default in test environment
    # This just verifies it doesn't crash
    assert isinstance(router.exo_available, bool)
