"""Structured Action Telemetry — queryable log of every Onyx decision and action.

Every significant action Onyx takes is recorded as an ActionTrace with:
  - What it was trying to do (intent)
  - What tools/steps it used
  - Whether it succeeded
  - How long it took
  - The reasoning that led to the action
  - System state at the time

Stored in SQLite for efficient querying. Onyx can ask itself:
  "What fails most often?" "How long do Blender builds take?"
  "What's my success rate on music generation?"

Usage:
    from core.telemetry import telemetry

    # Record an action
    with telemetry.trace("desktop", "Open Notepad") as t:
        t.reasoning = "User asked to open Notepad"
        do_the_thing()
        t.add_tool_call("launch_tool", {"app": "notepad"})
        t.set_result("success", "Notepad opened")

    # Or manually
    telemetry.record(
        action_type="music",
        intent="Generate lo-fi track",
        result="success",
        duration=45.2,
    )

    # Query
    stats = telemetry.get_stats()
    failures = telemetry.query(result="failure", limit=10)

CLI:
    python -m core.telemetry --stats
    python -m core.telemetry --recent 20
    python -m core.telemetry --failures
"""

import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

_log = logging.getLogger("core.telemetry")

_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = _ROOT / "data" / "telemetry.db"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    """A single tool invocation within an action."""
    tool: str
    params: dict = field(default_factory=dict)
    result: str = ""
    duration: float = 0.0


@dataclass
class ActionTrace:
    """A structured record of a single Onyx action."""
    timestamp: float = 0.0
    action_type: str = ""       # desktop, blender, music, video, chain, system, chat
    intent: str = ""            # What Onyx was trying to do
    tool_calls: list[ToolCall] = field(default_factory=list)
    result: str = ""            # success, failure, partial, skipped
    result_detail: str = ""     # Human-readable detail
    duration: float = 0.0       # Total seconds
    reasoning: str = ""         # LLM reasoning that led to this action
    context: dict = field(default_factory=dict)  # System state snapshot
    workflow_id: str = ""       # If part of a chain workflow
    step_id: str = ""           # If part of a workflow step
    error: str = ""             # Error message if failed
    metadata: dict = field(default_factory=dict)  # Extra data

    def add_tool_call(self, tool: str, params: dict = None, result: str = "",
                      duration: float = 0.0):
        self.tool_calls.append(ToolCall(
            tool=tool, params=params or {}, result=result, duration=duration,
        ))

    def set_result(self, result: str, detail: str = ""):
        self.result = result
        self.result_detail = detail


# ---------------------------------------------------------------------------
# Trace context manager
# ---------------------------------------------------------------------------

class TraceContext:
    """Context manager for recording an action trace with automatic timing."""

    def __init__(self, telemetry_instance, action_type: str, intent: str):
        self._telemetry = telemetry_instance
        self.trace = ActionTrace(
            timestamp=time.time(),
            action_type=action_type,
            intent=intent,
        )
        self._start_time = 0.0

    def __enter__(self) -> ActionTrace:
        self._start_time = time.time()
        return self.trace

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.trace.duration = time.time() - self._start_time
        if exc_type is not None:
            self.trace.result = self.trace.result or "failure"
            self.trace.error = str(exc_val)
        elif not self.trace.result:
            self.trace.result = "success"
        self._telemetry._store(self.trace)
        return False  # don't suppress exceptions

    # Convenience delegates
    @property
    def reasoning(self) -> str:
        return self.trace.reasoning

    @reasoning.setter
    def reasoning(self, value: str):
        self.trace.reasoning = value

    def add_tool_call(self, tool: str, params: dict = None, result: str = "",
                      duration: float = 0.0):
        self.trace.add_tool_call(tool, params, result, duration)

    def set_result(self, result: str, detail: str = ""):
        self.trace.set_result(result, detail)


# ---------------------------------------------------------------------------
# Telemetry Engine
# ---------------------------------------------------------------------------

class TelemetryEngine:
    """SQLite-backed telemetry store with query API."""

    def __init__(self, db_path: str = ""):
        self._db_path = db_path or str(_DB_PATH)
        self._lock = threading.Lock()
        self._initialized = False

    def _ensure_db(self):
        """Create the database and tables if needed."""
        if self._initialized:
            return
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    action_type TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    tool_calls TEXT DEFAULT '[]',
                    result TEXT DEFAULT '',
                    result_detail TEXT DEFAULT '',
                    duration REAL DEFAULT 0,
                    reasoning TEXT DEFAULT '',
                    context TEXT DEFAULT '{}',
                    workflow_id TEXT DEFAULT '',
                    step_id TEXT DEFAULT '',
                    error TEXT DEFAULT '',
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_traces_type
                ON traces(action_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_traces_result
                ON traces(result)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_traces_time
                ON traces(timestamp)
            """)
        self._initialized = True

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, timeout=5)

    # -- Recording --

    def trace(self, action_type: str, intent: str) -> TraceContext:
        """Context manager that auto-records an action trace.

        Usage:
            with telemetry.trace("desktop", "Open Notepad") as t:
                t.reasoning = "User requested"
                do_stuff()
                t.set_result("success")
        """
        return TraceContext(self, action_type, intent)

    def record(
        self,
        action_type: str,
        intent: str,
        result: str = "success",
        result_detail: str = "",
        duration: float = 0.0,
        reasoning: str = "",
        error: str = "",
        workflow_id: str = "",
        step_id: str = "",
        tool_calls: list[dict] = None,
        context: dict = None,
        metadata: dict = None,
    ):
        """Record a completed action trace directly."""
        trace = ActionTrace(
            timestamp=time.time(),
            action_type=action_type,
            intent=intent,
            result=result,
            result_detail=result_detail,
            duration=duration,
            reasoning=reasoning,
            error=error,
            workflow_id=workflow_id,
            step_id=step_id,
            context=context or {},
            metadata=metadata or {},
        )
        if tool_calls:
            for tc in tool_calls:
                trace.add_tool_call(
                    tc.get("tool", ""),
                    tc.get("params", {}),
                    tc.get("result", ""),
                    tc.get("duration", 0),
                )
        self._store(trace)

    def _store(self, trace: ActionTrace):
        """Persist a trace to SQLite."""
        self._ensure_db()
        try:
            with self._lock:
                with self._connect() as conn:
                    conn.execute("""
                        INSERT INTO traces
                        (timestamp, action_type, intent, tool_calls, result,
                         result_detail, duration, reasoning, context,
                         workflow_id, step_id, error, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        trace.timestamp,
                        trace.action_type,
                        trace.intent,
                        json.dumps([asdict(tc) for tc in trace.tool_calls]),
                        trace.result,
                        trace.result_detail,
                        trace.duration,
                        trace.reasoning,
                        json.dumps(trace.context),
                        trace.workflow_id,
                        trace.step_id,
                        trace.error,
                        json.dumps(trace.metadata),
                    ))
        except Exception as exc:
            _log.error("Failed to store trace: %s", exc)

    # -- Querying --

    def query(
        self,
        action_type: str = "",
        result: str = "",
        workflow_id: str = "",
        since: float = 0,
        limit: int = 50,
    ) -> list[dict]:
        """Query traces with filters. Returns list of dicts."""
        self._ensure_db()
        clauses = []
        params = []

        if action_type:
            clauses.append("action_type = ?")
            params.append(action_type)
        if result:
            clauses.append("result = ?")
            params.append(result)
        if workflow_id:
            clauses.append("workflow_id = ?")
            params.append(workflow_id)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM traces {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]
        except Exception as exc:
            _log.error("Query failed: %s", exc)
            return []

    def get_recent(self, limit: int = 20) -> list[dict]:
        """Get most recent traces."""
        return self.query(limit=limit)

    def get_failures(self, limit: int = 20) -> list[dict]:
        """Get recent failures."""
        return self.query(result="failure", limit=limit)

    # -- Analytics --

    def get_stats(self, since: float = 0) -> dict:
        """Get aggregate statistics."""
        self._ensure_db()
        if not since:
            since = time.time() - 86400 * 7  # last 7 days

        try:
            with self._connect() as conn:
                # Total counts by result
                rows = conn.execute("""
                    SELECT result, COUNT(*) as cnt
                    FROM traces WHERE timestamp >= ?
                    GROUP BY result
                """, (since,)).fetchall()
                by_result = {r[0]: r[1] for r in rows}

                # Counts by action type
                rows = conn.execute("""
                    SELECT action_type, COUNT(*) as cnt, AVG(duration) as avg_dur,
                           SUM(CASE WHEN result='success' THEN 1 ELSE 0 END) as successes
                    FROM traces WHERE timestamp >= ?
                    GROUP BY action_type
                """, (since,)).fetchall()
                by_type = {}
                for r in rows:
                    total = r[1]
                    by_type[r[0]] = {
                        "count": total,
                        "avg_duration": round(r[2], 2) if r[2] else 0,
                        "success_rate": round(r[3] / total * 100, 1) if total else 0,
                    }

                # Most common errors
                rows = conn.execute("""
                    SELECT error, COUNT(*) as cnt
                    FROM traces
                    WHERE timestamp >= ? AND result='failure' AND error != ''
                    GROUP BY error
                    ORDER BY cnt DESC
                    LIMIT 5
                """, (since,)).fetchall()
                top_errors = [{"error": r[0][:100], "count": r[1]} for r in rows]

                # Total
                total = sum(by_result.values())
                success_count = by_result.get("success", 0)

                return {
                    "period": "7 days",
                    "total_actions": total,
                    "success_rate": round(success_count / total * 100, 1) if total else 0,
                    "by_result": by_result,
                    "by_type": by_type,
                    "top_errors": top_errors,
                }
        except Exception as exc:
            _log.error("Stats query failed: %s", exc)
            return {"error": str(exc)}

    def get_stats_summary(self, since: float = 0) -> str:
        """Get a human-readable stats summary."""
        stats = self.get_stats(since)
        if "error" in stats:
            return f"Telemetry stats unavailable: {stats['error']}"

        lines = [
            f"Telemetry Stats (last {stats['period']})",
            f"  Total actions: {stats['total_actions']}",
            f"  Overall success rate: {stats['success_rate']}%",
        ]

        if stats.get("by_type"):
            lines.append("  By type:")
            for atype, info in stats["by_type"].items():
                lines.append(
                    f"    {atype}: {info['count']} actions, "
                    f"{info['success_rate']}% success, "
                    f"avg {info['avg_duration']}s"
                )

        if stats.get("top_errors"):
            lines.append("  Top errors:")
            for err in stats["top_errors"]:
                lines.append(f"    ({err['count']}x) {err['error']}")

        return "\n".join(lines)

    def get_workflow_stats(self, workflow_id: str) -> dict:
        """Get stats for a specific chain workflow."""
        self._ensure_db()
        try:
            with self._connect() as conn:
                rows = conn.execute("""
                    SELECT step_id, result, COUNT(*) as cnt, AVG(duration) as avg_dur
                    FROM traces
                    WHERE workflow_id = ?
                    GROUP BY step_id, result
                """, (workflow_id,)).fetchall()

                steps = {}
                for r in rows:
                    step = r[0] or "overall"
                    if step not in steps:
                        steps[step] = {"runs": 0, "successes": 0, "avg_duration": 0}
                    steps[step]["runs"] += r[2]
                    if r[1] == "success":
                        steps[step]["successes"] += r[2]
                    steps[step]["avg_duration"] = round(r[3], 2)

                for info in steps.values():
                    info["success_rate"] = round(
                        info["successes"] / info["runs"] * 100, 1
                    ) if info["runs"] else 0

                return {"workflow_id": workflow_id, "steps": steps}
        except Exception as exc:
            return {"error": str(exc)}


# Module-level singleton
telemetry = TelemetryEngine()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="OnyxKraken Telemetry")
    parser.add_argument("--stats", action="store_true", help="Show aggregate stats")
    parser.add_argument("--recent", type=int, default=0, help="Show N recent traces")
    parser.add_argument("--failures", action="store_true", help="Show recent failures")
    parser.add_argument("--type", default="", help="Filter by action type")
    parser.add_argument("--workflow", default="", help="Show workflow stats")
    args = parser.parse_args()

    if args.stats:
        print(telemetry.get_stats_summary())
    elif args.recent:
        traces = telemetry.get_recent(args.recent)
        for t in traces:
            ts = time.strftime("%m/%d %H:%M:%S", time.localtime(t["timestamp"]))
            dur = f"{t['duration']:.1f}s" if t["duration"] else ""
            err = f" ERR: {t['error'][:40]}" if t.get("error") else ""
            print(f"  [{ts}] {t['action_type']:10s} {t['result']:8s} "
                  f"{dur:>6s}  {t['intent'][:50]}{err}")
    elif args.failures:
        traces = telemetry.get_failures(20)
        for t in traces:
            ts = time.strftime("%m/%d %H:%M:%S", time.localtime(t["timestamp"]))
            print(f"  [{ts}] {t['action_type']:10s} {t['intent'][:40]}")
            if t.get("error"):
                print(f"           Error: {t['error'][:80]}")
    elif args.workflow:
        stats = telemetry.get_workflow_stats(args.workflow)
        print(f"Workflow: {args.workflow}")
        for step, info in stats.get("steps", {}).items():
            print(f"  {step}: {info['runs']} runs, "
                  f"{info['success_rate']}% success, "
                  f"avg {info['avg_duration']}s")
    elif args.type:
        traces = telemetry.query(action_type=args.type, limit=20)
        for t in traces:
            ts = time.strftime("%m/%d %H:%M:%S", time.localtime(t["timestamp"]))
            print(f"  [{ts}] {t['result']:8s} {t['intent'][:60]}")
    else:
        print("Usage: python -m core.telemetry --stats | --recent N | --failures | --type TYPE")
        print()
        # Show quick summary
        print(telemetry.get_stats_summary())
