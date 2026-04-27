"""OnyxKraken Plugin System — modular standalone↔Onyx wiring.

Every standalone package (nexus/, oms/, vision/, etc.) can be used
independently. When running inside OnyxKraken, a thin bridge module
registers the standalone as a plugin, wiring it into ServiceRegistry
and EventBus without the standalone knowing about either.

Architecture:
    standalone_package/     ← Zero Onyx imports. Works alone.
    core/plugins/bridge_x.py ← Thin adapter. Imports both sides.
    core/plugins/loader.py  ← Auto-discovers and loads bridges.

Plugin lifecycle:
    1. loader.discover()    — finds all bridge modules
    2. bridge.register()    — registers services + event subscriptions
    3. bridge.start()       — starts any background work (watchers, etc.)
    4. bridge.health()      — periodic health check
    5. bridge.stop()        — clean shutdown
    6. bridge.unregister()  — removes from registry

Usage:
    from core.plugins import loader
    loader.load_all()       # at app startup
    loader.shutdown_all()   # at app shutdown
"""

from core.plugins.protocol import OnyxPlugin, PluginMeta
from core.plugins.loader import PluginLoader

__all__ = ["OnyxPlugin", "PluginMeta", "PluginLoader"]
