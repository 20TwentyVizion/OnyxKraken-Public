"""Simple JSON-backed memory store for OnyxKraken.

Three categories of memories:
  - launch_methods: How to successfully launch each app
  - failures: Actions/approaches that failed and why
  - preferences: Observed user preferences and patterns

Designed to be dead simple — json.load / json.dump — and only graduate
to embeddings when this file becomes too large to search linearly.
"""

import json
import logging
import math

_log = logging.getLogger("memory.store")
import os
import time
from typing import Optional

from memory.base_store import BaseJsonStore


# ---------------------------------------------------------------------------
# Memory decay — exponential half-life scoring (neuroscience rule #1)
# ---------------------------------------------------------------------------

# Half-life in seconds: memories lose 50% relevance after this duration
MEMORY_HALF_LIFE = 7 * 24 * 3600  # 7 days


def decay_score(timestamp: float, half_life: float = MEMORY_HALF_LIFE) -> float:
    """Return a 0-1 relevance score based on age.

    Uses exponential decay: score = 0.5 ^ (age / half_life).
    A memory from *half_life* seconds ago scores 0.5;
    a memory from 2x half_life ago scores 0.25, etc.
    """
    age = max(0.0, time.time() - timestamp)
    return math.pow(0.5, age / half_life) if half_life > 0 else 1.0


MEMORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "memory.json")

_DEFAULT = {
    "launch_methods": {},
    "failures": [],
    "preferences": {},
    "task_history": [],
}

# Cap sizes to prevent unbounded growth
MAX_FAILURES = 100
MAX_TASK_HISTORY = 50


class MemoryStore(BaseJsonStore):
    """Persistent memory backed by a single JSON file."""

    def __init__(self, path: str = MEMORY_FILE):
        super().__init__(path, _DEFAULT)

    # ------------------------------------------------------------------
    # Launch methods: "grok" -> {"method": "desktop_shortcut", "detail": "Grok"}
    # ------------------------------------------------------------------

    def remember_launch(self, app_name: str, method: str, detail: str):
        """Record a successful launch method for an app."""
        self._data["launch_methods"][app_name.lower()] = {
            "method": method,
            "detail": detail,
            "last_used": time.time(),
        }
        self._save()

    def recall_launch(self, app_name: str) -> Optional[dict]:
        """Get the last successful launch method for an app."""
        return self._data["launch_methods"].get(app_name.lower())

    # ------------------------------------------------------------------
    # Failures: [{app, action, target, error, timestamp}]
    # ------------------------------------------------------------------

    def remember_failure(self, app_name: str, action: str, target: str, error: str):
        """Record a failed action for future avoidance."""
        self._data["failures"].append({
            "app": app_name,
            "action": action,
            "target": target,
            "error": error,
            "timestamp": time.time(),
        })
        # Cap size
        if len(self._data["failures"]) > MAX_FAILURES:
            self._data["failures"] = self._data["failures"][-MAX_FAILURES:]
        self._save()

    def recall_failures(self, app_name: Optional[str] = None, limit: int = 10) -> list[dict]:
        """Get recent failures, optionally filtered by app."""
        failures = self._data["failures"]
        if app_name:
            failures = [f for f in failures if f["app"].lower() == app_name.lower()]
        return failures[-limit:]

    def recall_failures_weighted(self, app_name: Optional[str] = None,
                                 limit: int = 10) -> list[dict]:
        """Get failures ranked by time-weighted relevance (recent > old)."""
        failures = self._data["failures"]
        if app_name:
            failures = [f for f in failures if f["app"].lower() == app_name.lower()]
        scored = []
        for f in failures:
            ts = f.get("timestamp", 0)
            scored.append((decay_score(ts), f))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored[:limit]]

    # ------------------------------------------------------------------
    # Preferences: {"key": "value"}
    # ------------------------------------------------------------------

    def set_preference(self, key: str, value):
        """Store a user preference."""
        self._data["preferences"][key] = value
        self._save()

    def get_preference(self, key: str, default=None):
        """Retrieve a user preference."""
        return self._data["preferences"].get(key, default)

    # ------------------------------------------------------------------
    # Task history: [{goal, app, steps_planned, steps_completed, time, success, timestamp}]
    # ------------------------------------------------------------------

    def record_task(self, goal: str, app_name: str, steps_planned: int,
                    steps_completed: int, total_time: float, success: bool,
                    notes: str = ""):
        """Record a completed task for retrospective analysis."""
        self._data["task_history"].append({
            "goal": goal,
            "app": app_name,
            "steps_planned": steps_planned,
            "steps_completed": steps_completed,
            "total_time": round(total_time, 1),
            "success": success,
            "notes": notes,
            "timestamp": time.time(),
        })
        if len(self._data["task_history"]) > MAX_TASK_HISTORY:
            self._data["task_history"] = self._data["task_history"][-MAX_TASK_HISTORY:]
        self._save()

    def recall_similar_tasks(self, goal: str, limit: int = 5) -> list[dict]:
        """Find past tasks similar to the given goal.

        Uses embedding-based cosine similarity when available, falls back
        to keyword overlap matching.  Both paths apply time-decay so
        recent tasks rank higher than stale ones.
        """
        if not self._data["task_history"]:
            return []

        # Try embedding-based search first
        try:
            from memory.embeddings import get_embedding_store
            store = get_embedding_store()
            if store.is_available():
                results = store.find_similar(
                    query=goal,
                    candidates=self._data["task_history"],
                    text_key="goal",
                    limit=limit * 2,  # over-fetch, then re-rank
                    threshold=0.4,
                )
                if results:
                    # Re-rank: combined = semantic * 0.7 + decay * 0.3
                    reranked = []
                    for sim_score, item in results:
                        d = decay_score(item.get("timestamp", 0))
                        combined = sim_score * 0.7 + d * 0.3
                        reranked.append((combined, item))
                    reranked.sort(key=lambda x: x[0], reverse=True)
                    return [item for _, item in reranked[:limit]]
        except Exception:
            pass  # Fall through to keyword matching

        # Fallback: keyword overlap * decay
        goal_words = set(goal.lower().split())
        scored = []
        for task in self._data["task_history"]:
            task_words = set(task["goal"].lower().split())
            overlap = len(goal_words & task_words)
            if overlap > 0:
                d = decay_score(task.get("timestamp", 0))
                scored.append((overlap * d, task))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:limit]]

    # ------------------------------------------------------------------
    # Bulk access
    # ------------------------------------------------------------------

    def get_all(self) -> dict:
        """Return the full memory store (for debugging/inspection)."""
        return dict(self._data)

    def decay_old_memories(self, threshold: float = 0.05):
        """Prune memories whose decay score has dropped below *threshold*.

        Default threshold 0.05 ≈ memories older than ~4.3 half-lives
        (about 30 days with the default 7-day half-life).
        """
        before_f = len(self._data["failures"])
        before_t = len(self._data["task_history"])

        self._data["failures"] = [
            f for f in self._data["failures"]
            if decay_score(f.get("timestamp", 0)) >= threshold
        ]
        self._data["task_history"] = [
            t for t in self._data["task_history"]
            if decay_score(t.get("timestamp", 0)) >= threshold
        ]

        pruned_f = before_f - len(self._data["failures"])
        pruned_t = before_t - len(self._data["task_history"])
        if pruned_f or pruned_t:
            _log.info(f"Memory decay pruned {pruned_f} failures, {pruned_t} tasks")
            self._save()

    def clear(self):
        """Wipe all memory."""
        self._data = json.loads(json.dumps(_DEFAULT))
        self._save()
