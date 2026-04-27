"""Tests for Tier 2 Plugin Bridges — Vision, Desktop, Personality, Knowledge.

Verifies extraction (no hard Onyx imports), discovery, lifecycle,
service registration, event wiring, and API methods.
"""

import sys, os, tempfile, shutil, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp_root = tempfile.mkdtemp(prefix="tier2_test_")

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
# Extraction Verification — no hard Onyx imports in standalone modules
# ---------------------------------------------------------------------------

print("=== Extraction Verification ===")


def check_no_hard_imports(filepath, forbidden):
    """Verify a file has no forbidden hard imports."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'"):
            continue
        for imp in forbidden:
            if imp in stripped and "try:" not in stripped:
                # Check it's not inside a try/except block
                # Look back for a try: within 3 lines
                in_try = False
                for j in range(max(0, i - 4), i):
                    if "try:" in lines[j]:
                        in_try = True
                        break
                if not in_try:
                    return False, f"Line {i}: {stripped}"
    return True, ""


# vision/analyzer.py — should NOT have 'import config' or 'from agent'
ok, msg = check_no_hard_imports(
    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                 "vision", "analyzer.py"),
    ["import config", "from agent.model_router"],
)
check("vision/analyzer.py standalone", ok)
if not ok:
    print(f"    {msg}")

# desktop/controller.py — should NOT have 'import config'
ok, msg = check_no_hard_imports(
    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                 "desktop", "controller.py"),
    ["import config"],
)
check("desktop/controller.py standalone", ok)
if not ok:
    print(f"    {msg}")

# core/personality.py — should NOT have 'from log import'
ok, msg = check_no_hard_imports(
    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                 "core", "personality.py"),
    ["from log import"],
)
check("core/personality.py standalone", ok)
if not ok:
    print(f"    {msg}")

# memory/base_store.py — should NOT have 'from log import'
ok, msg = check_no_hard_imports(
    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                 "memory", "base_store.py"),
    ["from log import"],
)
check("memory/base_store.py standalone", ok)
if not ok:
    print(f"    {msg}")


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

from core.service_registry import ServiceRegistry
from core.events import EventBus
from core.plugins.loader import PluginLoader


# ---------------------------------------------------------------------------
# Discovery — all Tier 2 bridges found
# ---------------------------------------------------------------------------

print("\n=== Discovery ===")

loader = PluginLoader()
discovered = loader.discover()
names = [m.name for m in discovered]

check("vision discovered", "vision" in names)
check("desktop discovered", "desktop" in names)
check("personality discovered", "personality" in names)
check("knowledge discovered", "knowledge" in names)
check("total >= 10", len(discovered) >= 10)
print(f"  INFO: {len(discovered)} plugins: {sorted(names)}")


# ---------------------------------------------------------------------------
# Vision Bridge
# ---------------------------------------------------------------------------

print("\n=== Vision Bridge ===")

from core.plugins.bridge_vision import VisionBridge

vis = VisionBridge()
check("vis meta name", vis.meta.name == "vision")
check("vis meta display", vis.meta.display_name == "Vision Analyzer")
check("vis meta standalone", vis.meta.standalone)
check("vis meta category", vis.meta.category == "core")

reg1 = ServiceRegistry()
bus1 = EventBus()

vis.register(reg1, bus1)
vis._registered = True
vis.start()

check("vis registered", vis.is_registered)
check("vis started", vis.is_started)
check("vis service in registry", reg1.has("vision"))

h = vis.health()
check("vis health ok", h["ok"])
check("vis health has configured", "configured" in h)
check("vis health has opencv", "opencv_available" in h)

# Verify analyzer.configure was called
from vision.analyzer import _config, _chat_fn
check("vis config injected", _config["save_screenshots"] is not None)
# chat_fn may or may not be set depending on whether model_router is available
# That's fine — the bridge tries but doesn't fail

vis.stop()
vis.unregister(reg1, bus1)
vis._registered = False
check("vis unregistered", not vis.is_registered)


# ---------------------------------------------------------------------------
# Desktop Bridge
# ---------------------------------------------------------------------------

print("\n=== Desktop Bridge ===")

from core.plugins.bridge_desktop import DesktopBridge

desk = DesktopBridge()
check("desk meta name", desk.meta.name == "desktop")
check("desk meta display", desk.meta.display_name == "Desktop Controller")
check("desk meta standalone", desk.meta.standalone)

reg2 = ServiceRegistry()
bus2 = EventBus()

desk.register(reg2, bus2)
desk._registered = True
desk.start()

check("desk registered", desk.is_registered)
check("desk service in registry", reg2.has("desktop"))

h = desk.health()
check("desk health ok", h["ok"])
check("desk health has windows count", "visible_windows" in h)

# Verify config was injected into controller
from desktop.controller import _config as dc_config
check("desk config injected", dc_config["app_load_timeout"] == 10)

# Test list_windows API
windows = desk.list_windows()
check("desk list_windows", isinstance(windows, list))

# Test find_window API (may or may not find anything)
result = desk.find_window("Nonexistent Window 12345")
check("desk find_window returns dict", isinstance(result, dict))
check("desk find_window not found", not result["found"])

desk.stop()
desk.unregister(reg2, bus2)
desk._registered = False
check("desk unregistered", not desk.is_registered)


# ---------------------------------------------------------------------------
# Personality Bridge
# ---------------------------------------------------------------------------

print("\n=== Personality Bridge ===")

from core.plugins.bridge_personality import PersonalityBridge

pers = PersonalityBridge()
check("pers meta name", pers.meta.name == "personality")
check("pers meta display", pers.meta.display_name == "Personality Engine")
check("pers meta standalone", pers.meta.standalone)

reg3 = ServiceRegistry()
bus3 = EventBus()

pers.register(reg3, bus3)
pers._registered = True
pers.start()

check("pers registered", pers.is_registered)
check("pers service in registry", reg3.has("personality"))

h = pers.health()
check("pers health ok", h["ok"])
check("pers health has preset", "active_preset" in h)
check("pers no preset active", h["active_preset"] is None)

# Test switch_preset API
pers_events = []
bus3.on("personality:switched", lambda d: pers_events.append(d))

result = pers.switch_preset({
    "name": "TestBot",
    "version": "1.0",
    "identity": {"name": "TestBot", "nickname": "TB", "role": "Test Agent"},
    "traits": {"primary": ["helpful"], "humor_level": 7},
    "values": ["testing"],
})
check("pers switch ok", result["ok"])
check("pers switch name", result["name"] == "TestBot")
check("pers switched event", len(pers_events) == 1)

# Test get_system_prompt
prompt = pers.get_system_prompt("chat")
check("pers system prompt", "TestBot" in prompt)
check("pers prompt has traits", "helpful" in prompt)

# Test get_active_preset
active = pers.get_active_preset()
check("pers active preset", active is not None)
check("pers active name", active["name"] == "TestBot")

# Test load_preset from file
preset_path = os.path.join(_tmp_root, "test_preset.json")
with open(preset_path, "w") as f:
    json.dump({
        "name": "FilePreset",
        "version": "2.0",
        "identity": {"name": "FilePreset"},
        "traits": {"primary": ["precise"]},
    }, f)

load_events = []
bus3.on("personality:loaded", lambda d: load_events.append(d))
result = pers.load_preset(preset_path)
check("pers load from file ok", result["ok"])
check("pers load name", result["name"] == "FilePreset")
check("pers loaded event", len(load_events) == 1)

pers.stop()
pers.unregister(reg3, bus3)
pers._registered = False
check("pers unregistered", not pers.is_registered)


# ---------------------------------------------------------------------------
# Knowledge Bridge
# ---------------------------------------------------------------------------

print("\n=== Knowledge Bridge ===")

from core.plugins.bridge_knowledge import KnowledgeBridge

know = KnowledgeBridge()
check("know meta name", know.meta.name == "knowledge")
check("know meta display", know.meta.display_name == "Knowledge Store")
check("know meta standalone", know.meta.standalone)

reg4 = ServiceRegistry()
bus4 = EventBus()

know.register(reg4, bus4)
know._registered = True
know.start()

check("know registered", know.is_registered)
check("know service in registry", reg4.has("knowledge"))

h = know.health()
check("know health ok", h["ok"])

# Test add API
know_events = []
bus4.on("knowledge:added", lambda d: know_events.append(d))

result = know.add("Plugin bridges enable modular standalone integration",
                   category="task_patterns", tags=["plugins"], source="test")
check("know add ok", result["ok"])
check("know add has entry_id", "entry_id" in result)
check("know:added event", len(know_events) == 1)

# Test search API
search_events = []
bus4.on("knowledge:searched", lambda d: search_events.append(d))

result = know.search("plugin bridge")
check("know search has results", len(result["results"]) > 0)
check("know:searched event", len(search_events) == 1)

# Test get_stats
stats = know.get_stats()
check("know stats has total", "total_entries" in stats)
check("know stats count > 0", stats["total_entries"] > 0)

# Test remove
entry_id = know_events[0]["entry_id"]
remove_events = []
bus4.on("knowledge:removed", lambda d: remove_events.append(d))
result = know.remove(entry_id)
check("know remove ok", result["ok"])
check("know:removed event", len(remove_events) == 1)

know.stop()
know.unregister(reg4, bus4)
know._registered = False
check("know unregistered", not know.is_registered)


# ---------------------------------------------------------------------------
# Full Loader — All 10 Plugins
# ---------------------------------------------------------------------------

print("\n=== Full Loader — All Plugins ===")

full_reg = ServiceRegistry()
full_bus = EventBus()

full_loader = PluginLoader()
full_loader.discover()
loaded = full_loader.load_all(full_reg, full_bus)

tier1 = ["memory", "nexus", "oms", "screen_recorder", "toolsmith", "voice"]
tier2 = ["vision", "desktop", "personality", "knowledge"]

for name in tier1 + tier2:
    check(f"full: {name} loaded", name in loaded)

check("full: all services", all(full_reg.has(n) for n in tier1 + tier2))
check("full: total loaded >= 10", len(loaded) >= 10)
print(f"  INFO: {len(loaded)} plugins loaded: {sorted(loaded)}")

# Health all
health = full_loader.health_all()
for name in tier1 + tier2:
    check(f"full: {name} healthy", health[name]["ok"])

# Shutdown all
full_loader.shutdown_all(full_reg, full_bus)
for name in tier1 + tier2:
    p = full_loader.get_plugin(name)
    check(f"full: {name} shutdown", not p.is_registered)


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
