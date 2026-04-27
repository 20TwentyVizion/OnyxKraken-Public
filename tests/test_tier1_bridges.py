"""Tests for Tier 1 Plugin Bridges — Memory, Voice, Screen Recorder, Toolsmith.

Verifies discovery, lifecycle, service registration, event wiring,
and API methods for each bridge.
"""

import sys, os, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
# Setup — shared infrastructure
# ---------------------------------------------------------------------------

from core.service_registry import ServiceRegistry
from core.events import EventBus
from core.plugins.loader import PluginLoader

registry = ServiceRegistry()
bus = EventBus()


# ---------------------------------------------------------------------------
# Discovery — verify all Tier 1 bridges are found
# ---------------------------------------------------------------------------

print("=== Discovery ===")

loader = PluginLoader()
discovered = loader.discover()
names = [m.name for m in discovered]

check("memory discovered", "memory" in names)
check("voice discovered", "voice" in names)
check("screen_recorder discovered", "screen_recorder" in names)
check("toolsmith discovered", "toolsmith" in names)
check("nexus discovered", "nexus" in names)
check("oms discovered", "oms" in names)
check("total >= 6", len(discovered) >= 6)
print(f"  INFO: {len(discovered)} plugins: {names}")


# ---------------------------------------------------------------------------
# Memory Bridge
# ---------------------------------------------------------------------------

print("\n=== Memory Bridge ===")

from core.plugins.bridge_memory import MemoryBridge

mem_bridge = MemoryBridge()

# Meta
check("mem meta name", mem_bridge.meta.name == "memory")
check("mem meta display", mem_bridge.meta.display_name == "Unified Memory")
check("mem meta standalone", mem_bridge.meta.standalone)
check("mem meta services", "unified_memory" in mem_bridge.meta.services)

# Health before registration
h = mem_bridge.health()
check("mem health before reg", not h["ok"])

# Register
mem_bridge.register(registry, bus)
mem_bridge._registered = True
mem_bridge.start()

check("mem registered", mem_bridge.is_registered)
check("mem started", mem_bridge.is_started)
check("mem service in registry", registry.has("memory"))
check("mem unified service", registry.has("unified_memory"))

# Health after registration
h = mem_bridge.health()
check("mem health ok", h["ok"])

# Search API — emits events
mem_events = []
bus.on("memory:searched", lambda d: mem_events.append(d))

result = mem_bridge.search("test query")
check("mem search returns dict", isinstance(result, dict))
check("mem search has query", result["query"] == "test query")
check("mem search has results", "results" in result)
check("mem:searched event fired", len(mem_events) >= 1)

# Shutdown
mem_bridge.stop()
mem_bridge.unregister(registry, bus)
mem_bridge._registered = False
check("mem unregistered", not mem_bridge.is_registered)


# ---------------------------------------------------------------------------
# Voice Bridge
# ---------------------------------------------------------------------------

print("\n=== Voice Bridge ===")

from core.plugins.bridge_voice import VoiceBridge

voice_bridge = VoiceBridge()

# Meta
check("voice meta name", voice_bridge.meta.name == "voice")
check("voice meta display", voice_bridge.meta.display_name == "Voice I/O")
check("voice meta standalone", voice_bridge.meta.standalone)
check("voice meta services", "voice" in voice_bridge.meta.services)
check("voice meta events", "voice:speech_started" in voice_bridge.meta.events_emitted)

# Register
registry2 = ServiceRegistry()
bus2 = EventBus()

voice_bridge.register(registry2, bus2)
voice_bridge._registered = True
voice_bridge.start()

check("voice registered", voice_bridge.is_registered)
check("voice started", voice_bridge.is_started)
check("voice service in registry", registry2.has("voice"))

# Health
h = voice_bridge.health()
check("voice health ok", h["ok"])
check("voice health has whisper check", "whisper_cpp_available" in h)
check("voice health has pyttsx3 check", "pyttsx3_available" in h)

# Shutdown
voice_bridge.stop()
voice_bridge.unregister(registry2, bus2)
voice_bridge._registered = False
check("voice unregistered", not voice_bridge.is_registered)


# ---------------------------------------------------------------------------
# Screen Recorder Bridge
# ---------------------------------------------------------------------------

print("\n=== Screen Recorder Bridge ===")

from core.plugins.bridge_screen_recorder import ScreenRecorderBridge

rec_bridge = ScreenRecorderBridge()

# Meta
check("rec meta name", rec_bridge.meta.name == "screen_recorder")
check("rec meta display", rec_bridge.meta.display_name == "Screen Recorder")
check("rec meta standalone", rec_bridge.meta.standalone)
check("rec meta category", rec_bridge.meta.category == "media")
check("rec meta services", "screen_recorder" in rec_bridge.meta.services)

# Register
registry3 = ServiceRegistry()
bus3 = EventBus()

rec_bridge.register(registry3, bus3)
rec_bridge._registered = True
rec_bridge.start()

check("rec registered", rec_bridge.is_registered)
check("rec started", rec_bridge.is_started)
check("rec service in registry", registry3.has("screen_recorder"))

# Health
h = rec_bridge.health()
check("rec health ok", h["ok"])
check("rec health has recording flag", "is_recording" in h)
check("rec health has ffmpeg check", "ffmpeg_available" in h)
check("rec not recording", not h["is_recording"])

# Get recorder via registry (lazy creation)
recorder = registry3.get("screen_recorder")
check("rec factory works", recorder is not None)
from core.screen_recorder import ScreenRecorder
check("rec is ScreenRecorder", isinstance(recorder, ScreenRecorder))

# Shutdown
rec_bridge.stop()
rec_bridge.unregister(registry3, bus3)
rec_bridge._registered = False
check("rec unregistered", not rec_bridge.is_registered)


# ---------------------------------------------------------------------------
# Toolsmith Bridge
# ---------------------------------------------------------------------------

print("\n=== Toolsmith Bridge ===")

from core.plugins.bridge_toolsmith import ToolsmithBridge

ts_bridge = ToolsmithBridge()

# Meta
check("ts meta name", ts_bridge.meta.name == "toolsmith")
check("ts meta display", ts_bridge.meta.display_name == "Toolsmith")
check("ts meta standalone", ts_bridge.meta.standalone)
check("ts meta services", "toolsmith" in ts_bridge.meta.services)
check("ts meta events", "toolsmith:registered" in ts_bridge.meta.events_emitted)

# Register
registry4 = ServiceRegistry()
bus4 = EventBus()

ts_bridge.register(registry4, bus4)
ts_bridge._registered = True
ts_bridge.start()

check("ts registered", ts_bridge.is_registered)
check("ts started", ts_bridge.is_started)
check("ts service in registry", registry4.has("toolsmith"))

# Health
h = ts_bridge.health()
check("ts health ok", h["ok"])
check("ts health has tool_count", "tool_count" in h)

# List tools
tools = ts_bridge.list_tools()
check("ts list_tools returns list", isinstance(tools, list))

# Shutdown
ts_bridge.stop()
ts_bridge.unregister(registry4, bus4)
ts_bridge._registered = False
check("ts unregistered", not ts_bridge.is_registered)


# ---------------------------------------------------------------------------
# Full Loader Lifecycle — all Tier 1 plugins
# ---------------------------------------------------------------------------

print("\n=== Full Loader Lifecycle ===")

full_registry = ServiceRegistry()
full_bus = EventBus()

full_loader = PluginLoader()
full_loader.discover()
loaded = full_loader.load_all(full_registry, full_bus)

check("all loaded", len(loaded) >= 6)
check("memory in loaded", "memory" in loaded)
check("voice in loaded", "voice" in loaded)
check("screen_recorder in loaded", "screen_recorder" in loaded)
check("toolsmith in loaded", "toolsmith" in loaded)
check("nexus in loaded", "nexus" in loaded)
check("oms in loaded", "oms" in loaded)

# All services registered
check("all: memory service", full_registry.has("memory"))
check("all: voice service", full_registry.has("voice"))
check("all: screen_recorder service", full_registry.has("screen_recorder"))
check("all: toolsmith service", full_registry.has("toolsmith"))
check("all: nexus service", full_registry.has("nexus"))
check("all: oms service", full_registry.has("oms"))

# Health all
health = full_loader.health_all()
check("health has all plugins", len(health) >= 6)
for name in ["memory", "voice", "screen_recorder", "toolsmith"]:
    check(f"health {name} ok", health[name]["ok"])

# Shutdown all
full_loader.shutdown_all(full_registry, full_bus)
for name in ["memory", "voice", "screen_recorder", "toolsmith"]:
    p = full_loader.get_plugin(name)
    check(f"shutdown {name}", not p.is_registered)


# ---------------------------------------------------------------------------
# Event Wiring Verification
# ---------------------------------------------------------------------------

print("\n=== Event Wiring ===")

ev_registry = ServiceRegistry()
ev_bus = EventBus()

ev_mem = MemoryBridge()
ev_mem.register(ev_registry, ev_bus)
ev_mem._registered = True
ev_mem.start()

# Verify task_completed event handler
task_events_received = []
original_record = None
try:
    unified = ev_mem._get_unified()
    original_record = getattr(unified.memory, 'record_task', None)
    # Monkey-patch to track calls
    calls = []
    unified.memory.record_task = lambda goal, app, success: calls.append((goal, app, success))
    ev_bus.emit("task_completed", {"goal": "Test goal", "app_name": "testapp", "success": True})
    check("task_completed triggers record_task", len(calls) == 1)
    check("record_task gets goal", calls[0][0] == "Test goal")
except Exception as e:
    check(f"event wiring (error: {e})", False)
finally:
    if original_record and ev_mem._unified:
        ev_mem._unified.memory.record_task = original_record

ev_mem.stop()
ev_mem.unregister(ev_registry, ev_bus)
ev_mem._registered = False


# ---------------------------------------------------------------------------
# PluginMeta Serialization for all bridges
# ---------------------------------------------------------------------------

print("\n=== Meta Serialization ===")

for Bridge in [MemoryBridge, VoiceBridge, ScreenRecorderBridge, ToolsmithBridge]:
    b = Bridge()
    d = b.meta.to_dict()
    name = d["name"]
    check(f"{name} meta has name", "name" in d)
    check(f"{name} meta has version", "version" in d)
    check(f"{name} meta has services", len(d["services"]) > 0)
    check(f"{name} meta has events_emitted", len(d["events_emitted"]) > 0)


# ===========================================================================
print(f"\n{'='*50}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"FAILURES: {failed}")
    sys.exit(1)
