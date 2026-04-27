"""Test conversation intent classification and goal resolution."""

import pytest
from agent.conversation import (
    ConversationState,
    ConversationTurn,
    Intent,
    classify_intent,
    resolve_goal,
    format_status_response,
)


@pytest.fixture
def empty_state():
    return ConversationState()


@pytest.fixture
def state_with_history():
    state = ConversationState()
    state.turns.append(ConversationTurn(
        user_input="Open Grok and ask about AI",
        resolved_goal="Open Grok and ask about AI",
        app_name="grok",
        result_summary="Grok responded with a detailed explanation about AI approaches.",
        success=True,
    ))
    return state


def test_no_history_is_new_goal(empty_state):
    assert classify_intent("Open Notepad", empty_state) == Intent.NEW_GOAL
    assert classify_intent("save that to a file", empty_state) == Intent.NEW_GOAL


def test_follow_up_detection(state_with_history):
    assert classify_intent("save that to a file", state_with_history) == Intent.FOLLOW_UP
    assert classify_intent("copy the response to Notepad", state_with_history) == Intent.FOLLOW_UP


def test_refinement_detection(state_with_history):
    assert classify_intent("do it again but ask about Python", state_with_history) == Intent.REFINEMENT
    assert classify_intent("try again", state_with_history) == Intent.REFINEMENT


def test_status_query(state_with_history):
    assert classify_intent("what did you do?", state_with_history) == Intent.STATUS_QUERY
    assert classify_intent("status", state_with_history) == Intent.STATUS_QUERY


def test_new_goal_different_topic(state_with_history):
    assert classify_intent("Open Notepad and type hello world", state_with_history) == Intent.NEW_GOAL


def test_follow_up_resolution(state_with_history):
    goal, app = resolve_goal("save that to a file", Intent.FOLLOW_UP, state_with_history)
    assert "grok" in app.lower() or app == "grok"
    assert "previous task" in goal.lower() or "context" in goal.lower()


def test_refinement_resolution(state_with_history):
    goal, app = resolve_goal("do it again but ask about Python", Intent.REFINEMENT, state_with_history)
    assert "Python" in goal
    assert "Grok" in goal or "AI" in goal


def test_status_response(state_with_history):
    status = format_status_response(state_with_history)
    assert "Open Grok" in status
