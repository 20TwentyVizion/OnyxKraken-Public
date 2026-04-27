"""Unified Memory — single API over all OnyxKraken memory stores.

Provides one interface to query, store, and manage data across:
  - MemoryStore (JSON) — launch methods, failures, preferences, task history
  - KnowledgeStore (JSON) — learned facts, app knowledge, task patterns
  - ConversationDB (SQLite) — sessions, turns, chat messages
  - EmbeddingStore (JSON cache) — vector similarity

Usage:
    from memory.unified import get_unified_memory

    mem = get_unified_memory()

    # Search across ALL stores at once
    results = mem.search("notepad launch")

    # Store with automatic routing
    mem.remember("notepad", "launch", "Desktop shortcut works best")

    # Get full context for a task
    context = mem.get_task_context("Open Notepad and type Hello")
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_log = logging.getLogger("memory.unified")


@dataclass
class MemoryResult:
    """A single result from unified search."""
    content: str
    source: str          # "memory", "knowledge", "conversation", "embedding"
    category: str        # subcategory within source
    relevance: float     # 0.0 to 1.0
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedMemory:
    """Single interface over all OnyxKraken memory subsystems.

    Lazy-initializes each backend on first access to avoid import
    overhead and circular dependencies.
    """

    def __init__(self):
        self._memory = None      # MemoryStore
        self._knowledge = None   # KnowledgeStore
        self._convo_db = None    # ConversationDB
        self._embeddings = None  # EmbeddingStore

    # ------------------------------------------------------------------
    # Lazy backend access
    # ------------------------------------------------------------------

    @property
    def memory(self):
        if self._memory is None:
            from memory.store import MemoryStore
            self._memory = MemoryStore()
        return self._memory

    @property
    def knowledge(self):
        if self._knowledge is None:
            from core.knowledge import get_knowledge_store
            self._knowledge = get_knowledge_store()
        return self._knowledge

    @property
    def convo_db(self):
        if self._convo_db is None:
            from memory.conversation_db import ConversationDB
            self._convo_db = ConversationDB()
        return self._convo_db

    @property
    def embeddings(self):
        if self._embeddings is None:
            from memory.embeddings import get_embedding_store
            self._embeddings = get_embedding_store()
        return self._embeddings

    # ------------------------------------------------------------------
    # Unified search
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 10,
               sources: Optional[List[str]] = None) -> List[MemoryResult]:
        """Search across all memory stores with unified ranking.

        Args:
            query: Search query string.
            limit: Maximum results to return.
            sources: Optional filter — subset of ["memory", "knowledge",
                     "conversation"]. Defaults to all.

        Returns:
            List of MemoryResult sorted by relevance (highest first).
        """
        if sources is None:
            sources = ["memory", "knowledge", "conversation"]

        results: List[MemoryResult] = []

        # Search MemoryStore (task history + failures)
        if "memory" in sources:
            results.extend(self._search_memory(query, limit))

        # Search KnowledgeStore (hybrid keyword + embedding)
        if "knowledge" in sources:
            results.extend(self._search_knowledge(query, limit))

        # Search ConversationDB (recent turns)
        if "conversation" in sources:
            results.extend(self._search_conversations(query, limit))

        # Sort by relevance, take top N
        results.sort(key=lambda r: r.relevance, reverse=True)
        return results[:limit]

    def _search_memory(self, query: str, limit: int) -> List[MemoryResult]:
        """Search MemoryStore (task history, failures)."""
        results = []
        try:
            # Similar tasks
            similar = self.memory.recall_similar_tasks(query, limit=limit)
            for task in similar:
                results.append(MemoryResult(
                    content=f"[{'OK' if task.get('success') else 'FAIL'}] {task['goal']}",
                    source="memory",
                    category="task_history",
                    relevance=0.7,
                    timestamp=task.get("timestamp", 0),
                    metadata=task,
                ))

            # Recent failures matching query
            query_words = set(query.lower().split())
            for fail in self.memory.recall_failures(limit=limit):
                fail_words = set(fail.get("error", "").lower().split())
                overlap = len(query_words & fail_words)
                if overlap > 0:
                    results.append(MemoryResult(
                        content=f"[FAILURE] {fail.get('action', '?')} on {fail.get('app', '?')}: {fail.get('error', '')}",
                        source="memory",
                        category="failure",
                        relevance=min(0.6, overlap * 0.15),
                        timestamp=fail.get("timestamp", 0),
                        metadata=fail,
                    ))
        except Exception as e:
            _log.debug(f"Memory search error: {e}")
        return results

    def _search_knowledge(self, query: str, limit: int) -> List[MemoryResult]:
        """Search KnowledgeStore (hybrid keyword + embedding)."""
        results = []
        try:
            entries = self.knowledge.search(query, limit=limit)
            for i, entry in enumerate(entries):
                # Approximate relevance from rank position
                relevance = max(0.3, 1.0 - (i * 0.08))
                results.append(MemoryResult(
                    content=entry.get("content", ""),
                    source="knowledge",
                    category=entry.get("category", "general"),
                    relevance=relevance,
                    timestamp=entry.get("created_at", 0),
                    metadata={
                        "id": entry.get("id", ""),
                        "tags": entry.get("tags", []),
                        "access_count": entry.get("access_count", 0),
                    },
                ))
        except Exception as e:
            _log.debug(f"Knowledge search error: {e}")
        return results

    def _search_conversations(self, query: str, limit: int) -> List[MemoryResult]:
        """Search ConversationDB (recent turns)."""
        results = []
        try:
            turns = self.convo_db.get_recent_turns(limit=limit * 2)
            query_words = set(query.lower().split())
            for turn in turns:
                turn_words = set(turn.user_input.lower().split())
                turn_words.update(turn.resolved_goal.lower().split())
                overlap = len(query_words & turn_words)
                if overlap > 0:
                    results.append(MemoryResult(
                        content=f"[{'OK' if turn.success else 'FAIL'}] {turn.resolved_goal} → {turn.result_summary[:100]}",
                        source="conversation",
                        category="turn",
                        relevance=min(0.65, overlap * 0.15),
                        timestamp=turn.timestamp,
                        metadata={
                            "user_input": turn.user_input,
                            "app_name": turn.app_name,
                            "success": turn.success,
                        },
                    ))
        except Exception as e:
            _log.debug(f"Conversation search error: {e}")
        return results

    # ------------------------------------------------------------------
    # Unified store operations
    # ------------------------------------------------------------------

    def remember_task(self, goal: str, app_name: str, steps_planned: int,
                      steps_completed: int, total_time: float, success: bool,
                      notes: str = "") -> None:
        """Record a completed task across all relevant stores.

        Writes to MemoryStore (task_history) and emits memory_updated event.
        """
        self.memory.record_task(
            goal=goal, app_name=app_name,
            steps_planned=steps_planned, steps_completed=steps_completed,
            total_time=total_time, success=success, notes=notes,
        )

        # Extract knowledge pattern from successful tasks
        if success and steps_completed > 0:
            pattern = f"Task succeeded: {goal} ({app_name}, {steps_completed} steps, {total_time:.1f}s)"
            self.knowledge.add_task_pattern(pattern, source=f"task:{goal[:60]}")

        self._emit_event("memory_updated", {
            "category": "task_history",
            "goal": goal,
            "success": success,
        })

    def remember_failure(self, app_name: str, action: str,
                         target: str, error: str) -> None:
        """Record a failure across relevant stores."""
        self.memory.remember_failure(app_name, action, target, error)
        self._emit_event("memory_updated", {
            "category": "failure",
            "app_name": app_name,
            "error": error[:100],
        })

    def add_knowledge(self, content: str, category: str = "general",
                      tags: Optional[List[str]] = None,
                      source: str = "") -> str:
        """Add knowledge and emit event."""
        entry_id = self.knowledge.add(content, category, tags, source)
        self._emit_event("knowledge_added", {
            "entry_id": entry_id,
            "category": category,
            "content": content[:100],
        })
        return entry_id

    def remember_launch(self, app_name: str, method: str, detail: str) -> None:
        """Record a successful launch method."""
        self.memory.remember_launch(app_name, method, detail)

    def recall_launch(self, app_name: str) -> Optional[Dict]:
        """Get the last successful launch method for an app."""
        return self.memory.recall_launch(app_name)

    # ------------------------------------------------------------------
    # Task context builder
    # ------------------------------------------------------------------

    def get_task_context(self, goal: str, app_name: str = "",
                         max_items: int = 8) -> str:
        """Build a rich context string for a task using all memory stores.

        Used by the planner/orchestrator to inject relevant history,
        knowledge, and past failures into LLM prompts.

        Args:
            goal: The current task goal.
            app_name: Optional app name to focus search.
            max_items: Maximum context items to include.

        Returns:
            Formatted context string for LLM injection.
        """
        parts = []

        # 1. Similar past tasks
        similar = self.memory.recall_similar_tasks(goal, limit=3)
        if similar:
            parts.append("PAST SIMILAR TASKS:")
            for t in similar:
                status = "succeeded" if t.get("success") else "failed"
                parts.append(f"  - \"{t['goal'][:60]}\" ({t.get('app', '?')}) — {status}")
                if t.get("notes"):
                    parts.append(f"    Notes: {t['notes'][:80]}")

        # 2. App-specific knowledge
        if app_name:
            app_knowledge = self.knowledge.get_app_knowledge(app_name, limit=3)
            if app_knowledge:
                parts.append(f"KNOWN ABOUT {app_name.upper()}:")
                for k in app_knowledge:
                    parts.append(f"  - {k['content'][:100]}")

        # 3. Recent failures for this app
        if app_name:
            failures = self.memory.recall_failures(app_name, limit=2)
            if failures:
                parts.append(f"RECENT FAILURES ({app_name}):")
                for f in failures:
                    parts.append(f"  - {f.get('action', '?')}: {f.get('error', '?')[:80]}")

        # 4. Launch method if known
        if app_name:
            launch = self.memory.recall_launch(app_name)
            if launch:
                parts.append(f"LAUNCH METHOD: {launch.get('method', '?')} — {launch.get('detail', '?')}")

        if not parts:
            return ""

        return "\n".join(parts[:max_items * 2])  # ~2 lines per item

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Get combined stats from all memory stores."""
        stats = {}
        try:
            mem_data = self.memory.get_all()
            stats["memory"] = {
                "task_history": len(mem_data.get("task_history", [])),
                "failures": len(mem_data.get("failures", [])),
                "launch_methods": len(mem_data.get("launch_methods", {})),
                "preferences": len(mem_data.get("preferences", {})),
            }
        except Exception:
            stats["memory"] = {"error": "unavailable"}

        try:
            stats["knowledge"] = self.knowledge.get_stats()
        except Exception:
            stats["knowledge"] = {"error": "unavailable"}

        try:
            stats["embeddings"] = {
                "available": self.embeddings.is_available(),
                "cache_size": len(self.embeddings._cache),
            }
        except Exception:
            stats["embeddings"] = {"error": "unavailable"}

        return stats

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """Emit a memory event via the event bus."""
        try:
            from core.events import bus
            bus.emit(event_name, data)
        except Exception:
            pass  # Event bus not available — not critical


# ---------------------------------------------------------------------------
# Singleton (delegates to service registry)
# ---------------------------------------------------------------------------

def get_unified_memory() -> UnifiedMemory:
    """Get the unified memory singleton."""
    from core.service_registry import services
    if not services.has("unified_memory"):
        services.register_factory("unified_memory", UnifiedMemory)
    return services.get("unified_memory", UnifiedMemory)
