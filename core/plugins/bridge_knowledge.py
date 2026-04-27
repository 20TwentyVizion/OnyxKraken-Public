"""Knowledge Bridge — wires the standalone knowledge store into OnyxKraken.

core/knowledge.py is now standalone (graceful degradation for events,
embeddings, and service registry). This bridge exposes KnowledgeStore
as a service and emits events.

Events emitted:
  knowledge:added       — entry added               {entry_id, category}
  knowledge:searched    — search performed           {query, result_count}
  knowledge:removed     — entry removed              {entry_id}

Events consumed:
  task_completed        — auto-learn task patterns
  app_shutting_down     — flush
"""

import logging
from typing import Any, Dict, List, Optional

from core.plugins.protocol import OnyxPlugin, PluginMeta

_log = logging.getLogger("core.plugins.bridge_knowledge")

KNOWLEDGE_ADDED = "knowledge:added"
KNOWLEDGE_SEARCHED = "knowledge:searched"
KNOWLEDGE_REMOVED = "knowledge:removed"


class KnowledgeBridge(OnyxPlugin):
    """Bridge between standalone core/knowledge.py and OnyxKraken."""

    def __init__(self):
        super().__init__()
        self._store = None
        self._bus = None
        self._event_handlers = {}

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="knowledge",
            display_name="Knowledge Store",
            version="1.0.0",
            description="Persistent learned facts with hybrid keyword + embedding retrieval.",
            standalone=True,
            category="core",
            services=["knowledge"],
            events_emitted=[KNOWLEDGE_ADDED, KNOWLEDGE_SEARCHED, KNOWLEDGE_REMOVED],
            events_consumed=["task_completed", "app_shutting_down"],
            dependencies=[],
            tags=["knowledge", "facts", "patterns", "rag"],
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def register(self, registry, event_bus) -> None:
        self._bus = event_bus
        registry.register_factory("knowledge", self._get_store, replace=True)

        self._subscribe(event_bus, "task_completed", self._on_task_completed)
        self._subscribe(event_bus, "app_shutting_down", self._on_shutdown)
        _log.info("Knowledge bridge registered.")

    def unregister(self, registry, event_bus) -> None:
        for event_name, handler in self._event_handlers.items():
            try:
                event_bus.off(event_name, handler)
            except Exception:
                pass
        self._event_handlers.clear()
        _log.info("Knowledge bridge unregistered.")

    def health(self) -> Dict[str, Any]:
        base = super().health()
        if self._store:
            stats = self._store.get_stats()
            base["total_entries"] = stats.get("total_entries", 0)
            base["total_retrievals"] = stats.get("total_retrievals", 0)
        return base

    # ------------------------------------------------------------------
    # Service factory
    # ------------------------------------------------------------------

    def _get_store(self):
        if self._store is None:
            from core.knowledge import KnowledgeStore
            self._store = KnowledgeStore()
            _log.info("KnowledgeStore initialized.")
        return self._store

    # ------------------------------------------------------------------
    # Onyx-facing API
    # ------------------------------------------------------------------

    def add(self, content: str, category: str = "general",
            tags: list = None, source: str = "") -> Dict:
        """Add knowledge with event emission."""
        store = self._get_store()
        entry_id = store.add(content, category=category, tags=tags, source=source)
        if self._bus:
            self._bus.emit(KNOWLEDGE_ADDED, {
                "entry_id": entry_id, "category": category,
            })
        return {"ok": True, "entry_id": entry_id}

    def search(self, query: str, category: str = None,
               tags: list = None, limit: int = 10) -> Dict:
        """Search knowledge with event emission."""
        store = self._get_store()
        results = store.search(query, category=category, tags=tags, limit=limit)
        if self._bus:
            self._bus.emit(KNOWLEDGE_SEARCHED, {
                "query": query, "result_count": len(results),
            })
        return {"query": query, "results": results}

    def remove(self, entry_id: str) -> Dict:
        """Remove knowledge entry."""
        store = self._get_store()
        ok = store.remove(entry_id)
        if ok and self._bus:
            self._bus.emit(KNOWLEDGE_REMOVED, {"entry_id": entry_id})
        return {"ok": ok}

    def get_stats(self) -> Dict:
        """Get knowledge store stats."""
        store = self._get_store()
        return store.get_stats()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_task_completed(self, data: Dict) -> None:
        """Auto-learn from completed tasks."""
        goal = data.get("goal", "")
        app_name = data.get("app_name", "")
        success = data.get("success", False)
        steps = data.get("steps", [])
        if goal and success and steps:
            pattern = f"Task: {goal}"
            if app_name:
                pattern += f" | App: {app_name}"
            pattern += f" | Steps: {len(steps)}"
            try:
                self._get_store().add_task_pattern(pattern, source="auto")
            except Exception as e:
                _log.debug("Knowledge auto-learn failed: %s", e)

    def _on_shutdown(self, data: Dict) -> None:
        _log.info("Knowledge: shutdown acknowledged.")

    def _subscribe(self, bus, event_name: str, handler):
        bus.on(event_name, handler)
        self._event_handlers[event_name] = handler


plugin = KnowledgeBridge()
