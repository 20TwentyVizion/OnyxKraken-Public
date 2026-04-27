"""Toolsmith Bridge — wires the standalone tool ecosystem into OnyxKraken.

core/toolsmith.py has zero Onyx imports for its core registry operations.
This bridge exposes toolsmith as a service and emits events when tools
are registered, launched, verified, or deleted.

Events emitted:
  toolsmith:registered   — tool added/updated      {name, status}
  toolsmith:launched     — tool script launched     {name, pid}
  toolsmith:verified     — tool marked verified     {name}
  toolsmith:deleted      — tool removed             {name}

Events consumed:
  app_ready              — log available tools
  app_shutting_down      — cleanup
"""

import logging
from typing import Any, Dict, List, Optional

from core.plugins.protocol import OnyxPlugin, PluginMeta

_log = logging.getLogger("core.plugins.bridge_toolsmith")

TOOLSMITH_REGISTERED = "toolsmith:registered"
TOOLSMITH_LAUNCHED = "toolsmith:launched"
TOOLSMITH_VERIFIED = "toolsmith:verified"
TOOLSMITH_DELETED = "toolsmith:deleted"


class ToolsmithBridge(OnyxPlugin):
    """Bridge between standalone core/toolsmith.py and OnyxKraken."""

    def __init__(self):
        super().__init__()
        self._bus = None
        self._event_handlers = {}

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="toolsmith",
            display_name="Toolsmith",
            version="1.0.0",
            description="Self-built tools ecosystem — register, launch, verify, prefer.",
            standalone=True,
            category="core",
            services=["toolsmith"],
            events_emitted=[
                TOOLSMITH_REGISTERED, TOOLSMITH_LAUNCHED,
                TOOLSMITH_VERIFIED, TOOLSMITH_DELETED,
            ],
            events_consumed=["app_ready", "app_shutting_down"],
            dependencies=[],
            tags=["tools", "scripts", "automation", "self-build"],
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def register(self, registry, event_bus) -> None:
        self._bus = event_bus
        registry.register("toolsmith", self, replace=True)

        self._subscribe(event_bus, "app_ready", self._on_app_ready)
        self._subscribe(event_bus, "app_shutting_down", self._on_shutdown)
        _log.info("Toolsmith bridge registered.")

    def unregister(self, registry, event_bus) -> None:
        for event_name, handler in self._event_handlers.items():
            try:
                event_bus.off(event_name, handler)
            except Exception:
                pass
        self._event_handlers.clear()
        _log.info("Toolsmith bridge unregistered.")

    def health(self) -> Dict[str, Any]:
        base = super().health()
        try:
            from core.toolsmith import list_tools
            tools = list_tools()
            base["tool_count"] = len(tools)
            base["verified_count"] = sum(1 for t in tools if t.is_verified)
            base["preferred_count"] = sum(1 for t in tools if t.is_preferred)
        except Exception:
            base["tool_count"] = 0
        return base

    # ------------------------------------------------------------------
    # Onyx-facing API
    # ------------------------------------------------------------------

    def list_tools(self) -> List[Dict]:
        """List all registered tools."""
        from core.toolsmith import list_tools
        return [{"name": t.name, "display_name": t.display_name,
                 "status": t.status, "description": t.description}
                for t in list_tools()]

    def get_tool(self, name: str) -> Optional[Dict]:
        """Get a single tool by name."""
        from core.toolsmith import get_tool
        t = get_tool(name)
        if t:
            return {"name": t.name, "display_name": t.display_name,
                    "status": t.status, "description": t.description,
                    "script_path": t.script_path, "replaces": t.replaces,
                    "capabilities": t.capabilities}
        return None

    def register_tool(self, **kwargs) -> Dict:
        """Register a tool with event emission."""
        from core.toolsmith import register_tool, ToolEntry
        entry = ToolEntry(**kwargs)
        register_tool(entry)
        if self._bus:
            self._bus.emit(TOOLSMITH_REGISTERED, {
                "name": entry.name,
                "status": entry.status,
            })
        return {"ok": True, "name": entry.name}

    def launch_tool(self, name: str) -> Dict:
        """Launch a tool's script."""
        from core.toolsmith import get_tool, launch_tool
        tool = get_tool(name)
        if not tool:
            return {"ok": False, "error": f"Tool '{name}' not found"}
        try:
            proc = launch_tool(name)
            if self._bus:
                self._bus.emit(TOOLSMITH_LAUNCHED, {
                    "name": name,
                    "pid": proc.pid if proc else 0,
                })
            return {"ok": True, "name": name, "pid": proc.pid if proc else 0}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def verify_tool(self, name: str) -> Dict:
        """Mark a tool as verified."""
        from core.toolsmith import verify_tool
        ok = verify_tool(name)
        if ok and self._bus:
            self._bus.emit(TOOLSMITH_VERIFIED, {"name": name})
        return {"ok": ok}

    def delete_tool(self, name: str) -> Dict:
        """Delete a tool."""
        from core.toolsmith import delete_tool
        ok = delete_tool(name)
        if ok and self._bus:
            self._bus.emit(TOOLSMITH_DELETED, {"name": name})
        return {"ok": ok}

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_app_ready(self, data: Dict) -> None:
        try:
            from core.toolsmith import list_tools
            tools = list_tools()
            _log.info("Toolsmith: %d tools available (%d verified).",
                      len(tools), sum(1 for t in tools if t.is_verified))
        except Exception:
            pass

    def _on_shutdown(self, data: Dict) -> None:
        _log.info("Toolsmith: shutdown acknowledged.")

    def _subscribe(self, bus, event_name: str, handler):
        bus.on(event_name, handler)
        self._event_handlers[event_name] = handler


plugin = ToolsmithBridge()
