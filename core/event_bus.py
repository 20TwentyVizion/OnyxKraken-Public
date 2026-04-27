"""OnyxBus — lightweight pub/sub event bus for cross-component communication.

This is PORT 1 of the Onyx Lego architecture. Every component connects
to the ecosystem through this bus. Components emit events, others subscribe.

Design rules:
  - Events are fire-and-forget (async by default, sync option available).
  - Subscribers MUST NOT raise exceptions — they are caught and logged.
  - Event names use dot-notation: "music.playing", "emotion.changed", etc.
  - Wildcard subscriptions: "music.*" matches "music.playing", "music.stopped".
  - Thread-safe via threading.Lock.

Usage:
    from core.event_bus import bus

    # Subscribe
    bus.on("emotion.changed", lambda data: print(data))
    bus.on("music.*", handle_any_music_event)

    # Emit
    bus.emit("emotion.changed", {"emotion": "happy", "intensity": 0.9})

    # Unsubscribe
    bus.off("emotion.changed", my_handler)
"""

import fnmatch
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

_log = logging.getLogger("core.event_bus")


@dataclass
class EventRecord:
    """Record of an emitted event (for debugging / replay)."""
    event: str
    data: Any
    timestamp: float
    source: str = ""


class OnyxBus:
    """Thread-safe publish/subscribe event bus.

    Supports exact matches and glob-style wildcards (e.g., "music.*").
    """

    def __init__(self, history_size: int = 100):
        self._lock = threading.Lock()
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._history: List[EventRecord] = []
        self._history_size = history_size
        self._muted: bool = False

    # ------------------------------------------------------------------
    # Subscribe / Unsubscribe
    # ------------------------------------------------------------------

    def on(self, event_pattern: str, callback: Callable) -> None:
        """Subscribe to an event pattern.

        Args:
            event_pattern: Exact event name or glob pattern (e.g., "music.*").
            callback: Function(data) called when a matching event fires.
        """
        with self._lock:
            if callback not in self._subscribers[event_pattern]:
                self._subscribers[event_pattern].append(callback)
                _log.debug("Subscribed to '%s': %s", event_pattern, callback.__name__)

    def off(self, event_pattern: str, callback: Callable) -> None:
        """Unsubscribe a callback from an event pattern."""
        with self._lock:
            subs = self._subscribers.get(event_pattern, [])
            if callback in subs:
                subs.remove(callback)
                _log.debug("Unsubscribed from '%s': %s", event_pattern, callback.__name__)

    def once(self, event_pattern: str, callback: Callable) -> None:
        """Subscribe to an event pattern — auto-unsubscribes after first fire."""
        def _wrapper(data):
            self.off(event_pattern, _wrapper)
            callback(data)
        _wrapper.__name__ = f"once_{callback.__name__}"
        self.on(event_pattern, _wrapper)

    # ------------------------------------------------------------------
    # Emit
    # ------------------------------------------------------------------

    def emit(self, event: str, data: Any = None, source: str = "") -> int:
        """Emit an event. Returns the number of subscribers notified.

        Args:
            event: Exact event name (e.g., "emotion.changed").
            data: Arbitrary payload (dict, str, None, etc.).
            source: Optional source identifier for debugging.

        Returns:
            Number of callbacks invoked.
        """
        if self._muted:
            return 0

        record = EventRecord(event=event, data=data,
                             timestamp=time.time(), source=source)

        with self._lock:
            self._history.append(record)
            if len(self._history) > self._history_size:
                self._history = self._history[-self._history_size:]

            # Collect matching subscribers
            matched: List[Callable] = []
            for pattern, callbacks in self._subscribers.items():
                if pattern == event or fnmatch.fnmatch(event, pattern):
                    matched.extend(callbacks)

        # Fire outside the lock to avoid deadlocks
        count = 0
        for cb in matched:
            try:
                cb(data)
                count += 1
            except Exception as e:
                _log.error("Event handler error on '%s' in %s: %s",
                           event, getattr(cb, '__name__', cb), e)

        if count > 0:
            _log.debug("Event '%s' → %d handler(s)", event, count)

        return count

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def mute(self) -> None:
        """Suppress all events (useful during batch operations)."""
        self._muted = True

    def unmute(self) -> None:
        """Resume event delivery."""
        self._muted = False

    def clear(self) -> None:
        """Remove all subscribers and history."""
        with self._lock:
            self._subscribers.clear()
            self._history.clear()

    def subscriber_count(self, event_pattern: str = None) -> int:
        """Count subscribers. If event_pattern given, count for that pattern only."""
        with self._lock:
            if event_pattern:
                return len(self._subscribers.get(event_pattern, []))
            return sum(len(v) for v in self._subscribers.values())

    def list_events(self) -> List[str]:
        """Return all event patterns that have subscribers."""
        with self._lock:
            return list(self._subscribers.keys())

    def recent_events(self, limit: int = 20) -> List[Dict]:
        """Return recent event history for debugging."""
        with self._lock:
            return [
                {"event": r.event, "data": r.data, "time": r.timestamp,
                 "source": r.source}
                for r in self._history[-limit:]
            ]

    def __repr__(self) -> str:
        return (f"<OnyxBus subscribers={self.subscriber_count()} "
                f"history={len(self._history)}>")


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

bus = OnyxBus()
