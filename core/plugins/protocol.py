"""OnyxPlugin protocol — the contract for standalone↔Onyx bridges.

Any bridge module implements this protocol. The standalone package itself
never touches this — only the bridge adapter does.

Design rules:
  - Bridges are THIN. Business logic lives in the standalone package.
  - Bridges translate between Onyx events ↔ standalone method calls.
  - register() and unregister() are always safe to call multiple times.
  - health() returns a dict with at minimum {"ok": bool, "message": str}.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class PluginMeta:
    """Metadata about a plugin — used for discovery, display, and licensing."""
    name: str                              # machine name: "nexus", "oms", "webvision"
    display_name: str                      # human name: "Neural Organizer"
    version: str = "0.1.0"
    description: str = ""
    author: str = "OnyxKraken"
    standalone: bool = True                # can it run without Onyx?
    category: str = "core"                 # core | addon | community
    services: List[str] = field(default_factory=list)   # service names it registers
    events_emitted: List[str] = field(default_factory=list)  # events it emits
    events_consumed: List[str] = field(default_factory=list)  # events it listens to
    dependencies: List[str] = field(default_factory=list)  # other plugin names required
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "version": self.version,
            "description": self.description,
            "standalone": self.standalone,
            "category": self.category,
            "services": self.services,
            "events_emitted": self.events_emitted,
            "events_consumed": self.events_consumed,
            "dependencies": self.dependencies,
            "tags": self.tags,
        }


class OnyxPlugin(ABC):
    """Base class for all Onyx plugin bridges.

    Subclass this in core/plugins/bridge_xxx.py to wire a standalone
    package into OnyxKraken. The standalone package itself should
    never import this class.

    Lifecycle:
        __init__()   → create the bridge (lightweight, no side effects)
        register()   → register services + subscribe to events
        start()      → begin background work (watchers, timers, etc.)
        health()     → report health status
        stop()       → halt background work
        unregister() → remove from registry
    """

    def __init__(self):
        self._registered = False
        self._started = False
        self._start_time: float = 0

    # ------------------------------------------------------------------
    # Required overrides
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def meta(self) -> PluginMeta:
        """Return plugin metadata."""
        ...

    @abstractmethod
    def register(self, registry, event_bus) -> None:
        """Register services and subscribe to events.

        Args:
            registry: ServiceRegistry instance.
            event_bus: EventBus instance.
        """
        ...

    @abstractmethod
    def unregister(self, registry, event_bus) -> None:
        """Remove services and unsubscribe from events."""
        ...

    # ------------------------------------------------------------------
    # Optional overrides
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start background work. Called after register()."""
        self._started = True
        self._start_time = time.time()

    def stop(self) -> None:
        """Stop background work. Called before unregister()."""
        self._started = False

    def health(self) -> Dict[str, Any]:
        """Return health status.

        Returns:
            Dict with at minimum: {"ok": bool, "message": str}
        """
        return {
            "ok": self._registered,
            "message": "running" if self._started else "registered" if self._registered else "idle",
            "uptime": time.time() - self._start_time if self._start_time else 0,
        }

    def on_app_ready(self) -> None:
        """Called when the full OnyxKraken app is ready."""
        pass

    def on_shutdown(self) -> None:
        """Called when OnyxKraken is shutting down."""
        self.stop()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def is_registered(self) -> bool:
        return self._registered

    @property
    def is_started(self) -> bool:
        return self._started

    def __repr__(self) -> str:
        state = "started" if self._started else "registered" if self._registered else "idle"
        return f"<{self.meta.display_name} [{state}] v{self.meta.version}>"
