"""OMS Bridge — wires the Onyx Management Station into OnyxKraken.

OMS is already standalone (python -m oms). This bridge exposes it as a
service so other Onyx subsystems can trigger health checks, scans, and
repairs programmatically via the registry.

Events emitted:
  oms:health_checked  — after a health check   {findings_count, pass_rate}
  oms:repair_run      — after auto-repair       {fixed_count, failed_count}

Events consumed:
  app_ready           — run initial health check
  app_shutting_down   — final status log
"""

import logging
from typing import Any, Dict

from core.plugins.protocol import OnyxPlugin, PluginMeta

_log = logging.getLogger("core.plugins.bridge_oms")

OMS_HEALTH_CHECKED = "oms:health_checked"
OMS_REPAIR_RUN = "oms:repair_run"


class OMSBridge(OnyxPlugin):
    """Bridge between standalone oms/ and OnyxKraken infrastructure."""

    def __init__(self):
        super().__init__()
        self._bus = None
        self._event_handlers = {}

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="oms",
            display_name="Onyx Management Station",
            version="0.1.0",
            description="Health checks, code auditing, auto-repair, and monitoring.",
            standalone=True,
            category="core",
            services=["oms"],
            events_emitted=[OMS_HEALTH_CHECKED, OMS_REPAIR_RUN],
            events_consumed=["app_ready", "app_shutting_down"],
            dependencies=[],
            tags=["management", "health", "repair", "monitoring"],
        )

    def register(self, registry, event_bus) -> None:
        self._bus = event_bus
        registry.register_factory("oms", self._create_oms, replace=True)
        self._subscribe(event_bus, "app_ready", self._on_app_ready)
        self._subscribe(event_bus, "app_shutting_down", self._on_shutdown)
        _log.info("OMS bridge registered.")

    def unregister(self, registry, event_bus) -> None:
        for event_name, handler in self._event_handlers.items():
            try:
                event_bus.off(event_name, handler)
            except Exception:
                pass
        self._event_handlers.clear()
        _log.info("OMS bridge unregistered.")

    def health(self) -> Dict[str, Any]:
        base = super().health()
        base["description"] = "Management station for ecosystem health"
        return base

    def _create_oms(self) -> Dict[str, Any]:
        """Return a dict of OMS functions for service consumers."""
        from oms.health import HealthChecker
        from oms.scanner import EcosystemScanner
        from oms.config import OMS_CONFIG

        return {
            "health_checker": HealthChecker(OMS_CONFIG),
            "scanner": EcosystemScanner(OMS_CONFIG),
            "config": OMS_CONFIG,
        }

    def _on_app_ready(self, data: Dict) -> None:
        _log.info("OMS: app ready — standing by for management commands.")

    def _on_shutdown(self, data: Dict) -> None:
        _log.info("OMS: app shutting down.")

    def _subscribe(self, bus, event_name: str, handler):
        bus.on(event_name, handler)
        self._event_handlers[event_name] = handler


plugin = OMSBridge()
