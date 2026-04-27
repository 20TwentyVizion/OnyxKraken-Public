"""Plugin Loader — auto-discovers and manages plugin bridges.

Scans core/plugins/bridge_*.py for OnyxPlugin subclasses, resolves
dependency order, and manages the full lifecycle.

Usage:
    from core.plugins.loader import plugin_loader
    plugin_loader.discover()
    plugin_loader.load_all(registry, bus)
    plugin_loader.shutdown_all(registry, bus)
"""

import importlib
import logging
import os
import pkgutil
from typing import Any, Dict, List, Optional, Type

from core.plugins.protocol import OnyxPlugin, PluginMeta

_log = logging.getLogger("core.plugins.loader")


class PluginLoader:
    """Discovers, loads, and manages OnyxPlugin bridges."""

    def __init__(self):
        self._plugins: Dict[str, OnyxPlugin] = {}  # name → instance
        self._load_order: List[str] = []

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self, plugin_dir: Optional[str] = None) -> List[PluginMeta]:
        """Scan for bridge modules and instantiate their plugins.

        Looks for modules named bridge_*.py in core/plugins/.
        Each module must have a top-level `plugin` variable that is an
        OnyxPlugin instance, OR a `create_plugin()` factory function.

        Returns:
            List of discovered PluginMeta objects.
        """
        if plugin_dir is None:
            plugin_dir = os.path.dirname(os.path.abspath(__file__))

        discovered = []

        for filename in sorted(os.listdir(plugin_dir)):
            if not filename.startswith("bridge_") or not filename.endswith(".py"):
                continue

            module_name = filename[:-3]  # strip .py
            full_module = f"core.plugins.{module_name}"

            try:
                mod = importlib.import_module(full_module)
            except Exception as e:
                _log.error("Failed to import plugin bridge %s: %s", full_module, e)
                continue

            # Get plugin instance
            plugin = getattr(mod, "plugin", None)
            if plugin is None:
                factory = getattr(mod, "create_plugin", None)
                if factory:
                    try:
                        plugin = factory()
                    except Exception as e:
                        _log.error("Factory failed for %s: %s", module_name, e)
                        continue

            if plugin is None or not isinstance(plugin, OnyxPlugin):
                _log.debug("No OnyxPlugin found in %s", module_name)
                continue

            name = plugin.meta.name
            if name in self._plugins:
                _log.warning("Duplicate plugin name '%s' — skipping %s", name, module_name)
                continue

            self._plugins[name] = plugin
            discovered.append(plugin.meta)
            _log.info("Discovered plugin: %s v%s (%s)",
                      plugin.meta.display_name, plugin.meta.version, name)

        return discovered

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_all(self, registry, event_bus) -> List[str]:
        """Register and start all discovered plugins in dependency order.

        Returns list of successfully loaded plugin names.
        """
        if not self._plugins:
            self.discover()

        # Resolve load order (topological sort by dependencies)
        self._load_order = self._resolve_order()
        loaded = []

        for name in self._load_order:
            plugin = self._plugins[name]

            # Check dependencies
            missing = [d for d in plugin.meta.dependencies
                       if d not in self._plugins or not self._plugins[d].is_registered]
            if missing:
                _log.warning("Plugin '%s' missing dependencies: %s. Skipping.",
                             name, missing)
                continue

            try:
                plugin.register(registry, event_bus)
                plugin._registered = True
                _log.info("Registered plugin: %s", plugin.meta.display_name)
            except Exception as e:
                _log.error("Failed to register plugin '%s': %s", name, e)
                continue

            try:
                plugin.start()
                _log.info("Started plugin: %s", plugin.meta.display_name)
            except Exception as e:
                _log.error("Failed to start plugin '%s': %s", name, e)

            loaded.append(name)

        return loaded

    def load_one(self, name: str, registry, event_bus) -> bool:
        """Load a single plugin by name."""
        plugin = self._plugins.get(name)
        if not plugin:
            _log.warning("Plugin '%s' not discovered.", name)
            return False

        try:
            plugin.register(registry, event_bus)
            plugin._registered = True
            plugin.start()
            return True
        except Exception as e:
            _log.error("Failed to load plugin '%s': %s", name, e)
            return False

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown_all(self, registry, event_bus) -> None:
        """Stop and unregister all plugins in reverse order."""
        for name in reversed(self._load_order):
            plugin = self._plugins.get(name)
            if plugin and plugin.is_registered:
                try:
                    plugin.stop()
                except Exception as e:
                    _log.error("Failed to stop plugin '%s': %s", name, e)
                try:
                    plugin.unregister(registry, event_bus)
                    plugin._registered = False
                except Exception as e:
                    _log.error("Failed to unregister plugin '%s': %s", name, e)

        _log.info("All plugins shut down.")

    def shutdown_one(self, name: str, registry, event_bus) -> bool:
        """Shut down a single plugin by name."""
        plugin = self._plugins.get(name)
        if not plugin or not plugin.is_registered:
            return False

        try:
            plugin.stop()
            plugin.unregister(registry, event_bus)
            plugin._registered = False
            return True
        except Exception as e:
            _log.error("Failed to shutdown plugin '%s': %s", name, e)
            return False

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def health_all(self) -> Dict[str, Dict]:
        """Get health status for all plugins."""
        return {name: p.health() for name, p in self._plugins.items()}

    def get_plugin(self, name: str) -> Optional[OnyxPlugin]:
        """Get a plugin instance by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> List[PluginMeta]:
        """List all discovered plugins."""
        return [p.meta for p in self._plugins.values()]

    @property
    def plugin_count(self) -> int:
        return len(self._plugins)

    @property
    def loaded_count(self) -> int:
        return sum(1 for p in self._plugins.values() if p.is_registered)

    # ------------------------------------------------------------------
    # Dependency resolution
    # ------------------------------------------------------------------

    def _resolve_order(self) -> List[str]:
        """Topological sort of plugins by dependencies."""
        visited = set()
        order = []

        def _visit(name):
            if name in visited:
                return
            visited.add(name)
            plugin = self._plugins.get(name)
            if plugin:
                for dep in plugin.meta.dependencies:
                    if dep in self._plugins:
                        _visit(dep)
            order.append(name)

        for name in self._plugins:
            _visit(name)

        return order


# ---------------------------------------------------------------------------
# Global instance
# ---------------------------------------------------------------------------

plugin_loader = PluginLoader()
