"""Event Bus — decoupled pub/sub communication for OnyxKraken circuits.

Allows subsystems to communicate without importing each other:
  - Personality change → Voice updates style, Chat reloads prompt
  - Task completed → Memory records, Knowledge extracts patterns
  - Skill registered → Command router adds fast-path, UI refreshes

Usage:
    from core.events import bus

    # Subscribe (any module)
    def on_personality_changed(data):
        print(f"Personality now: {data['preset_name']}")

    bus.on("personality_changed", on_personality_changed)

    # Emit (the module that owns the change)
    bus.emit("personality_changed", {"preset_name": "Creative"})

    # Unsubscribe
    bus.off("personality_changed", on_personality_changed)

    # One-shot listener
    bus.once("app_ready", lambda d: print("App is ready!"))

Thread-safe. Handlers run synchronously on the emitting thread by default.
Use bus.emit_async() for background dispatch.
"""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

_log = logging.getLogger("core.events")


# ---------------------------------------------------------------------------
# Event names (constants to avoid typos)
# ---------------------------------------------------------------------------

# Identity / Personality
PERSONALITY_CHANGED = "personality_changed"      # {preset_name, preset}
MOOD_CHANGED = "mood_changed"                    # {mood, previous_mood}
FOCUS_CHANGED = "focus_changed"                  # {focus, previous_focus}

# Agent / Tasks
TASK_STARTED = "task_started"                    # {goal, app_name}
TASK_COMPLETED = "task_completed"                # {goal, app_name, success, duration}
STEP_COMPLETED = "step_completed"                # {step_desc, step_type, status}

# Memory / Knowledge
MEMORY_UPDATED = "memory_updated"                # {category, key}
KNOWLEDGE_ADDED = "knowledge_added"              # {entry_id, category, content}

# Skills
SKILL_REGISTERED = "skill_registered"            # {skill_name, display_name}
SKILL_EXECUTED = "skill_executed"                 # {skill_name, action, success}

# Addons
ADDON_LOADED = "addon_loaded"                    # {addon_name, capabilities}
ADDON_UNLOADED = "addon_unloaded"                # {addon_name}

# Plugins
PLUGIN_LOADED = "plugin_loaded"                  # {plugin_name, version}
PLUGIN_UNLOADED = "plugin_unloaded"              # {plugin_name}

# Nexus (Neural Organizer)
NEXUS_INGESTED = "nexus:ingested"                # {thoughts_created, thoughts_merged, source}
NEXUS_QUERIED = "nexus:queried"                  # {query, match_count}
NEXUS_SYNTHESIZED = "nexus:synthesized"          # {hypotheses_created, clusters_found}
NEXUS_STATUS = "nexus:status"                    # {nodes, edges, density}

# OMS (Management Station)
OMS_HEALTH_CHECKED = "oms:health_checked"        # {findings_count, pass_rate}
OMS_REPAIR_RUN = "oms:repair_run"                # {fixed_count, failed_count}

# Memory (Unified Memory)
MEMORY_SEARCHED = "memory:searched"              # {query, result_count}
MEMORY_STORED = "memory:stored"                  # {category, key}
MEMORY_CONTEXT_BUILT = "memory:context_built"    # {goal, result_count}

# Screen Recorder
RECORDER_STARTED = "recorder:started"            # {path, fps, quality}
RECORDER_STOPPED = "recorder:stopped"            # {path, duration, size_bytes}

# Toolsmith
TOOLSMITH_REGISTERED = "toolsmith:registered"    # {name, status}
TOOLSMITH_LAUNCHED = "toolsmith:launched"         # {name, pid}
TOOLSMITH_VERIFIED = "toolsmith:verified"        # {name}
TOOLSMITH_DELETED = "toolsmith:deleted"          # {name}

# Voice
VOICE_SETTINGS_CHANGED = "voice_settings_changed"  # {rate, pitch, engine}
SPEECH_STARTED = "speech_started"                   # {text}
SPEECH_FINISHED = "speech_finished"                 # {text, duration}

# UI
UI_READY = "ui_ready"                            # {}
UI_MODE_CHANGED = "ui_mode_changed"              # {mode}  companion/work/demo

# System
APP_STARTING = "app_starting"                    # {}
APP_READY = "app_ready"                          # {}
APP_SHUTTING_DOWN = "app_shutting_down"           # {}


# ---------------------------------------------------------------------------
# Handler wrapper for one-shot listeners
# ---------------------------------------------------------------------------

class _OnceWrapper:
    """Wraps a handler so it auto-unsubscribes after one call."""

    def __init__(self, event: str, handler: Callable, bus: "EventBus"):
        self._event = event
        self._handler = handler
        self._bus = bus

    def __call__(self, data: Any) -> Any:
        result = self._handler(data)
        self._bus.off(self._event, self)
        return result


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

class EventBus:
    """Thread-safe publish/subscribe event bus.

    Handlers are called synchronously in subscription order.
    Use emit_async() for non-blocking dispatch.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._handlers: Dict[str, List[Callable]] = {}
        self._emit_count: int = 0
        self._error_count: int = 0

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------

    def on(self, event: str, handler: Callable) -> Callable:
        """Subscribe to an event.

        Args:
            event: Event name string.
            handler: Callable that receives one arg (event data dict).

        Returns:
            The handler (for chaining or later off() call).
        """
        with self._lock:
            if event not in self._handlers:
                self._handlers[event] = []
            if handler not in self._handlers[event]:
                self._handlers[event].append(handler)
        return handler

    def once(self, event: str, handler: Callable) -> Callable:
        """Subscribe to an event for exactly one invocation."""
        wrapper = _OnceWrapper(event, handler, self)
        return self.on(event, wrapper)

    def off(self, event: str, handler: Callable) -> bool:
        """Unsubscribe a handler from an event.

        Returns True if the handler was found and removed.
        """
        with self._lock:
            handlers = self._handlers.get(event, [])
            try:
                handlers.remove(handler)
                return True
            except ValueError:
                return False

    def off_all(self, event: Optional[str] = None) -> int:
        """Remove all handlers for an event, or all events if None.

        Returns the number of handlers removed.
        """
        with self._lock:
            if event:
                count = len(self._handlers.get(event, []))
                self._handlers.pop(event, None)
                return count
            else:
                count = sum(len(h) for h in self._handlers.values())
                self._handlers.clear()
                return count

    # ------------------------------------------------------------------
    # Emit
    # ------------------------------------------------------------------

    def emit(self, event: str, data: Optional[Dict[str, Any]] = None) -> int:
        """Emit an event synchronously.

        All handlers for this event are called in subscription order
        on the current thread. Exceptions in handlers are logged but
        don't prevent subsequent handlers from running.

        Args:
            event: Event name.
            data: Event payload (dict). Defaults to {}.

        Returns:
            Number of handlers that were called.
        """
        if data is None:
            data = {}

        with self._lock:
            handlers = list(self._handlers.get(event, []))

        if not handlers:
            return 0

        self._emit_count += 1
        called = 0
        for handler in handlers:
            try:
                handler(data)
                called += 1
            except Exception as e:
                self._error_count += 1
                _log.error(
                    "Event handler error: %s.%s — %s",
                    event, getattr(handler, "__name__", "?"), e,
                )
        return called

    def emit_async(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Emit an event on a background thread (non-blocking).

        Useful for events where the emitter shouldn't wait for handlers.
        """
        thread = threading.Thread(
            target=self.emit,
            args=(event, data),
            daemon=True,
            name=f"event:{event}",
        )
        thread.start()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def has_listeners(self, event: str) -> bool:
        """Check if any handlers are registered for an event."""
        with self._lock:
            return bool(self._handlers.get(event))

    def listener_count(self, event: Optional[str] = None) -> int:
        """Count listeners for an event, or all events if None."""
        with self._lock:
            if event:
                return len(self._handlers.get(event, []))
            return sum(len(h) for h in self._handlers.values())

    def list_events(self) -> List[str]:
        """List all events that have at least one handler."""
        with self._lock:
            return [e for e, h in self._handlers.items() if h]

    def get_stats(self) -> Dict[str, Any]:
        """Return bus statistics."""
        with self._lock:
            return {
                "events_with_handlers": len([h for h in self._handlers.values() if h]),
                "total_handlers": sum(len(h) for h in self._handlers.values()),
                "total_emits": self._emit_count,
                "total_errors": self._error_count,
            }

    def reset(self) -> None:
        """Clear all handlers and counters (for testing)."""
        with self._lock:
            self._handlers.clear()
            self._emit_count = 0
            self._error_count = 0

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"<EventBus: {stats['total_handlers']} handlers across "
            f"{stats['events_with_handlers']} events, "
            f"{stats['total_emits']} emits>"
        )


# ---------------------------------------------------------------------------
# Global instance
# ---------------------------------------------------------------------------

bus = EventBus()
