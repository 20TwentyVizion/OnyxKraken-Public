"""Tests for the Onyx Ecosystem — dispatch, workflows, parallel, quality gates, scheduler."""

import time
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Service registry tests
# ---------------------------------------------------------------------------

def test_services_registered():
    from apps.onyx_ecosystem import SERVICES
    assert "blakvision" in SERVICES
    assert "evera" in SERVICES
    assert "gamekree8r" in SERVICES
    assert "worldbuild" in SERVICES
    assert "justedit" in SERVICES
    assert "blender" in SERVICES
    assert len(SERVICES) == 6


def test_service_info_fields():
    from apps.onyx_ecosystem import SERVICES
    bv = SERVICES["blakvision"]
    assert bv.name == "BlakVision"
    assert bv.port == 8188
    assert bv.category == "media"
    assert "text-to-image" in bv.capabilities
    assert bv.health_action == "blakvision_status"


def test_capabilities_grouped():
    from apps.onyx_ecosystem import get_ecosystem
    eco = get_ecosystem()
    caps = eco.list_capabilities()
    assert "media" in caps
    assert "creative" in caps
    assert "writing" in caps
    media_names = [s["service"] for s in caps["media"]]
    assert "blakvision" in media_names
    assert "evera" in media_names


# ---------------------------------------------------------------------------
# Dispatch tests (mocked modules)
# ---------------------------------------------------------------------------

def test_dispatch_unknown_service():
    from apps.onyx_ecosystem import OnyxEcosystem
    eco = OnyxEcosystem()
    result = eco.dispatch("nonexistent", "nonexistent_do", {})
    assert result["ok"] is False
    assert "Unknown service" in result["error"]


def test_dispatch_routes_to_module():
    from apps.onyx_ecosystem import OnyxEcosystem
    eco = OnyxEcosystem()

    mock_mod = MagicMock()
    mock_mod.execute_action.return_value = {"ok": True, "data": "test"}
    eco._modules["blakvision"] = mock_mod

    result = eco.dispatch("blakvision", "blakvision_generate", {"prompt": "hello"})
    assert result["ok"] is True
    assert result["_service"] == "blakvision"
    assert result["_action"] == "blakvision_generate"
    assert "_elapsed" in result
    mock_mod.execute_action.assert_called_once_with("blakvision_generate", {"prompt": "hello"})


def test_dispatch_handles_exception():
    from apps.onyx_ecosystem import OnyxEcosystem
    eco = OnyxEcosystem()

    mock_mod = MagicMock()
    mock_mod.execute_action.side_effect = RuntimeError("connection refused")
    eco._modules["gamekree8r"] = mock_mod

    result = eco.dispatch("gamekree8r", "gamekree8r_status", {})
    assert result["ok"] is False
    assert "connection refused" in result["error"]


# ---------------------------------------------------------------------------
# Workflow execution tests
# ---------------------------------------------------------------------------

def _make_eco_with_mocks():
    """Create an ecosystem with mock modules that return ok=True."""
    from apps.onyx_ecosystem import OnyxEcosystem, SERVICES
    eco = OnyxEcosystem()
    for name in SERVICES:
        mock = MagicMock()
        mock.execute_action.return_value = {"ok": True, "output": f"mock_{name}"}
        eco._modules[name] = mock
    return eco


def test_workflow_sequential():
    eco = _make_eco_with_mocks()
    steps = [
        {"service": "worldbuild", "action": "worldbuild_outline", "params": {"title": "Test"}},
        {"service": "blakvision", "action": "blakvision_generate", "params": {"prompt": "cover"}},
    ]
    result = eco.run_workflow(steps)
    assert result["ok"] is True
    assert result["steps_total"] == 2
    assert result["steps_completed"] == 2
    assert result["steps_failed"] == 0


def test_workflow_aborts_on_failure():
    from apps.onyx_ecosystem import OnyxEcosystem, SERVICES
    eco = OnyxEcosystem()

    # First module succeeds, second fails
    mock_ok = MagicMock()
    mock_ok.execute_action.return_value = {"ok": True}
    mock_fail = MagicMock()
    mock_fail.execute_action.return_value = {"ok": False, "error": "down"}

    eco._modules["worldbuild"] = mock_ok
    eco._modules["blakvision"] = mock_fail
    eco._modules["evera"] = mock_ok

    steps = [
        {"service": "worldbuild", "action": "worldbuild_outline", "params": {}},
        {"service": "blakvision", "action": "blakvision_generate", "params": {}},
        {"service": "evera", "action": "evera_generate", "params": {}},
    ]
    result = eco.run_workflow(steps)
    assert result["ok"] is False
    assert result["steps_completed"] == 1  # Only first succeeded


def test_workflow_optional_step_doesnt_abort():
    from apps.onyx_ecosystem import OnyxEcosystem
    eco = OnyxEcosystem()

    mock_ok = MagicMock()
    mock_ok.execute_action.return_value = {"ok": True}
    mock_fail = MagicMock()
    mock_fail.execute_action.return_value = {"ok": False, "error": "skip"}

    eco._modules["worldbuild"] = mock_ok
    eco._modules["blakvision"] = mock_fail
    eco._modules["evera"] = mock_ok

    steps = [
        {"service": "worldbuild", "action": "worldbuild_outline", "params": {}},
        {"service": "blakvision", "action": "blakvision_generate", "params": {}, "optional": True},
        {"service": "evera", "action": "evera_generate", "params": {}},
    ]
    result = eco.run_workflow(steps)
    # 2 out of 3 succeeded, but the failed one was optional
    assert result["steps_completed"] == 2


# ---------------------------------------------------------------------------
# Parallel execution tests
# ---------------------------------------------------------------------------

def test_parallel_groups_detected():
    from apps.onyx_ecosystem import OnyxEcosystem
    eco = OnyxEcosystem()
    steps = [
        {"service": "a", "action": "a_1", "params": {}},
        {"service": "b", "action": "b_1", "params": {}, "parallel_group": "pg"},
        {"service": "c", "action": "c_1", "params": {}, "parallel_group": "pg"},
        {"service": "d", "action": "d_1", "params": {}},
    ]
    groups = eco._build_execution_groups(steps)
    assert len(groups) == 3  # [a_1], [b_1, c_1], [d_1]
    assert len(groups[0]) == 1
    assert len(groups[1]) == 2
    assert len(groups[2]) == 1


def test_parallel_execution():
    eco = _make_eco_with_mocks()
    steps = [
        {"service": "blakvision", "action": "blakvision_generate",
         "params": {"prompt": "1"}, "parallel_group": "art"},
        {"service": "blakvision", "action": "blakvision_generate",
         "params": {"prompt": "2"}, "parallel_group": "art"},
        {"service": "evera", "action": "evera_generate",
         "params": {}, "parallel_group": "art"},
    ]
    result = eco.run_workflow(steps)
    assert result["ok"] is True
    assert result["steps_completed"] == 3


# ---------------------------------------------------------------------------
# Quality gate tests
# ---------------------------------------------------------------------------

def test_quality_gate_field_pass():
    from apps.onyx_ecosystem import OnyxEcosystem
    eco = OnyxEcosystem()
    gate = {"field": "score", "min": 5}
    result = {"ok": True, "score": 8}
    check = eco._check_quality_gate(1, result, gate)
    assert check["passed"] is True


def test_quality_gate_field_fail():
    from apps.onyx_ecosystem import OnyxEcosystem
    eco = OnyxEcosystem()
    gate = {"field": "score", "min": 7}
    result = {"ok": True, "score": 3}
    check = eco._check_quality_gate(1, result, gate)
    assert check["passed"] is False
    assert "score=3" in check["reason"]


def test_quality_gate_contains_pass():
    from apps.onyx_ecosystem import OnyxEcosystem
    eco = OnyxEcosystem()
    gate = {"contains": "success"}
    result = {"ok": True, "message": "Operation was a success"}
    check = eco._check_quality_gate(1, result, gate)
    assert check["passed"] is True


def test_quality_gate_contains_fail():
    from apps.onyx_ecosystem import OnyxEcosystem
    eco = OnyxEcosystem()
    gate = {"contains": "completed"}
    result = {"ok": True, "message": "Something else"}
    check = eco._check_quality_gate(1, result, gate)
    assert check["passed"] is False


# ---------------------------------------------------------------------------
# Retry tests
# ---------------------------------------------------------------------------

def test_retry_on_failure():
    from apps.onyx_ecosystem import OnyxEcosystem
    eco = OnyxEcosystem()

    mock = MagicMock()
    call_count = [0]

    def side_effect(action, params):
        call_count[0] += 1
        if call_count[0] < 3:
            return {"ok": False, "error": "temporary"}
        return {"ok": True, "data": "recovered"}

    mock.execute_action.side_effect = side_effect
    eco._modules["blakvision"] = mock

    steps = [
        {"service": "blakvision", "action": "blakvision_generate",
         "params": {"prompt": "test"}, "retry": 3},
    ]
    result = eco.run_workflow(steps)
    assert result["ok"] is True
    assert result["results"][0]["_attempt"] == 3  # Succeeded on 3rd attempt


# ---------------------------------------------------------------------------
# Asset tracking tests
# ---------------------------------------------------------------------------

def test_asset_tracking():
    from apps.onyx_ecosystem import OnyxEcosystem
    eco = OnyxEcosystem()

    step = {"service": "blakvision", "action": "blakvision_generate",
            "params": {}, "asset_tag": "cover_art"}
    result = {"ok": True, "local_path": "/tmp/image.png", "_step": 1}

    asset = eco._track_asset(step, result)
    assert asset is not None
    assert asset["tag"] == "cover_art"
    assert "/tmp/image.png" in asset["paths"]


def test_asset_tracking_no_tag():
    from apps.onyx_ecosystem import OnyxEcosystem
    eco = OnyxEcosystem()

    step = {"service": "blakvision", "action": "blakvision_generate", "params": {}}
    result = {"ok": True, "local_path": "/tmp/image.png"}

    asset = eco._track_asset(step, result)
    assert asset is None


# ---------------------------------------------------------------------------
# Workflow template tests
# ---------------------------------------------------------------------------

def test_workflow_templates_loadable():
    from apps.workflows import list_workflows, WORKFLOWS
    wfs = list_workflows()
    assert len(wfs) == 6
    ids = [w["id"] for w in wfs]
    assert "game_with_assets" in ids
    assert "music_video" in ids
    assert "publish_book" in ids
    assert "marketing_bundle" in ids
    assert "concept_to_game" in ids
    assert "album_release" in ids


def test_workflow_build():
    from apps.workflows import build_workflow
    steps = build_workflow("game_with_assets", {"genre": "platformer"})
    assert steps is not None
    assert len(steps) >= 3
    # Check parallel groups exist
    pg_values = [s.get("parallel_group") for s in steps if s.get("parallel_group")]
    assert len(pg_values) > 0


def test_workflow_build_unknown():
    from apps.workflows import build_workflow
    steps = build_workflow("nonexistent_workflow")
    assert steps is None


# ---------------------------------------------------------------------------
# Scheduler tests
# ---------------------------------------------------------------------------

def test_scheduler_add_remove():
    from apps.workflow_scheduler import WorkflowScheduler
    sched = WorkflowScheduler()
    sched._schedules.clear()  # Start clean

    entry = sched.add("test_sched", "publish_book",
                       params={"title": "Test"}, interval_seconds=3600)
    assert entry.id == "test_sched"
    assert entry.workflow_id == "publish_book"
    assert entry.enabled is True
    assert entry.interval_seconds == 3600
    assert "test_sched" in [s["id"] for s in sched.list_schedules()]

    removed = sched.remove("test_sched")
    assert removed is True
    assert "test_sched" not in [s["id"] for s in sched.list_schedules()]


def test_scheduler_toggle():
    from apps.workflow_scheduler import WorkflowScheduler
    sched = WorkflowScheduler()
    sched._schedules.clear()

    sched.add("toggle_test", "music_video", interval_seconds=600)
    assert sched._schedules["toggle_test"].enabled is True

    sched.enable("toggle_test", False)
    assert sched._schedules["toggle_test"].enabled is False


def test_scheduler_due():
    from apps.workflow_scheduler import WorkflowScheduler, ScheduleEntry
    sched = WorkflowScheduler()
    sched._schedules.clear()

    # Create an entry that's already past due
    entry = ScheduleEntry(
        id="due_test", workflow_id="publish_book",
        interval_seconds=60, enabled=True,
        next_run=time.time() - 10,  # 10 seconds ago
    )
    sched._schedules["due_test"] = entry

    due = sched.get_due()
    assert len(due) == 1
    assert due[0].id == "due_test"


def test_scheduler_stats():
    from apps.workflow_scheduler import WorkflowScheduler
    sched = WorkflowScheduler()
    sched._schedules.clear()

    sched.add("s1", "publish_book", interval_seconds=3600)
    sched.add("s2", "music_video", interval_seconds=7200)
    sched.enable("s2", False)

    stats = sched.get_stats()
    assert stats["total_schedules"] == 2
    assert stats["enabled"] == 1


# ---------------------------------------------------------------------------
# Parameter interpolation tests
# ---------------------------------------------------------------------------

def test_interpolation():
    from apps.onyx_ecosystem import OnyxEcosystem
    eco = OnyxEcosystem()

    prev = [{"artist_id": "art_123"}, {"track_count": 9}]
    context = {"project": "TestAlbum"}

    result = eco._interpolate(
        "Artist ${step_1.artist_id} made ${step_2.track_count} tracks for ${context.project}",
        prev, context,
    )
    assert "art_123" in result
    assert "9" in result
    assert "TestAlbum" in result


def test_interpolation_unresolved():
    from apps.onyx_ecosystem import OnyxEcosystem
    eco = OnyxEcosystem()
    result = eco._interpolate("${step_99.missing}", [], {})
    assert "${step_99.missing}" in result  # Stays unresolved
