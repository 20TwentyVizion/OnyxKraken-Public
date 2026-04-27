"""Desktop Bridge — wires the standalone desktop/ package into OnyxKraken.

desktop/controller.py is now standalone (injectable config).
This bridge injects real config values and exposes desktop automation
as a service with event emission.

Events emitted:
  desktop:app_launched     — after launch            {name, path}
  desktop:window_found     — after find_window       {title}
  desktop:clicked          — after click             {x, y}
  desktop:typed            — after type_text         {length}

Events consumed:
  app_ready               — inject config
  app_shutting_down       — cleanup
"""

import logging
from typing import Any, Dict, Optional

from core.plugins.protocol import OnyxPlugin, PluginMeta

_log = logging.getLogger("core.plugins.bridge_desktop")

DESKTOP_APP_LAUNCHED = "desktop:app_launched"
DESKTOP_WINDOW_FOUND = "desktop:window_found"
DESKTOP_CLICKED = "desktop:clicked"
DESKTOP_TYPED = "desktop:typed"


class DesktopBridge(OnyxPlugin):
    """Bridge between standalone desktop/ and OnyxKraken infrastructure."""

    def __init__(self):
        super().__init__()
        self._bus = None
        self._event_handlers = {}

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="desktop",
            display_name="Desktop Controller",
            version="1.0.0",
            description="OS-level window management, app launching, and UI interaction.",
            standalone=True,
            category="core",
            services=["desktop"],
            events_emitted=[
                DESKTOP_APP_LAUNCHED, DESKTOP_WINDOW_FOUND,
                DESKTOP_CLICKED, DESKTOP_TYPED,
            ],
            events_consumed=["app_ready", "app_shutting_down"],
            dependencies=[],
            tags=["desktop", "windows", "automation", "pyautogui"],
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def register(self, registry, event_bus) -> None:
        self._bus = event_bus
        registry.register("desktop", self, replace=True)

        self._subscribe(event_bus, "app_ready", self._on_app_ready)
        self._subscribe(event_bus, "app_shutting_down", self._on_shutdown)

        # Inject config immediately
        self._inject_config()

        _log.info("Desktop bridge registered.")

    def unregister(self, registry, event_bus) -> None:
        for event_name, handler in self._event_handlers.items():
            try:
                event_bus.off(event_name, handler)
            except Exception:
                pass
        self._event_handlers.clear()
        _log.info("Desktop bridge unregistered.")

    def health(self) -> Dict[str, Any]:
        base = super().health()
        try:
            from desktop.controller import list_windows
            base["visible_windows"] = len(list_windows())
        except Exception:
            base["visible_windows"] = -1
        return base

    # ------------------------------------------------------------------
    # Config injection
    # ------------------------------------------------------------------

    def _inject_config(self):
        """Inject OnyxKraken config values into desktop.controller."""
        try:
            import config as onyx_config
            from desktop.controller import configure
            configure({
                "app_load_timeout": getattr(onyx_config, "APP_LOAD_TIMEOUT", 10),
            })
        except ImportError as e:
            _log.debug("Could not inject desktop config: %s", e)

    # ------------------------------------------------------------------
    # Onyx-facing API
    # ------------------------------------------------------------------

    def launch_app(self, name_or_path: str) -> Dict:
        """Launch an app by name (desktop item search) or path."""
        from desktop.controller import launch_desktop_item, launch_app, find_desktop_item
        import os

        # Try desktop item first
        item = find_desktop_item(name_or_path)
        if item:
            proc = launch_app(item["path"])
            if self._bus:
                self._bus.emit(DESKTOP_APP_LAUNCHED, {
                    "name": item["name"], "path": item["path"],
                })
            return {"ok": True, "name": item["name"], "path": item["path"]}

        # Try direct path
        if os.path.exists(name_or_path):
            proc = launch_app(name_or_path)
            if self._bus:
                self._bus.emit(DESKTOP_APP_LAUNCHED, {
                    "name": os.path.basename(name_or_path), "path": name_or_path,
                })
            return {"ok": True, "path": name_or_path}

        return {"ok": False, "error": f"Could not find '{name_or_path}'"}

    def find_window(self, title: str) -> Dict:
        """Find a window by title fragment."""
        from desktop.controller import find_window
        win = find_window(title)
        if win and self._bus:
            self._bus.emit(DESKTOP_WINDOW_FOUND, {"title": title})
        return {"ok": win is not None, "found": win is not None}

    def list_windows(self):
        """List all visible windows."""
        from desktop.controller import list_windows
        return list_windows()

    def click(self, x: int, y: int) -> Dict:
        """Click at screen coordinates."""
        from desktop.controller import click_coords
        click_coords(x, y)
        if self._bus:
            self._bus.emit(DESKTOP_CLICKED, {"x": x, "y": y})
        return {"ok": True}

    def type_text(self, text: str) -> Dict:
        """Type text via clipboard paste."""
        from desktop.controller import type_text
        type_text(text)
        if self._bus:
            self._bus.emit(DESKTOP_TYPED, {"length": len(text)})
        return {"ok": True}

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_app_ready(self, data: Dict) -> None:
        self._inject_config()

    def _on_shutdown(self, data: Dict) -> None:
        _log.info("Desktop: shutdown acknowledged.")

    def _subscribe(self, bus, event_name: str, handler):
        bus.on(event_name, handler)
        self._event_handlers[event_name] = handler


plugin = DesktopBridge()
