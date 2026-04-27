"""Smoke tests for Phase 1-3 refactor: Service Registry, Events, Identity, Unified Memory."""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_service_registry():
    from core.service_registry import ServiceRegistry
    reg = ServiceRegistry()

    # Register + resolve
    reg.register("test", {"hello": "world"})
    assert reg.get("test") == {"hello": "world"}
    assert reg.has("test")
    print("  register + resolve: OK")

    # Lazy factory
    reg.register_factory("lazy", lambda: [1, 2, 3])
    assert reg.get("lazy") == [1, 2, 3]
    print("  lazy factory: OK")

    # Replace
    reg.register("test", {"new": True}, replace=True)
    assert reg.get("test") == {"new": True}
    print("  replace: OK")

    # try_get
    assert reg.try_get("nonexistent") is None
    print("  try_get miss: OK")

    # list
    names = reg.list_services()
    assert "test" in names and "lazy" in names
    print(f"  list_services: {names}")

    reg.reset()
    print("  PASS")


def test_event_bus():
    from core.events import EventBus, PERSONALITY_CHANGED

    bus = EventBus()
    received = []
    bus.on(PERSONALITY_CHANGED, lambda d: received.append(d))
    bus.emit(PERSONALITY_CHANGED, {"preset_name": "Creative"})
    assert len(received) == 1
    assert received[0]["preset_name"] == "Creative"
    print("  emit + receive: OK")

    # Once listener
    once_data = []
    bus.once("test_once", lambda d: once_data.append(d))
    bus.emit("test_once", {"x": 1})
    bus.emit("test_once", {"x": 2})
    assert len(once_data) == 1
    print("  once listener: OK")

    # Off
    handler = lambda d: None
    bus.on("test_off", handler)
    assert bus.has_listeners("test_off")
    bus.off("test_off", handler)
    assert not bus.has_listeners("test_off")
    print("  off: OK")

    # Stats
    stats = bus.get_stats()
    assert stats["total_emits"] >= 3
    print(f"  stats: {stats}")

    bus.reset()
    print("  PASS")


def test_personality_preset_v2():
    from core.personality import PersonalityPreset

    presets_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "personality_presets"
    )

    for fname in os.listdir(presets_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(presets_dir, fname)
        with open(path, "r") as f:
            data = json.load(f)
        p = PersonalityPreset(data)
        assert p.version == "2.0", f"{fname}: version is {p.version}"
        assert len(p.core_values) >= 3, f"{fname}: only {len(p.core_values)} core_values"
        assert len(p.long_term_goals) >= 3, f"{fname}: only {len(p.long_term_goals)} goals"
        assert p.voice_config.get("engine"), f"{fname}: missing voice engine"
        print(f"  {fname}: v{p.version}, {len(p.core_values)} values, {len(p.long_term_goals)} goals, voice={p.voice_config.get('engine')}")

    print("  PASS")


def test_mind_identity_from_preset():
    from core.mind import _get_identity

    identity = _get_identity()
    assert identity["name"], "name is empty"
    assert identity["role"], "role is empty"
    assert len(identity["long_term_goals"]) >= 3, "not enough goals"
    assert len(identity["personality"]) >= 2, "not enough personality traits"
    assert len(identity["core_values"]) >= 3, "not enough core values"
    print(f"  name: {identity['name']}")
    print(f"  role: {identity['role']}")
    print(f"  personality: {identity['personality'][:3]}")
    print(f"  goals: {len(identity['long_term_goals'])} items")
    print(f"  values: {len(identity['core_values'])} items")
    print("  PASS")


def test_utils():
    from core.utils import extract_json

    assert extract_json('text {"key": "val"} more') == {"key": "val"}
    assert extract_json('no json here') is None
    assert extract_json('{"nested": {"a": 1}}') == {"nested": {"a": 1}}
    assert extract_json('') is None
    print("  extract_json: OK")
    print("  PASS")


def test_unified_memory_init():
    from memory.unified import UnifiedMemory, MemoryResult

    mem = UnifiedMemory()
    # Just verify it constructs without error and has the expected interface
    assert hasattr(mem, "search")
    assert hasattr(mem, "remember_task")
    assert hasattr(mem, "add_knowledge")
    assert hasattr(mem, "get_task_context")
    assert hasattr(mem, "get_stats")
    print("  interface check: OK")

    # MemoryResult dataclass
    r = MemoryResult(content="test", source="memory", category="task", relevance=0.8)
    assert r.content == "test"
    assert r.relevance == 0.8
    print("  MemoryResult: OK")
    print("  PASS")


if __name__ == "__main__":
    tests = [
        ("Service Registry", test_service_registry),
        ("Event Bus", test_event_bus),
        ("Personality Preset v2", test_personality_preset_v2),
        ("Mind Identity from Preset", test_mind_identity_from_preset),
        ("Utils", test_utils),
        ("Unified Memory Init", test_unified_memory_init),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        print(f"\n=== {name} ===")
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("ALL TESTS PASSED")
    else:
        sys.exit(1)
