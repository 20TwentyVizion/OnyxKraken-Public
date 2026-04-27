"""Service Registry — lightweight dependency injection for OnyxKraken.

Replaces scattered module-level singletons with a central registry that:
  - Stores service instances by name and/or protocol (ABC/Protocol)
  - Supports lazy initialization via factory callables
  - Allows swapping implementations (testing, A/B experiments)
  - Provides lifecycle management (shutdown hooks)

Usage:
    from core.service_registry import services

    # Register (typically at module init or app startup)
    services.register("mind", Mind())
    services.register_factory("knowledge", lambda: KnowledgeStore())

    # Resolve (anywhere that needs the service)
    mind = services.get("mind")             # by name
    mind = services.get("mind", Mind)       # by name + type check

    # Swap (for testing)
    services.register("mind", MockMind(), replace=True)

    # Shutdown
    services.shutdown()  # calls all registered teardown hooks

Thread-safe. Zero breaking changes — existing get_xxx() singletons
can delegate to this registry internally.
"""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

_log = logging.getLogger("core.registry")

T = TypeVar("T")


class ServiceRegistry:
    """Central service container with lazy factories and lifecycle hooks."""

    def __init__(self):
        self._lock = threading.Lock()
        self._instances: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._teardown_hooks: List[Callable] = []
        self._frozen = False

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str, instance: Any, *, replace: bool = False) -> None:
        """Register a service instance by name.

        Args:
            name: Unique service name (e.g. "mind", "knowledge", "personality_manager").
            instance: The service object.
            replace: If True, overwrite an existing registration.

        Raises:
            ValueError: If name already registered and replace is False.
        """
        with self._lock:
            if name in self._instances and not replace:
                raise ValueError(
                    f"Service '{name}' already registered. "
                    f"Use replace=True to overwrite."
                )
            self._instances[name] = instance
            _log.debug("Registered service: %s (%s)", name, type(instance).__name__)

    def register_factory(self, name: str, factory: Callable[[], Any],
                         *, replace: bool = False) -> None:
        """Register a lazy factory for a service.

        The factory is called exactly once, on first .get() for this name.
        The resulting instance is cached.

        Args:
            name: Unique service name.
            factory: Zero-arg callable that creates the service.
            replace: If True, overwrite existing registration.
        """
        with self._lock:
            if name in self._factories and not replace:
                if name not in self._instances:
                    raise ValueError(
                        f"Factory for '{name}' already registered. "
                        f"Use replace=True to overwrite."
                    )
            self._factories[name] = factory
            # Clear any cached instance so the new factory runs on next get()
            if replace and name in self._instances:
                del self._instances[name]
            _log.debug("Registered factory: %s", name)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def get(self, name: str, expected_type: Optional[Type[T]] = None) -> T:
        """Resolve a service by name.

        If a factory was registered and no instance exists yet, the factory
        is called (exactly once) and the result is cached.

        Args:
            name: Service name.
            expected_type: Optional type to assert against.

        Returns:
            The service instance.

        Raises:
            KeyError: If the service is not registered.
            TypeError: If expected_type is given and the instance doesn't match.
        """
        # Fast path — already instantiated
        instance = self._instances.get(name)
        if instance is not None:
            if expected_type and not isinstance(instance, expected_type):
                raise TypeError(
                    f"Service '{name}' is {type(instance).__name__}, "
                    f"expected {expected_type.__name__}"
                )
            return instance

        # Slow path — check factory
        with self._lock:
            # Double-check after acquiring lock
            instance = self._instances.get(name)
            if instance is not None:
                if expected_type and not isinstance(instance, expected_type):
                    raise TypeError(
                        f"Service '{name}' is {type(instance).__name__}, "
                        f"expected {expected_type.__name__}"
                    )
                return instance

            factory = self._factories.get(name)
            if factory is None:
                raise KeyError(
                    f"Service '{name}' not registered. "
                    f"Available: {', '.join(self.list_services())}"
                )

            _log.debug("Creating service '%s' via factory", name)
            instance = factory()
            self._instances[name] = instance

            if expected_type and not isinstance(instance, expected_type):
                raise TypeError(
                    f"Service '{name}' is {type(instance).__name__}, "
                    f"expected {expected_type.__name__}"
                )
            return instance

    def try_get(self, name: str, expected_type: Optional[Type[T]] = None) -> Optional[T]:
        """Resolve a service, returning None if not found (no exception)."""
        try:
            return self.get(name, expected_type)
        except (KeyError, TypeError):
            return None

    def has(self, name: str) -> bool:
        """Check if a service is registered (instance or factory)."""
        return name in self._instances or name in self._factories

    def list_services(self) -> List[str]:
        """List all registered service names."""
        with self._lock:
            names = set(self._instances.keys()) | set(self._factories.keys())
            return sorted(names)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_shutdown(self, hook: Callable) -> None:
        """Register a teardown hook called during shutdown()."""
        self._teardown_hooks.append(hook)

    def shutdown(self) -> None:
        """Run all teardown hooks and clear the registry."""
        _log.info("Service registry shutting down (%d hooks)", len(self._teardown_hooks))
        for hook in reversed(self._teardown_hooks):
            try:
                hook()
            except Exception as e:
                _log.error("Teardown hook failed: %s", e)
        self._teardown_hooks.clear()
        self._instances.clear()
        self._factories.clear()

    def reset(self) -> None:
        """Clear all registrations (for testing)."""
        with self._lock:
            self._instances.clear()
            self._factories.clear()
            self._teardown_hooks.clear()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return registry statistics."""
        with self._lock:
            return {
                "instantiated": list(self._instances.keys()),
                "pending_factories": [
                    k for k in self._factories
                    if k not in self._instances
                ],
                "teardown_hooks": len(self._teardown_hooks),
            }

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"<ServiceRegistry: {len(stats['instantiated'])} active, "
            f"{len(stats['pending_factories'])} pending>"
        )


# ---------------------------------------------------------------------------
# Global instance
# ---------------------------------------------------------------------------

services = ServiceRegistry()
