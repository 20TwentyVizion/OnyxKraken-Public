"""Personality Bridge — wires the standalone personality system into OnyxKraken.

core/personality.py is now standalone (stdlib logging only).
This bridge exposes personality presets as a service and emits events
when presets are loaded or switched.

Events emitted:
  personality:loaded    — preset loaded from file    {name, version}
  personality:switched  — active preset changed      {name}

Events consumed:
  app_ready            — load default preset
  app_shutting_down    — cleanup
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from core.plugins.protocol import OnyxPlugin, PluginMeta

_log = logging.getLogger("core.plugins.bridge_personality")

PERSONALITY_LOADED = "personality:loaded"
PERSONALITY_SWITCHED = "personality:switched"


class PersonalityBridge(OnyxPlugin):
    """Bridge between standalone core/personality.py and OnyxKraken."""

    def __init__(self):
        super().__init__()
        self._active_preset = None
        self._bus = None
        self._event_handlers = {}

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="personality",
            display_name="Personality Engine",
            version="1.0.0",
            description="Customizable personality presets — communication style, humor, verbosity.",
            standalone=True,
            category="core",
            services=["personality"],
            events_emitted=[PERSONALITY_LOADED, PERSONALITY_SWITCHED],
            events_consumed=["app_ready", "app_shutting_down"],
            dependencies=[],
            tags=["personality", "identity", "presets", "voice"],
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def register(self, registry, event_bus) -> None:
        self._bus = event_bus
        registry.register("personality", self, replace=True)

        self._subscribe(event_bus, "app_ready", self._on_app_ready)
        self._subscribe(event_bus, "app_shutting_down", self._on_shutdown)
        _log.info("Personality bridge registered.")

    def unregister(self, registry, event_bus) -> None:
        for event_name, handler in self._event_handlers.items():
            try:
                event_bus.off(event_name, handler)
            except Exception:
                pass
        self._event_handlers.clear()
        _log.info("Personality bridge unregistered.")

    def health(self) -> Dict[str, Any]:
        base = super().health()
        base["active_preset"] = self._active_preset.name if self._active_preset else None
        return base

    # ------------------------------------------------------------------
    # Onyx-facing API
    # ------------------------------------------------------------------

    def load_preset(self, path: str) -> Dict:
        """Load a personality preset from a JSON file."""
        from core.personality import load_preset_from_file
        preset = load_preset_from_file(Path(path))
        if preset:
            self._active_preset = preset
            if self._bus:
                self._bus.emit(PERSONALITY_LOADED, {
                    "name": preset.name, "version": preset.version,
                })
            return {"ok": True, "name": preset.name, "version": preset.version}
        return {"ok": False, "error": f"Failed to load preset from {path}"}

    def switch_preset(self, preset_data: dict) -> Dict:
        """Switch to a new preset from dict data."""
        from core.personality import PersonalityPreset
        self._active_preset = PersonalityPreset(preset_data)
        if self._bus:
            self._bus.emit(PERSONALITY_SWITCHED, {"name": self._active_preset.name})
        return {"ok": True, "name": self._active_preset.name}

    def get_system_prompt(self, context: str = "chat") -> str:
        """Get system prompt for the active preset."""
        if self._active_preset:
            return self._active_preset.get_system_prompt(context)
        return ""

    def get_active_preset(self) -> Optional[Dict]:
        """Get the active preset as a dict."""
        if self._active_preset:
            return self._active_preset.to_dict()
        return None

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_app_ready(self, data: Dict) -> None:
        """Load default preset on startup."""
        default_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "personality", "default.json",
        )
        if os.path.exists(default_path):
            self.load_preset(default_path)
        else:
            _log.debug("No default personality preset found at %s", default_path)

    def _on_shutdown(self, data: Dict) -> None:
        _log.info("Personality: shutdown acknowledged.")

    def _subscribe(self, bus, event_name: str, handler):
        bus.on(event_name, handler)
        self._event_handlers[event_name] = handler


plugin = PersonalityBridge()
