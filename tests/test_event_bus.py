"""Tests for core.event_bus — OnyxBus pub/sub event system."""

import threading
import time
import pytest
from core.event_bus import OnyxBus


@pytest.fixture
def bus():
    """Fresh bus instance per test."""
    return OnyxBus(history_size=50)


# ---------------------------------------------------------------------------
# Subscribe / emit basics
# ---------------------------------------------------------------------------

class TestBasicPubSub:

    def test_emit_with_no_subscribers(self, bus):
        count = bus.emit("test.nothing")
        assert count == 0

    def test_subscribe_and_emit(self, bus):
        received = []
        bus.on("test.ping", lambda d: received.append(d))
        bus.emit("test.ping", {"msg": "hello"})
        assert received == [{"msg": "hello"}]

    def test_multiple_subscribers(self, bus):
        results = []
        bus.on("evt", lambda d: results.append("a"))
        bus.on("evt", lambda d: results.append("b"))
        count = bus.emit("evt")
        assert count == 2
        assert results == ["a", "b"]

    def test_emit_returns_count(self, bus):
        bus.on("evt", lambda d: None)
        bus.on("evt", lambda d: None)
        assert bus.emit("evt") == 2

    def test_unsubscribe(self, bus):
        cb = lambda d: None
        bus.on("evt", cb)
        assert bus.subscriber_count("evt") == 1
        bus.off("evt", cb)
        assert bus.subscriber_count("evt") == 0

    def test_unsubscribe_nonexistent(self, bus):
        # Should not raise
        bus.off("nope", lambda d: None)

    def test_no_duplicate_subscribe(self, bus):
        cb = lambda d: None
        bus.on("evt", cb)
        bus.on("evt", cb)
        assert bus.subscriber_count("evt") == 1


# ---------------------------------------------------------------------------
# Wildcards
# ---------------------------------------------------------------------------

class TestWildcard:

    def test_star_wildcard(self, bus):
        received = []
        bus.on("music.*", lambda d: received.append(d))
        bus.emit("music.playing", "song1")
        bus.emit("music.stopped", "done")
        bus.emit("face.changed", "nope")
        assert received == ["song1", "done"]

    def test_exact_and_wildcard_both_fire(self, bus):
        results = []
        bus.on("music.play", lambda d: results.append("exact"))
        bus.on("music.*", lambda d: results.append("wild"))
        bus.emit("music.play")
        assert "exact" in results
        assert "wild" in results


# ---------------------------------------------------------------------------
# Once
# ---------------------------------------------------------------------------

class TestOnce:

    def test_once_fires_once(self, bus):
        results = []
        bus.once("evt", lambda d: results.append(d))
        bus.emit("evt", 1)
        bus.emit("evt", 2)
        assert results == [1]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:

    def test_subscriber_exception_doesnt_break_others(self, bus):
        results = []

        def bad_handler(d):
            raise ValueError("oops")

        bus.on("evt", bad_handler)
        bus.on("evt", lambda d: results.append("ok"))
        count = bus.emit("evt")
        assert count == 1  # only the successful one counts
        assert results == ["ok"]


# ---------------------------------------------------------------------------
# Mute / unmute
# ---------------------------------------------------------------------------

class TestMute:

    def test_muted_bus_skips_events(self, bus):
        results = []
        bus.on("evt", lambda d: results.append(d))
        bus.mute()
        bus.emit("evt", "nope")
        assert results == []
        bus.unmute()
        bus.emit("evt", "yes")
        assert results == ["yes"]


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

class TestHistory:

    def test_history_records_events(self, bus):
        bus.emit("a", 1)
        bus.emit("b", 2)
        history = bus.recent_events()
        assert len(history) == 2
        assert history[0]["event"] == "a"
        assert history[1]["event"] == "b"

    def test_history_respects_limit(self, bus):
        for i in range(100):
            bus.emit("evt", i)
        history = bus.recent_events(5)
        assert len(history) == 5

    def test_history_capped_at_size(self):
        small_bus = OnyxBus(history_size=3)
        for i in range(10):
            small_bus.emit("evt", i)
        history = small_bus.recent_events(100)
        assert len(history) == 3


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

class TestUtils:

    def test_clear(self, bus):
        bus.on("evt", lambda d: None)
        bus.emit("evt")
        bus.clear()
        assert bus.subscriber_count() == 0
        assert bus.recent_events() == []

    def test_list_events(self, bus):
        bus.on("a.b", lambda d: None)
        bus.on("c.d", lambda d: None)
        events = bus.list_events()
        assert "a.b" in events
        assert "c.d" in events

    def test_subscriber_count_total(self, bus):
        bus.on("a", lambda d: None)
        bus.on("b", lambda d: None)
        bus.on("b", lambda d: None)
        assert bus.subscriber_count() == 3

    def test_repr(self, bus):
        r = repr(bus)
        assert "OnyxBus" in r


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_emit(self, bus):
        results = []
        bus.on("evt", lambda d: results.append(d))

        threads = []
        for i in range(10):
            t = threading.Thread(target=bus.emit, args=("evt", i))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        assert sorted(results) == list(range(10))
