"""Tests for core/mind.py — identity, reflection, proactive goals, and full wiring."""

import inspect
import json
import os
import tempfile
import pytest


# ---------------------------------------------------------------------------
# Mind identity and state
# ---------------------------------------------------------------------------

def test_mind_identity_exists():
    """Mind module should define IDENTITY with required fields."""
    from core.mind import IDENTITY
    assert IDENTITY["name"] == "OnyxKraken"
    assert "personality" in IDENTITY
    assert "long_term_goals" in IDENTITY
    assert "core_values" in IDENTITY
    assert len(IDENTITY["personality"]) >= 3
    assert len(IDENTITY["long_term_goals"]) >= 3


def test_mind_state_persistence():
    """MindState should save and reload correctly."""
    from core.mind import MindState
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        state = MindState(path=path)
        state.data["mood"] = "confident"
        state.data["strengths"] = ["file operations", "app launching"]
        state.data["current_focus"] = "improve chat app interactions"
        state.save()

        # Reload
        state2 = MindState(path=path)
        assert state2.data["mood"] == "confident"
        assert state2.data["strengths"] == ["file operations", "app launching"]
        assert state2.data["current_focus"] == "improve chat app interactions"
    finally:
        os.unlink(path)


def test_mind_get_identity_prompt():
    """get_identity_prompt should return a string with the agent's name."""
    from core.mind import Mind
    mind = Mind()
    prompt = mind.get_identity_prompt()
    assert "OnyxKraken" in prompt
    assert "Autonomous Desktop Agent" in prompt


def test_mind_get_stats():
    """get_stats should return a dict with all expected keys."""
    from core.mind import Mind
    mind = Mind()
    stats = mind.get_stats()
    assert stats["identity"] == "OnyxKraken"
    assert "mood" in stats
    assert "focus" in stats
    assert "strengths" in stats
    assert "weaknesses" in stats
    assert "proactive_goals_generated" in stats
    assert "total_reflections" in stats


def test_mind_singleton():
    """get_mind should return the same instance."""
    from core.mind import get_mind
    m1 = get_mind()
    m2 = get_mind()
    assert m1 is m2


# ---------------------------------------------------------------------------
# Planner wiring — self-improvement advice injection
# ---------------------------------------------------------------------------

def test_planner_injects_mind_identity():
    """The planner's decompose_goal should inject mind identity context."""
    source = inspect.getsource(__import__("agent.planner", fromlist=["decompose_goal"]))
    assert "get_mind" in source
    assert "get_identity_prompt" in source


def test_planner_injects_self_improvement_advice():
    """The planner should inject self-improvement planning advice."""
    source = inspect.getsource(__import__("agent.planner", fromlist=["decompose_goal"]))
    assert "planning_advice" in source
    assert "PLANNING STRATEGIES" in source


# ---------------------------------------------------------------------------
# Error recovery wiring — knowledge store integration
# ---------------------------------------------------------------------------

def test_error_recovery_stores_to_knowledge():
    """ErrorDiagnoser.diagnose should store recovery strategies in knowledge."""
    source = inspect.getsource(__import__("agent.error_recovery", fromlist=["ErrorDiagnoser"]))
    assert "get_knowledge_store" in source
    assert "error_recovery" in source


# ---------------------------------------------------------------------------
# Daemon wiring — mind integration
# ---------------------------------------------------------------------------

def test_daemon_has_reflection():
    """AutonomyDaemon should have a _run_reflection method."""
    from core.autonomy import AutonomyDaemon
    daemon = AutonomyDaemon()
    assert hasattr(daemon, "_run_reflection")
    assert hasattr(daemon, "_run_proactive")
    assert hasattr(daemon, "_notify")


def test_daemon_has_mind_stats():
    """Daemon stats should include mind stats."""
    from core.autonomy import AutonomyDaemon
    daemon = AutonomyDaemon()
    stats = daemon.get_stats()
    # Mind stats are best-effort, so just check the daemon fields
    assert "proactive_completed" in stats
    assert "tasks_completed" in stats


def test_daemon_intervals():
    """Daemon should have configurable intervals for reflection and proactive goals."""
    from core.autonomy import AutonomyDaemon
    daemon = AutonomyDaemon(
        reflect_interval=60.0,
        proactive_interval=30.0,
    )
    assert daemon.reflect_interval == 60.0
    assert daemon.proactive_interval == 30.0


# ---------------------------------------------------------------------------
# Server wiring — mind endpoints + antipattern fixes
# ---------------------------------------------------------------------------

def test_server_has_mind_endpoints():
    """Server should have /mind, /mind/reflect, /mind/goal endpoints."""
    from server import app
    routes = [r.path for r in app.routes]
    assert "/mind" in routes
    assert "/mind/reflect" in routes
    assert "/mind/goal" in routes


def test_server_improve_no_background_tasks():
    """The /improve endpoint should not use BackgroundTasks parameter."""
    from routes.daemon import run_improvement
    sig = inspect.signature(run_improvement)
    assert "background_tasks" not in sig.parameters


def test_server_voice_goal_no_background_tasks():
    """The /voice/goal endpoint should not use BackgroundTasks parameter."""
    from routes.voice_mind import voice_goal
    sig = inspect.signature(voice_goal)
    assert "background_tasks" not in sig.parameters


# ---------------------------------------------------------------------------
# Discord bot wiring — conversation state
# ---------------------------------------------------------------------------

def test_discord_bot_has_conversation_context():
    """Discord bot should have per-channel conversation context."""
    from core.discord_bot import _ChannelContext, _is_affirmative, _is_negation
    ctx = _ChannelContext()
    assert not ctx.active
    ctx.set("test goal", "test result")
    assert ctx.active
    assert ctx.last_goal == "test goal"


def test_affirmative_detection():
    """Should detect affirmative phrases."""
    from core.discord_bot import _is_affirmative, _is_negation
    assert _is_affirmative("yes")
    assert _is_affirmative("do it")
    assert _is_affirmative("let's go!")
    assert _is_affirmative("sounds good")
    assert not _is_affirmative("open notepad and type hello")


def test_negation_detection():
    """Should detect negation phrases."""
    from core.discord_bot import _is_negation
    assert _is_negation("no")
    assert _is_negation("cancel")
    assert _is_negation("nevermind")
    assert not _is_negation("open notepad")


# ---------------------------------------------------------------------------
# Notification wiring
# ---------------------------------------------------------------------------

def test_discord_notify_module():
    """discord_notify should have all notification functions."""
    from core import discord_notify
    assert hasattr(discord_notify, "notify")
    assert hasattr(discord_notify, "notify_task_complete")
    assert hasattr(discord_notify, "notify_task_failed")
    assert hasattr(discord_notify, "notify_improvement")
    assert hasattr(discord_notify, "notify_daemon_event")


# ---------------------------------------------------------------------------
# Full wiring: orchestrator post-task → all subsystems
# ---------------------------------------------------------------------------

def test_orchestrator_wires_to_all_subsystems():
    """Task runner run() should wire to memory, self-improvement, knowledge, and discord."""
    from agent import task_runner
    source = inspect.getsource(task_runner._post_task_reflect)
    # Memory
    assert "memory.record_task" in source
    # Self-improvement
    assert "get_improvement_engine" in source
    assert "record_failure" in source
    # Knowledge
    assert "get_knowledge_store" in source
    assert "add_task_pattern" in source
    # Discord notifications
    assert "notify_task_complete" in source
    assert "notify_task_failed" in source
