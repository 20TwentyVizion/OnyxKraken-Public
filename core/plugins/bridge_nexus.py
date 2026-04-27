"""Nexus Bridge — wires the standalone Neural Organizer into OnyxKraken.

The nexus/ package has zero Onyx imports. This bridge is the ONLY file
that imports from both sides. It translates between:
  - ServiceRegistry ↔ NexusEngine instance
  - EventBus events ↔ NexusEngine method calls
  - OnyxKraken knowledge/memory events ↔ Nexus ingest triggers

Events emitted:
  nexus:ingested     — after successful ingest  {thoughts_created, thoughts_merged, source}
  nexus:queried      — after query              {query, match_count}
  nexus:synthesized  — after synthesis           {hypotheses_created, clusters_found}
  nexus:status       — periodic health ping      {nodes, edges, density}

Events consumed:
  knowledge_added    — auto-ingest new knowledge entries
  task_completed     — ingest task summaries for pattern mining
  app_shutting_down  — clean shutdown
"""

import logging
from typing import Any, Dict

from core.plugins.protocol import OnyxPlugin, PluginMeta

_log = logging.getLogger("core.plugins.bridge_nexus")

# Event name constants
NEXUS_INGESTED = "nexus:ingested"
NEXUS_QUERIED = "nexus:queried"
NEXUS_SYNTHESIZED = "nexus:synthesized"
NEXUS_STATUS = "nexus:status"


class NexusBridge(OnyxPlugin):
    """Bridge between standalone nexus/ and OnyxKraken infrastructure."""

    def __init__(self, config=None):
        super().__init__()
        self._config = config  # Optional NexusConfig override
        self._engine = None
        self._bus = None
        self._event_handlers = {}

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="nexus",
            display_name="Neural Organizer",
            version="1.0.0",
            description="Knowledge graph engine — ingest, chunk, embed, link, synthesize.",
            standalone=True,
            category="core",
            services=["nexus", "nexus_engine"],
            events_emitted=[
                NEXUS_INGESTED, NEXUS_QUERIED,
                NEXUS_SYNTHESIZED, NEXUS_STATUS,
            ],
            events_consumed=[
                "knowledge_added", "task_completed", "app_shutting_down",
            ],
            dependencies=[],
            tags=["knowledge", "graph", "embeddings", "synthesis"],
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def register(self, registry, event_bus) -> None:
        """Register NexusEngine as a service and subscribe to events."""
        self._bus = event_bus

        # Lazy factory — engine is created on first use
        registry.register_factory("nexus", self._create_engine, replace=True)
        registry.register_factory("nexus_engine", self._create_engine, replace=True)

        # Subscribe to Onyx events
        self._subscribe(event_bus, "knowledge_added", self._on_knowledge_added)
        self._subscribe(event_bus, "task_completed", self._on_task_completed)
        self._subscribe(event_bus, "app_shutting_down", self._on_shutdown)

        _log.info("Nexus bridge registered.")

    def unregister(self, registry, event_bus) -> None:
        """Remove services and unsubscribe."""
        # Unsubscribe all handlers
        for event_name, handler in self._event_handlers.items():
            try:
                event_bus.off(event_name, handler)
            except Exception:
                pass
        self._event_handlers.clear()

        # Shutdown engine if active
        if self._engine:
            self._engine.shutdown()
            self._engine = None

        _log.info("Nexus bridge unregistered.")

    def start(self) -> None:
        """Start the engine's folder watcher if configured."""
        super().start()
        # Engine is lazy — don't force creation here.
        # Watcher starts on first ingest or explicit call.

    def stop(self) -> None:
        """Stop background work."""
        if self._engine:
            self._engine.stop_watching()
        super().stop()

    def health(self) -> Dict[str, Any]:
        """Report Nexus health."""
        base = super().health()
        if self._engine:
            status = self._engine.status()
            base.update({
                "nodes": status.get("nodes", 0),
                "edges": status.get("edges", 0),
                "embeddings_cached": status.get("embeddings_cached", 0),
                "watcher_active": status.get("watcher_active", False),
            })
        return base

    # ------------------------------------------------------------------
    # Engine creation
    # ------------------------------------------------------------------

    def _create_engine(self):
        """Factory for lazy NexusEngine creation."""
        if self._engine is None:
            from nexus.engine import NexusEngine
            from nexus.config import NexusConfig
            self._engine = NexusEngine(self._config or NexusConfig())
            _log.info("NexusEngine created: %d nodes, %d edges.",
                      self._engine.graph.node_count, self._engine.graph.edge_count)
        return self._engine

    # ------------------------------------------------------------------
    # Onyx-facing API (called by other Onyx subsystems via registry)
    # ------------------------------------------------------------------

    def ingest(self, text_or_path: str, source: str = "") -> Dict:
        """Ingest wrapper that emits events."""
        engine = self._create_engine()
        result = engine.ingest(text_or_path, source=source)

        if self._bus and result.ok:
            self._bus.emit(NEXUS_INGESTED, {
                "thoughts_created": result.thoughts_created,
                "thoughts_merged": result.thoughts_merged,
                "source": result.source,
                "thought_ids": result.thought_ids,
            })

        return {
            "ok": result.ok,
            "thoughts_created": result.thoughts_created,
            "thoughts_merged": result.thoughts_merged,
            "source": result.source,
        }

    def query(self, search: str, limit: int = 10, depth: int = 1) -> Dict:
        """Query wrapper that emits events."""
        engine = self._create_engine()
        result = engine.query(search, limit=limit, depth=depth)

        if self._bus:
            self._bus.emit(NEXUS_QUERIED, {
                "query": search,
                "match_count": len(result.thoughts),
            })

        return {
            "query": result.query,
            "thoughts": [t.to_dict() for t in result.thoughts],
            "links": [l.to_dict() for l in result.links],
            "total_matches": result.total_matches,
        }

    def synthesize(self) -> Dict:
        """Synthesis wrapper that emits events."""
        engine = self._create_engine()
        result = engine.synthesize()

        if self._bus:
            self._bus.emit(NEXUS_SYNTHESIZED, {
                "hypotheses_created": result.hypotheses_created,
                "clusters_found": result.clusters_found,
            })

        return {
            "ok": result.ok,
            "hypotheses_created": result.hypotheses_created,
            "clusters_found": result.clusters_found,
        }

    # ------------------------------------------------------------------
    # Event handlers (Onyx → Nexus)
    # ------------------------------------------------------------------

    def _on_knowledge_added(self, data: Dict) -> None:
        """When OnyxKraken learns something, ingest it into Nexus."""
        content = data.get("content", "")
        category = data.get("category", "")
        if content and len(content) > 20:
            source = f"onyx:knowledge:{category}" if category else "onyx:knowledge"
            try:
                self.ingest(content, source=source)
            except Exception as e:
                _log.debug("Auto-ingest from knowledge_added failed: %s", e)

    def _on_task_completed(self, data: Dict) -> None:
        """When a task completes, ingest the summary for pattern mining."""
        goal = data.get("goal", "")
        app_name = data.get("app_name", "")
        success = data.get("success", False)
        if goal and success:
            summary = f"Task completed: {goal}"
            if app_name:
                summary += f" (app: {app_name})"
            try:
                self.ingest(summary, source="onyx:task")
            except Exception as e:
                _log.debug("Auto-ingest from task_completed failed: %s", e)

    def _on_shutdown(self, data: Dict) -> None:
        """Clean shutdown on app exit."""
        if self._engine:
            self._engine.shutdown()
            _log.info("NexusEngine shut down via app_shutting_down event.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _subscribe(self, bus, event_name: str, handler):
        """Subscribe and track for later cleanup."""
        bus.on(event_name, handler)
        self._event_handlers[event_name] = handler


# ---------------------------------------------------------------------------
# Module-level instance — auto-discovered by PluginLoader
# ---------------------------------------------------------------------------

plugin = NexusBridge()
