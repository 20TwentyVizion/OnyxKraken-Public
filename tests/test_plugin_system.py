"""Tests for the OnyxKraken Plugin System + Nexus Bridge.

Tests plugin protocol, loader discovery, lifecycle, and Nexus bridge wiring.
"""

import sys, os, tempfile, shutil, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Temp dir for all test data — avoids polluting real data/nexus/
_tmp_root = tempfile.mkdtemp(prefix="nexus_plugin_test_")

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name}")
        failed += 1


# ---------------------------------------------------------------------------
# Plugin Protocol
# ---------------------------------------------------------------------------

print("=== Plugin Protocol ===")

from core.plugins.protocol import OnyxPlugin, PluginMeta


class MockPlugin(OnyxPlugin):
    """Minimal test plugin."""

    @property
    def meta(self):
        return PluginMeta(
            name="mock",
            display_name="Mock Plugin",
            version="0.0.1",
            description="Test plugin for unit tests.",
            standalone=True,
            category="test",
            services=["mock_service"],
            events_emitted=["mock:event"],
            events_consumed=["app_ready"],
            tags=["test"],
        )

    def register(self, registry, event_bus):
        registry.register("mock_service", {"test": True}, replace=True)
        self._registered = True

    def unregister(self, registry, event_bus):
        self._registered = False


mp = MockPlugin()
check("plugin created", mp is not None)
check("plugin not registered", not mp.is_registered)
check("plugin not started", not mp.is_started)
check("meta name", mp.meta.name == "mock")
check("meta display", mp.meta.display_name == "Mock Plugin")
check("meta version", mp.meta.version == "0.0.1")
check("meta standalone", mp.meta.standalone)
check("meta category", mp.meta.category == "test")
check("meta services", mp.meta.services == ["mock_service"])
check("meta events_emitted", mp.meta.events_emitted == ["mock:event"])
check("meta events_consumed", mp.meta.events_consumed == ["app_ready"])
check("meta to_dict", mp.meta.to_dict()["name"] == "mock")
check("meta tags", mp.meta.tags == ["test"])

# Health before registration
h = mp.health()
check("health returns dict", isinstance(h, dict))
check("health ok false before reg", not h["ok"])
check("health message idle", h["message"] == "idle")

# repr
check("repr contains display name", "Mock Plugin" in repr(mp))
check("repr contains idle", "idle" in repr(mp))

# Start
mp.start()
check("start sets started", mp.is_started)
check("start sets start_time", mp._start_time > 0)


# ---------------------------------------------------------------------------
# ServiceRegistry (mini test for plugin integration)
# ---------------------------------------------------------------------------

print("\n=== ServiceRegistry for Plugins ===")

from core.service_registry import ServiceRegistry

registry = ServiceRegistry()

# Register via plugin
mp2 = MockPlugin()
mp2.register(registry, None)
check("plugin registered service", registry.has("mock_service"))
check("plugin service value", registry.get("mock_service")["test"] is True)

# Unregister
mp2.unregister(registry, None)
check("plugin unregistered", not mp2.is_registered)

registry.reset()


# ---------------------------------------------------------------------------
# EventBus (mini test for plugin integration)
# ---------------------------------------------------------------------------

print("\n=== EventBus for Plugins ===")

from core.events import EventBus

bus = EventBus()
received = []

def on_mock_event(data):
    received.append(data)

bus.on("mock:event", on_mock_event)
bus.emit("mock:event", {"msg": "hello"})
check("event received", len(received) == 1)
check("event data", received[0]["msg"] == "hello")

bus.off("mock:event", on_mock_event)
bus.emit("mock:event", {"msg": "should not arrive"})
check("event unsubscribed", len(received) == 1)


# ---------------------------------------------------------------------------
# Plugin Loader — Discovery
# ---------------------------------------------------------------------------

print("\n=== Plugin Loader ===")

from core.plugins.loader import PluginLoader

loader = PluginLoader()
check("loader created", loader is not None)
check("loader empty", loader.plugin_count == 0)

# Discover from actual core/plugins/ directory
discovered = loader.discover()
check("discovered plugins", len(discovered) >= 2)
plugin_names = [m.name for m in discovered]
check("nexus discovered", "nexus" in plugin_names)
check("oms discovered", "oms" in plugin_names)
print(f"  INFO: Discovered {len(discovered)} plugins: {plugin_names}")

# List plugins
listed = loader.list_plugins()
check("list_plugins", len(listed) == len(discovered))

# Get plugin by name
nexus_plugin = loader.get_plugin("nexus")
check("get_plugin nexus", nexus_plugin is not None)
check("nexus meta", nexus_plugin.meta.display_name == "Neural Organizer")

oms_plugin = loader.get_plugin("oms")
check("get_plugin oms", oms_plugin is not None)
check("oms meta", oms_plugin.meta.display_name == "Onyx Management Station")


# ---------------------------------------------------------------------------
# Plugin Loader — Full Lifecycle
# ---------------------------------------------------------------------------

print("\n=== Plugin Lifecycle ===")

registry2 = ServiceRegistry()
bus2 = EventBus()

# Create a fresh NexusBridge with temp config (avoids stale manifest)
from core.plugins.bridge_nexus import NexusBridge
from nexus.config import NexusConfig

test_config = NexusConfig(data_dir=os.path.join(_tmp_root, "nexus_data"))
fresh_nexus = NexusBridge(config=test_config)

# Replace the auto-discovered nexus plugin with our test one
loader._plugins["nexus"] = fresh_nexus

# Load all
loaded = loader.load_all(registry2, bus2)
check("loaded plugins", len(loaded) >= 2)
check("nexus loaded", "nexus" in loaded)
check("oms loaded", "oms" in loaded)
check("loaded count", loader.loaded_count >= 2)
print(f"  INFO: Loaded {len(loaded)} plugins: {loaded}")

# Check services registered
check("nexus service registered", registry2.has("nexus"))
check("nexus_engine service registered", registry2.has("nexus_engine"))
check("oms service registered", registry2.has("oms"))

# Health check
health = loader.health_all()
check("health_all returns dict", isinstance(health, dict))
check("nexus health ok", health["nexus"]["ok"])
check("oms health ok", health["oms"]["ok"])

# Nexus plugin state
nexus_p = loader.get_plugin("nexus")
check("nexus is_registered", nexus_p.is_registered)
check("nexus is_started", nexus_p.is_started)
check("nexus repr started", "started" in repr(nexus_p))


# ---------------------------------------------------------------------------
# Nexus Bridge — Service Access
# ---------------------------------------------------------------------------

print("\n=== Nexus Bridge — Service Access ===")

# Get engine via registry (lazy creation)
engine = registry2.get("nexus")
check("nexus engine via registry", engine is not None)

from nexus.engine import NexusEngine
check("engine is NexusEngine", isinstance(engine, NexusEngine))
check("engine has graph", engine.graph is not None)
check("engine has config", engine.config is not None)


# ---------------------------------------------------------------------------
# Nexus Bridge — Event Integration
# ---------------------------------------------------------------------------

print("\n=== Nexus Bridge — Events ===")

nexus_events = []

def on_nexus_event(data):
    nexus_events.append(data)

bus2.on("nexus:ingested", on_nexus_event)

# Ingest via bridge (use the fresh_nexus bridge directly)
bridge = fresh_nexus
result = bridge.ingest(
    "Plugin systems enable modular architecture with hot-swappable components. "
    "Each standalone module can function independently while also integrating "
    "seamlessly into the larger ecosystem through thin bridge adapters.",
    source="test",
)
check("bridge ingest ok", result["ok"])
check("bridge ingest created", result["thoughts_created"] > 0)
check("nexus:ingested event fired", len(nexus_events) >= 1)
if nexus_events:
    check("event has thoughts_created", "thoughts_created" in nexus_events[0])
    check("event has source", "source" in nexus_events[0])

# Query via bridge
qr = bridge.query("modular architecture")
check("bridge query works", len(qr["thoughts"]) > 0)
check("bridge query has query", qr["query"] == "modular architecture")

# Synthesize via bridge (may not produce results with few nodes)
sr = bridge.synthesize()
check("bridge synthesize ok", sr["ok"])

# Health after operations
h = bridge.health()
check("bridge health nodes > 0", h.get("nodes", 0) > 0)


# ---------------------------------------------------------------------------
# Nexus Bridge — Auto-ingest from Knowledge Events
# ---------------------------------------------------------------------------

print("\n=== Nexus Bridge — Knowledge Auto-Ingest ===")

initial_count = engine.graph.node_count

# Simulate knowledge_added event
bus2.emit("knowledge_added", {
    "entry_id": "k_test",
    "category": "patterns",
    "content": "Distributed consensus algorithms like Raft and Paxos enable fault-tolerant "
               "replication across multiple nodes in a cluster. These protocols guarantee "
               "that all non-faulty nodes agree on the same sequence of state transitions "
               "even when network partitions and message delays occur between participants.",
})

# Check if Nexus ingested it
new_count = engine.graph.node_count
check("auto-ingest from knowledge event", new_count > initial_count)
print(f"  INFO: Graph grew from {initial_count} to {new_count} nodes via event")


# ---------------------------------------------------------------------------
# Plugin Shutdown
# ---------------------------------------------------------------------------

print("\n=== Plugin Shutdown ===")

loader.shutdown_all(registry2, bus2)
check("nexus unregistered", not nexus_p.is_registered)
check("nexus stopped", not nexus_p.is_started)
check("oms unregistered", not loader.get_plugin("oms").is_registered)

registry2.reset()


# ---------------------------------------------------------------------------
# Dependency Resolution
# ---------------------------------------------------------------------------

print("\n=== Dependency Resolution ===")


class DepA(OnyxPlugin):
    @property
    def meta(self):
        return PluginMeta(name="dep_a", display_name="Dep A", dependencies=[])

    def register(self, r, b):
        self._registered = True

    def unregister(self, r, b):
        self._registered = False


class DepB(OnyxPlugin):
    @property
    def meta(self):
        return PluginMeta(name="dep_b", display_name="Dep B", dependencies=["dep_a"])

    def register(self, r, b):
        self._registered = True

    def unregister(self, r, b):
        self._registered = False


dep_loader = PluginLoader()
dep_loader._plugins = {"dep_b": DepB(), "dep_a": DepA()}
order = dep_loader._resolve_order()
check("dep_a before dep_b", order.index("dep_a") < order.index("dep_b"))

# Load — dep_a should load first
dep_reg = ServiceRegistry()
dep_bus = EventBus()
loaded_deps = dep_loader.load_all(dep_reg, dep_bus)
check("both deps loaded", len(loaded_deps) == 2)
check("dep_a loaded first", loaded_deps[0] == "dep_a")
check("dep_b loaded second", loaded_deps[1] == "dep_b")

# Shutdown — reverse order
dep_loader.shutdown_all(dep_reg, dep_bus)
check("dep_b shutdown first (reverse)", not dep_loader.get_plugin("dep_b").is_registered)
check("dep_a shutdown second (reverse)", not dep_loader.get_plugin("dep_a").is_registered)


# ---------------------------------------------------------------------------
# PluginMeta serialization
# ---------------------------------------------------------------------------

print("\n=== PluginMeta ===")

meta = PluginMeta(
    name="test_meta",
    display_name="Test Meta",
    version="2.0.0",
    description="Test description",
    standalone=False,
    category="addon",
    services=["s1", "s2"],
    events_emitted=["e1"],
    events_consumed=["e2"],
    dependencies=["dep_x"],
    tags=["tag1", "tag2"],
)

d = meta.to_dict()
check("meta dict name", d["name"] == "test_meta")
check("meta dict version", d["version"] == "2.0.0")
check("meta dict standalone", d["standalone"] is False)
check("meta dict services", d["services"] == ["s1", "s2"])
check("meta dict dependencies", d["dependencies"] == ["dep_x"])
check("meta dict tags", d["tags"] == ["tag1", "tag2"])


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

try:
    shutil.rmtree(_tmp_root)
except Exception:
    pass

# ===========================================================================
print(f"\n{'='*50}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"FAILURES: {failed}")
    sys.exit(1)
