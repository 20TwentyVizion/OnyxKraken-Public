"""Tests for memory.conversation_db — SQLite-backed conversation persistence."""

import os
import time
import pytest

from memory.conversation_db import ConversationDB, StoredTurn, StoredMessage


@pytest.fixture
def db(tmp_path):
    """Create a fresh ConversationDB in a temp directory."""
    db_path = str(tmp_path / "test_conversations.db")
    cdb = ConversationDB(db_path=db_path)
    yield cdb
    cdb.close()


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

class TestSessions:
    def test_session_id_positive(self, db):
        assert db.session_id > 0

    def test_each_instance_gets_new_session(self, tmp_path):
        path = str(tmp_path / "sessions.db")
        db1 = ConversationDB(db_path=path)
        s1 = db1.session_id
        db1.close()
        db2 = ConversationDB(db_path=path)
        s2 = db2.session_id
        db2.close()
        assert s2 > s1


# ---------------------------------------------------------------------------
# Turns (orchestrator tasks)
# ---------------------------------------------------------------------------

class TestTurns:
    def test_add_turn(self, db):
        turn_id = db.add_turn(
            user_input="open notepad",
            resolved_goal="Launch Notepad application",
            app_name="notepad",
            result_summary="Notepad opened successfully",
            success=True,
        )
        assert turn_id > 0

    def test_get_recent_turns(self, db):
        db.add_turn("task 1", success=True)
        db.add_turn("task 2", success=False)
        db.add_turn("task 3", success=True)
        turns = db.get_recent_turns(limit=10)
        assert len(turns) == 3
        # Newest first
        assert turns[0].user_input == "task 3"

    def test_get_session_turns(self, db):
        db.add_turn("session task A")
        db.add_turn("session task B")
        turns = db.get_session_turns()
        assert len(turns) == 2
        # Oldest first (chronological)
        assert turns[0].user_input == "session task A"

    def test_turn_fields(self, db):
        db.add_turn(
            user_input="test input",
            resolved_goal="resolved",
            app_name="chrome",
            result_summary="done",
            success=True,
        )
        turns = db.get_session_turns()
        t = turns[0]
        assert isinstance(t, StoredTurn)
        assert t.user_input == "test input"
        assert t.resolved_goal == "resolved"
        assert t.app_name == "chrome"
        assert t.result_summary == "done"
        assert t.success is True
        assert t.session_id == db.session_id
        assert t.timestamp > 0

    def test_turn_defaults(self, db):
        db.add_turn("minimal turn")
        t = db.get_session_turns()[0]
        assert t.resolved_goal == ""
        assert t.app_name == "unknown"
        assert t.result_summary == ""
        assert t.success is False

    def test_recent_turns_limit(self, db):
        for i in range(10):
            db.add_turn(f"turn {i}")
        turns = db.get_recent_turns(limit=3)
        assert len(turns) == 3

    def test_empty_turns(self, db):
        assert db.get_recent_turns() == []
        assert db.get_session_turns() == []


# ---------------------------------------------------------------------------
# Messages (chat panel)
# ---------------------------------------------------------------------------

class TestMessages:
    def test_add_message(self, db):
        msg_id = db.add_message("user", "Hello Onyx!")
        assert msg_id > 0

    def test_get_recent_messages(self, db):
        db.add_message("user", "Hi")
        db.add_message("assistant", "Hello!")
        db.add_message("user", "Do something")
        msgs = db.get_recent_messages(limit=10)
        assert len(msgs) == 3
        # Should be oldest-first for display
        assert msgs[0].text == "Hi"
        assert msgs[2].text == "Do something"

    def test_get_session_messages(self, db):
        db.add_message("user", "msg A")
        db.add_message("assistant", "msg B")
        msgs = db.get_session_messages()
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"

    def test_message_fields(self, db):
        db.add_message("system", "System init")
        msgs = db.get_session_messages()
        m = msgs[0]
        assert isinstance(m, StoredMessage)
        assert m.role == "system"
        assert m.text == "System init"
        assert m.session_id == db.session_id
        assert m.timestamp > 0

    def test_recent_messages_limit(self, db):
        for i in range(20):
            db.add_message("user", f"msg {i}")
        msgs = db.get_recent_messages(limit=5)
        assert len(msgs) == 5

    def test_empty_messages(self, db):
        assert db.get_recent_messages() == []
        assert db.get_session_messages() == []


# ---------------------------------------------------------------------------
# Context summary (LLM injection)
# ---------------------------------------------------------------------------

class TestContextSummary:
    def test_empty_summary(self, db):
        assert db.get_context_summary() == ""

    def test_summary_with_turns(self, db):
        db.add_turn("open chrome", resolved_goal="Launch Chrome", success=True)
        db.add_turn("type hello", resolved_goal="Type in Notepad", success=False,
                     result_summary="Window not found")
        summary = db.get_context_summary()
        assert "Previous conversation history" in summary
        assert "open chrome" in summary
        assert "type hello" in summary
        assert "OK" in summary
        assert "FAIL" in summary

    def test_summary_respects_limit(self, db):
        for i in range(10):
            db.add_turn(f"task_{i}", success=True)
        summary = db.get_context_summary(max_turns=2)
        # Should only include 2 turns
        assert summary.count("task_") == 2


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_fresh_db_stats(self, db):
        stats = db.get_stats()
        assert stats["total_sessions"] == 1
        assert stats["total_turns"] == 0
        assert stats["total_messages"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["current_session"] == db.session_id

    def test_stats_after_activity(self, db):
        db.add_turn("t1", success=True)
        db.add_turn("t2", success=True)
        db.add_turn("t3", success=False)
        db.add_message("user", "hello")
        stats = db.get_stats()
        assert stats["total_turns"] == 3
        assert stats["total_messages"] == 1
        assert stats["success_rate"] == pytest.approx(0.67, abs=0.01)


# ---------------------------------------------------------------------------
# Persistence across close/reopen
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_data_persists(self, tmp_path):
        path = str(tmp_path / "persist.db")
        db1 = ConversationDB(db_path=path)
        db1.add_turn("persistent task", success=True)
        db1.add_message("user", "persistent msg")
        db1.close()

        db2 = ConversationDB(db_path=path)
        turns = db2.get_recent_turns()
        msgs = db2.get_recent_messages()
        db2.close()

        assert len(turns) == 1
        assert turns[0].user_input == "persistent task"
        assert len(msgs) == 1
        assert msgs[0].text == "persistent msg"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_unicode_content(self, db):
        db.add_turn("打开记事本", resolved_goal="Open Notepad", success=True)
        db.add_message("user", "こんにちは 🤖")
        turns = db.get_session_turns()
        msgs = db.get_session_messages()
        assert turns[0].user_input == "打开记事本"
        assert "🤖" in msgs[0].text

    def test_very_long_text(self, db):
        long_text = "x" * 10000
        db.add_turn(long_text)
        db.add_message("user", long_text)
        assert db.get_session_turns()[0].user_input == long_text
        assert db.get_session_messages()[0].text == long_text

    def test_empty_strings(self, db):
        db.add_turn("")
        db.add_message("user", "")
        assert db.get_session_turns()[0].user_input == ""
        assert db.get_session_messages()[0].text == ""

    def test_special_sql_chars(self, db):
        evil = "Robert'; DROP TABLE turns; --"
        db.add_turn(evil)
        turns = db.get_session_turns()
        assert len(turns) == 1
        assert turns[0].user_input == evil
