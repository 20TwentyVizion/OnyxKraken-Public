"""Tests for new core systems — self-improvement, knowledge, embeddings, autonomy."""

import json
import os
import tempfile
import pytest

# ---------------------------------------------------------------------------
# Knowledge store
# ---------------------------------------------------------------------------

def test_knowledge_add_and_search():
    from core.knowledge import KnowledgeStore
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        ks = KnowledgeStore(path=path)
        ks.add("Notepad uses File menu for saving", category="app_knowledge", tags=["notepad"])
        ks.add("Blender requires bpy for scripting", category="app_knowledge", tags=["blender"])
        ks.add("Always check accessibility tree before clicking", category="task_patterns")

        results = ks.search("Notepad File menu", category="app_knowledge")
        assert len(results) > 0
        assert "Notepad" in results[0]["content"]

        results = ks.search("scripting", tags=["blender"])
        assert len(results) > 0

        stats = ks.get_stats()
        assert stats["total_entries"] == 3
    finally:
        os.unlink(path)


def test_knowledge_remove():
    from core.knowledge import KnowledgeStore
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        ks = KnowledgeStore(path=path)
        entry_id = ks.add("temporary fact")
        assert len(ks.get_all()) == 1
        assert ks.remove(entry_id)
        assert len(ks.get_all()) == 0
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Self-improvement engine
# ---------------------------------------------------------------------------

def test_self_improvement_record_failure():
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
        engine.record_failure(
            goal="Open unknown app",
            error="Window not found",
            app_name="unknown_app",
            actions_tried=["launch", "interact"],
        )
        assert len(engine._store.data["failed_tasks"]) == 1
        f = engine._store.data["failed_tasks"][0]
        assert f["goal"] == "Open unknown app"
        assert not f["analyzed"]
    finally:
        os.unlink(path)


def test_self_improvement_stats():
    from core.self_improvement import SelfImprovementEngine
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        engine = SelfImprovementEngine()
        engine._store.path = path
        engine._store._data = {
            "failed_tasks": [{"analyzed": False}, {"analyzed": True}],
            "skill_gaps": [{"resolved": False}, {"resolved": True}],
            "generated_modules": [],
            "improvement_runs": [{}],
            "stats": {
                "total_failures_analyzed": 1, "total_gaps_identified": 2,
                "total_modules_generated": 0, "total_modules_deployed": 0,
            }
        }
        stats = engine.get_stats()
        assert stats["unanalyzed_failures"] == 1
        assert stats["unresolved_gaps"] == 1
        assert stats["total_improvement_runs"] == 1
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Autonomy daemon
# ---------------------------------------------------------------------------

def test_daemon_lifecycle():
    from core.autonomy import AutonomyDaemon, DaemonState
    # Use long improve_interval to prevent self-improvement from firing during test
    daemon = AutonomyDaemon(check_interval=0.1, improve_interval=9999)
    assert daemon.state == DaemonState.STOPPED

    daemon.start()
    import time; time.sleep(0.15)  # let thread spin up
    assert daemon.state == DaemonState.IDLE

    daemon.pause()
    assert daemon.state == DaemonState.PAUSED

    daemon.resume()
    assert daemon.state == DaemonState.IDLE

    daemon.stop()
    assert daemon.state == DaemonState.STOPPED


def test_daemon_queue():
    from core.autonomy import AutonomyDaemon
    daemon = AutonomyDaemon()
    daemon.queue_goal("test goal 1", priority=1)
    daemon.queue_goal("test goal 2", priority=5)
    assert daemon.queue_size() == 2

    stats = daemon.get_stats()
    assert stats["queue_size"] == 2


# ---------------------------------------------------------------------------
# Embeddings (graceful fallback)
# ---------------------------------------------------------------------------

def test_embeddings_cosine_similarity():
    from memory.embeddings import _cosine_similarity
    assert _cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
    assert _cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)
    assert _cosine_similarity([1, 0, 0], [-1, 0, 0]) == pytest.approx(-1.0)
    assert _cosine_similarity([], []) == 0.0


def test_embedding_store_cache():
    from memory.embeddings import EmbeddingStore
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        store = EmbeddingStore(cache_path=path)
        # Manually inject a cache entry
        store._cache["test:hello"] = [0.1, 0.2, 0.3]
        store.flush_cache()

        # Reload and verify
        store2 = EmbeddingStore(cache_path=path)
        assert "test:hello" in store2._cache
        assert store2._cache["test:hello"] == [0.1, 0.2, 0.3]
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Action dispatch registry
# ---------------------------------------------------------------------------

def test_action_dispatch_registry():
    from agent.action_dispatch import execute_action
    # Test 'done' action
    result = execute_action({"action": "done", "target": "", "params": {"reason": "test"}})
    assert "complete" in result.lower() or "test" in result.lower()

    # Test 'fail' action
    result = execute_action({"action": "fail", "target": "", "params": {"reason": "test fail"}})
    assert "fail" in result.lower()

    # Test 'wait' action
    import time
    start = time.time()
    result = execute_action({"action": "wait", "target": "", "params": {"seconds": 0.1}})
    assert time.time() - start >= 0.1
    assert "wait" in result.lower() or "0.1" in result

    # Test unknown action
    result = execute_action({"action": "nonexistent_xyz", "target": "", "params": {}})
    assert "unknown" in result.lower() or "no handler" in result.lower()


# ---------------------------------------------------------------------------
# Planner / classify_step
# ---------------------------------------------------------------------------

def test_classify_step_filesystem():
    from agent.planner import classify_step
    r = classify_step("Write the file directly")
    assert r["type"] == "filesystem"

    r = classify_step("Run python script to compute result")
    assert r["type"] == "filesystem"

    r = classify_step("Execute command to list files")
    assert r["type"] == "filesystem"

    r = classify_step("Calculate the factorial using python")
    assert r["type"] == "filesystem"
