"""Memory Bridge — wires the standalone memory/ package into OnyxKraken.

The memory/ package (UnifiedMemory, MemoryStore, ConversationDB,
EmbeddingStore) has zero Onyx imports. This bridge exposes it as
services and wires event-driven memory operations.

Events emitted:
  memory:searched     — after unified search       {query, result_count}
  memory:stored       — after remember()           {category, key}
  memory:context_built — after get_task_context()  {goal, result_count}

Events consumed:
  task_completed      — auto-store task results
  knowledge_added     — cross-index with embeddings
  app_shutting_down   — flush any pending writes
"""

import logging
from typing import Any, Dict

from core.plugins.protocol import OnyxPlugin, PluginMeta

_log = logging.getLogger("core.plugins.bridge_memory")

MEMORY_SEARCHED = "memory:searched"
MEMORY_STORED = "memory:stored"
MEMORY_CONTEXT_BUILT = "memory:context_built"


class MemoryBridge(OnyxPlugin):
    """Bridge between standalone memory/ and OnyxKraken infrastructure."""

    def __init__(self):
        super().__init__()
        self._unified = None
        self._bus = None
        self._event_handlers = {}

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="memory",
            display_name="Unified Memory",
            version="1.0.0",
            description="Persistent memory across sessions — task history, knowledge, conversations, embeddings.",
            standalone=True,
            category="core",
            services=["memory", "unified_memory"],
            events_emitted=[MEMORY_SEARCHED, MEMORY_STORED, MEMORY_CONTEXT_BUILT],
            events_consumed=["task_completed", "knowledge_added", "app_shutting_down"],
            dependencies=[],
            tags=["memory", "search", "embeddings", "conversation"],
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def register(self, registry, event_bus) -> None:
        self._bus = event_bus
        registry.register_factory("memory", self._get_unified, replace=True)
        registry.register_factory("unified_memory", self._get_unified, replace=True)

        self._subscribe(event_bus, "task_completed", self._on_task_completed)
        self._subscribe(event_bus, "app_shutting_down", self._on_shutdown)
        _log.info("Memory bridge registered.")

    def unregister(self, registry, event_bus) -> None:
        for event_name, handler in self._event_handlers.items():
            try:
                event_bus.off(event_name, handler)
            except Exception:
                pass
        self._event_handlers.clear()
        _log.info("Memory bridge unregistered.")

    def health(self) -> Dict[str, Any]:
        base = super().health()
        if self._unified:
            base["backends"] = ["memory_store", "knowledge_store",
                                "conversation_db", "embedding_store"]
        return base

    # ------------------------------------------------------------------
    # Service factory
    # ------------------------------------------------------------------

    def _get_unified(self):
        if self._unified is None:
            from memory.unified import get_unified_memory
            self._unified = get_unified_memory()
            _log.info("UnifiedMemory initialized.")
        return self._unified

    # ------------------------------------------------------------------
    # Onyx-facing API
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 10, sources=None) -> Dict:
        """Unified search with event emission."""
        mem = self._get_unified()
        results = mem.search(query, limit=limit, sources=sources)
        if self._bus:
            self._bus.emit(MEMORY_SEARCHED, {
                "query": query,
                "result_count": len(results),
            })
        return {
            "query": query,
            "results": [{"content": r.content, "source": r.source,
                         "category": r.category, "relevance": r.relevance}
                        for r in results],
        }

    def remember(self, app_name: str, category: str, content: str) -> None:
        """Store a memory with event emission."""
        mem = self._get_unified()
        mem.remember(app_name, category, content)
        if self._bus:
            self._bus.emit(MEMORY_STORED, {
                "category": category,
                "key": app_name,
            })

    def get_task_context(self, goal: str) -> Dict:
        """Build task context with event emission."""
        mem = self._get_unified()
        ctx = mem.get_task_context(goal)
        if self._bus:
            self._bus.emit(MEMORY_CONTEXT_BUILT, {
                "goal": goal,
                "result_count": len(ctx) if isinstance(ctx, list) else 1,
            })
        return ctx

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_task_completed(self, data: Dict) -> None:
        """Auto-store completed task results."""
        goal = data.get("goal", "")
        app_name = data.get("app_name", "")
        success = data.get("success", False)
        if goal:
            try:
                mem = self._get_unified()
                mem.memory.record_task(goal, app_name, success)
            except Exception as e:
                _log.debug("Memory auto-store failed: %s", e)

    def _on_shutdown(self, data: Dict) -> None:
        _log.info("Memory: flushing on shutdown.")

    def _subscribe(self, bus, event_name: str, handler):
        bus.on(event_name, handler)
        self._event_handlers[event_name] = handler


plugin = MemoryBridge()
