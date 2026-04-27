"""Cross-session conversation memory — SQLite-backed persistence.

Stores conversation turns (user input, resolved goal, app, result, success)
across sessions so OnyxKraken remembers what it did last time. Also stores
chat messages for the Face GUI's chat panel.

Schema:
  sessions — one row per app launch (session_id, started_at)
  turns    — one row per orchestrator task (goal, app, result, success)
  messages — one row per chat message (role, text, timestamp)
"""

import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional

_log = logging.getLogger("memory.conversation_db")

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "conversations.db"
)


@dataclass
class StoredTurn:
    """A persisted conversation turn."""
    id: int
    session_id: int
    user_input: str
    resolved_goal: str
    app_name: str
    result_summary: str
    success: bool
    timestamp: float


@dataclass
class StoredMessage:
    """A persisted chat message."""
    id: int
    session_id: int
    role: str       # "user", "assistant", "system"
    text: str
    timestamp: float


class ConversationDB:
    """SQLite-backed conversation memory."""

    def __init__(self, db_path: str = _DB_PATH):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        self._session_id = self._start_session()
        _log.info(f"ConversationDB session {self._session_id} started")

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                user_input TEXT NOT NULL,
                resolved_goal TEXT NOT NULL DEFAULT '',
                app_name TEXT NOT NULL DEFAULT 'unknown',
                result_summary TEXT NOT NULL DEFAULT '',
                success INTEGER NOT NULL DEFAULT 0,
                timestamp REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_turns_timestamp ON turns(timestamp);
        """)

    def _start_session(self) -> int:
        cur = self._conn.execute(
            "INSERT INTO sessions (started_at) VALUES (?)", (time.time(),)
        )
        self._conn.commit()
        return cur.lastrowid

    @property
    def session_id(self) -> int:
        return self._session_id

    # ------------------------------------------------------------------
    # Turns (orchestrator tasks)
    # ------------------------------------------------------------------

    def add_turn(
        self,
        user_input: str,
        resolved_goal: str = "",
        app_name: str = "unknown",
        result_summary: str = "",
        success: bool = False,
    ) -> int:
        """Record a conversation turn."""
        cur = self._conn.execute(
            """INSERT INTO turns
               (session_id, user_input, resolved_goal, app_name, result_summary, success, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (self._session_id, user_input, resolved_goal, app_name,
             result_summary, 1 if success else 0, time.time()),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_recent_turns(self, limit: int = 20) -> list[StoredTurn]:
        """Get recent turns across all sessions, newest first."""
        rows = self._conn.execute(
            """SELECT id, session_id, user_input, resolved_goal, app_name,
                      result_summary, success, timestamp
               FROM turns ORDER BY timestamp DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            StoredTurn(
                id=r[0], session_id=r[1], user_input=r[2],
                resolved_goal=r[3], app_name=r[4], result_summary=r[5],
                success=bool(r[6]), timestamp=r[7],
            )
            for r in rows
        ]

    def get_session_turns(self, session_id: Optional[int] = None) -> list[StoredTurn]:
        """Get all turns from a specific session (default: current)."""
        sid = session_id or self._session_id
        rows = self._conn.execute(
            """SELECT id, session_id, user_input, resolved_goal, app_name,
                      result_summary, success, timestamp
               FROM turns WHERE session_id = ? ORDER BY timestamp ASC""",
            (sid,),
        ).fetchall()
        return [
            StoredTurn(
                id=r[0], session_id=r[1], user_input=r[2],
                resolved_goal=r[3], app_name=r[4], result_summary=r[5],
                success=bool(r[6]), timestamp=r[7],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Messages (chat panel)
    # ------------------------------------------------------------------

    def add_message(self, role: str, text: str) -> int:
        """Store a chat message."""
        cur = self._conn.execute(
            """INSERT INTO messages (session_id, role, text, timestamp)
               VALUES (?, ?, ?, ?)""",
            (self._session_id, role, text, time.time()),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_recent_messages(self, limit: int = 50) -> list[StoredMessage]:
        """Get recent messages across all sessions, newest first."""
        rows = self._conn.execute(
            """SELECT id, session_id, role, text, timestamp
               FROM messages ORDER BY timestamp DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            StoredMessage(id=r[0], session_id=r[1], role=r[2], text=r[3], timestamp=r[4])
            for r in reversed(rows)  # return oldest-first for display
        ]

    def get_session_messages(self, session_id: Optional[int] = None) -> list[StoredMessage]:
        """Get all messages from a specific session."""
        sid = session_id or self._session_id
        rows = self._conn.execute(
            """SELECT id, session_id, role, text, timestamp
               FROM messages WHERE session_id = ? ORDER BY timestamp ASC""",
            (sid,),
        ).fetchall()
        return [
            StoredMessage(id=r[0], session_id=r[1], role=r[2], text=r[3], timestamp=r[4])
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Context for LLM (summary of recent history)
    # ------------------------------------------------------------------

    def get_context_summary(self, max_turns: int = 5) -> str:
        """Build a summary of recent turns for LLM context injection."""
        turns = self.get_recent_turns(limit=max_turns)
        if not turns:
            return ""
        lines = ["Previous conversation history:"]
        for t in reversed(turns):  # oldest first
            status = "OK" if t.success else "FAIL"
            lines.append(f"  [{status}] \"{t.user_input}\" → {t.resolved_goal}")
            if t.result_summary:
                lines.append(f"    Result: {t.result_summary[:100]}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        total_sessions = self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        total_turns = self._conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
        total_messages = self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        success_rate = 0.0
        if total_turns > 0:
            successes = self._conn.execute("SELECT COUNT(*) FROM turns WHERE success = 1").fetchone()[0]
            success_rate = successes / total_turns
        return {
            "total_sessions": total_sessions,
            "total_turns": total_turns,
            "total_messages": total_messages,
            "success_rate": round(success_rate, 2),
            "current_session": self._session_id,
        }

    def close(self):
        self._conn.close()


# Singleton
_db: Optional[ConversationDB] = None


def get_conversation_db() -> ConversationDB:
    global _db
    if _db is None:
        _db = ConversationDB()
    return _db
