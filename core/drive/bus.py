"""DriveBus — central event bus for animation drive commands.

Anything that wants to drive a character (REST endpoint, MCP tool, chat
dispatcher, episode player) publishes a DriveEvent on the bus. Anything
that wants to *receive* (face GUI backend, WebSocket relay, frontend
canvas via SSE) subscribes.

This decouples senders from receivers — the chat pipeline doesn't need to
know whether the renderer is the desktop face GUI, a WebSocket-connected
browser, or a recording sink. They all subscribe to the same bus.

Thread-safe: publish() can be called from any thread; each subscriber's
queue receives a copy.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional


@dataclass
class DriveEvent:
    """A single drive instruction.

    kind: "emotion" | "pose" | "body_anim" | "speak" | "episode_beat" | "stop"
    """
    kind: str
    character: str = "onyx"
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    source: str = ""           # "rest" | "mcp" | "ws" | "chat" | "episode"

    def to_dict(self) -> dict:
        return asdict(self)


class DriveBus:
    """Synchronous fan-out bus with optional async subscribers."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sync_subs: list[Callable[[DriveEvent], None]] = []
        self._async_queues: list[asyncio.Queue] = []
        self._history: list[DriveEvent] = []
        self._history_max = 64

    # ----------------------------------------------------------- publish
    def publish(self, event: DriveEvent) -> None:
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_max:
                self._history = self._history[-self._history_max:]
            sync = list(self._sync_subs)
            queues = list(self._async_queues)

        for fn in sync:
            try:
                fn(event)
            except Exception:
                pass
        for q in queues:
            try:
                q.put_nowait(event)
            except Exception:
                pass

    # --------------------------------------------------------- subscribe
    def subscribe(self, fn: Callable[[DriveEvent], None]) -> Callable[[], None]:
        with self._lock:
            self._sync_subs.append(fn)

        def _unsub() -> None:
            with self._lock:
                if fn in self._sync_subs:
                    self._sync_subs.remove(fn)

        return _unsub

    def subscribe_async(self) -> tuple[asyncio.Queue, Callable[[], None]]:
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._async_queues.append(q)

        def _unsub() -> None:
            with self._lock:
                if q in self._async_queues:
                    self._async_queues.remove(q)

        return q, _unsub

    def recent(self, limit: int = 20) -> list[DriveEvent]:
        with self._lock:
            return list(self._history[-limit:])


_singleton: Optional[DriveBus] = None


def get_bus() -> DriveBus:
    global _singleton
    if _singleton is None:
        _singleton = DriveBus()
    return _singleton
