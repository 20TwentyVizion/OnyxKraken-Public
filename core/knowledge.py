"""Knowledge Store — persistent learned context with RAG retrieval.

Standalone module. Gracefully degrades without OnyxKraken internals:
  - Event emission (core.events) — skipped if unavailable
  - Embedding search (memory.embeddings) — falls back to keyword-only
  - Service registry (core.service_registry) — falls back to simple singleton

Categories:
  - app_knowledge: Learned facts about specific applications
  - task_patterns: Successful task execution patterns
  - user_preferences: Observed user behavior and preferences
  - general: Miscellaneous learned facts

Storage: JSON file at data/knowledge.json
"""

import hashlib
import json
import logging
import os
import time
from typing import Optional

_log = logging.getLogger("knowledge")

try:
    from memory.base_store import BaseJsonStore
except ImportError:
    BaseJsonStore = None


_KNOWLEDGE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "knowledge.json"
)

_DEFAULT = {
    "entries": [],
    "stats": {
        "total_entries": 0,
        "total_retrievals": 0,
    }
}

MAX_ENTRIES = 500


class KnowledgeStore(BaseJsonStore):
    """Persistent knowledge base with semantic retrieval."""

    def __init__(self, path: str = _KNOWLEDGE_FILE):
        super().__init__(path, _DEFAULT)

    # ------------------------------------------------------------------
    # Add knowledge
    # ------------------------------------------------------------------

    def add(self, content: str, category: str = "general",
            tags: Optional[list[str]] = None, source: str = "") -> str:
        """Add a knowledge entry.

        Args:
            content: The knowledge text.
            category: One of app_knowledge, task_patterns, user_preferences, general.
            tags: Optional list of tags for filtering.
            source: Where this knowledge came from (e.g. "task:Open Notepad").

        Returns:
            The entry ID.
        """
        entry_id = hashlib.md5(f"{content}:{time.time()}".encode()).hexdigest()[:12]
        entry = {
            "id": entry_id,
            "content": content,
            "category": category,
            "tags": tags or [],
            "source": source,
            "created_at": time.time(),
            "access_count": 0,
            "last_accessed": 0.0,
        }
        self._data["entries"].append(entry)
        self._data["stats"]["total_entries"] = len(self._data["entries"])

        # Cap
        if len(self._data["entries"]) > MAX_ENTRIES:
            # Remove least-accessed entries first
            self._data["entries"].sort(key=lambda e: e.get("access_count", 0))
            self._data["entries"] = self._data["entries"][-MAX_ENTRIES:]

        self._save()

        # Emit event so subscribers (unified memory, mind, etc.) can react
        try:
            from core.events import bus, KNOWLEDGE_ADDED
            bus.emit(KNOWLEDGE_ADDED, {
                "entry_id": entry_id,
                "category": category,
                "content": content[:100],
                "source": source,
            })
        except Exception:
            pass

        return entry_id

    def add_app_knowledge(self, app_name: str, fact: str, source: str = "") -> str:
        """Convenience: add knowledge about a specific application."""
        return self.add(
            content=f"[{app_name}] {fact}",
            category="app_knowledge",
            tags=[app_name.lower()],
            source=source,
        )

    def add_task_pattern(self, pattern: str, source: str = "") -> str:
        """Convenience: add a successful task execution pattern."""
        return self.add(
            content=pattern,
            category="task_patterns",
            source=source,
        )

    # ------------------------------------------------------------------
    # Retrieve knowledge
    # ------------------------------------------------------------------

    def search(self, query: str, category: Optional[str] = None,
               tags: Optional[list[str]] = None, limit: int = 10) -> list[dict]:
        """Hybrid search — combines keyword + embedding scores for best retrieval.

        Runs both keyword matching and embedding similarity in parallel, then
        merges results via Reciprocal Rank Fusion (RRF). This catches exact-term
        matches that embeddings miss AND semantic matches that keywords miss.
        """
        candidates = self._data["entries"]

        # Filter by category
        if category:
            candidates = [e for e in candidates if e["category"] == category]

        # Filter by tags
        if tags:
            tag_set = set(t.lower() for t in tags)
            candidates = [
                e for e in candidates
                if tag_set & set(t.lower() for t in e.get("tags", []))
            ]

        if not candidates:
            return []

        # --- Keyword scoring ---
        query_words = set(query.lower().split())
        keyword_ranked: list[tuple[int, dict]] = []
        for entry in candidates:
            content_words = set(entry["content"].lower().split())
            overlap = len(query_words & content_words)
            if overlap > 0:
                keyword_ranked.append((overlap, entry))
        keyword_ranked.sort(key=lambda x: x[0], reverse=True)

        # --- Embedding scoring ---
        embed_ranked: list[tuple[float, dict]] = []
        try:
            from memory.embeddings import get_embedding_store
            embed = get_embedding_store()
            if embed.is_available():
                embed_ranked = embed.find_similar(
                    query=query,
                    candidates=candidates,
                    text_key="content",
                    limit=limit * 2,
                    threshold=0.30,
                )
        except Exception as e:
            _log.debug(f"Embedding search unavailable, using keyword-only: {e}")

        # --- Reciprocal Rank Fusion (k=60) ---
        rrf_k = 60
        rrf_scores: dict[str, float] = {}  # entry_id → fused score
        entry_map: dict[str, dict] = {}    # entry_id → entry dict

        for rank, (_, entry) in enumerate(keyword_ranked):
            eid = entry.get("id", id(entry))
            rrf_scores[eid] = rrf_scores.get(eid, 0.0) + 1.0 / (rrf_k + rank + 1)
            entry_map[eid] = entry

        for rank, (_, entry) in enumerate(embed_ranked):
            eid = entry.get("id", id(entry))
            rrf_scores[eid] = rrf_scores.get(eid, 0.0) + 1.0 / (rrf_k + rank + 1)
            entry_map[eid] = entry

        if not rrf_scores:
            return []

        # Sort by fused score
        fused = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        results = [entry_map[eid] for eid, _ in fused[:limit]]

        self._data["stats"]["total_retrievals"] += 1
        for entry in results:
            entry["access_count"] = entry.get("access_count", 0) + 1
            entry["last_accessed"] = time.time()
        self._save()

        return results

    def get_app_knowledge(self, app_name: str, limit: int = 10) -> list[dict]:
        """Get all knowledge about a specific application."""
        return self.search(
            query=app_name,
            category="app_knowledge",
            tags=[app_name.lower()],
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def remove(self, entry_id: str) -> bool:
        """Remove a knowledge entry by ID."""
        before = len(self._data["entries"])
        self._data["entries"] = [e for e in self._data["entries"] if e["id"] != entry_id]
        if len(self._data["entries"]) < before:
            self._data["stats"]["total_entries"] = len(self._data["entries"])
            self._save()
            return True
        return False

    def get_stats(self) -> dict:
        return {
            **self._data["stats"],
            "entries_by_category": self._count_by_category(),
        }

    def _count_by_category(self) -> dict:
        counts = {}
        for entry in self._data["entries"]:
            cat = entry.get("category", "general")
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def get_all(self) -> list[dict]:
        return list(self._data["entries"])


# Singleton — uses ServiceRegistry when available, simple global otherwise

_standalone_instance: KnowledgeStore | None = None


def get_knowledge_store() -> KnowledgeStore:
    global _standalone_instance
    try:
        from core.service_registry import services
        if not services.has("knowledge"):
            services.register_factory("knowledge", KnowledgeStore)
        return services.get("knowledge", KnowledgeStore)
    except ImportError:
        if _standalone_instance is None:
            _standalone_instance = KnowledgeStore()
        return _standalone_instance
