"""Component Registry — discovers, registers, and queries Onyx components.

The brain asks: "What can I use? What can do X?"
The registry answers.

Usage:
    from core.components.registry import component_registry

    # Register
    component_registry.register(BlenderComponent())

    # Query
    component_registry.get("blender")
    component_registry.list_all()
    component_registry.find_capable("render")
    component_registry.find_by_category("creative")

    # Auto-discover from core/components/builtins/
    component_registry.discover()
"""

import importlib
import logging
import os
import pkgutil
import threading
from typing import Dict, List, Optional

from core.components.base import OnyxComponent, ComponentStatus

_log = logging.getLogger("core.components.registry")


class ComponentRegistry:
    """Central registry of all Onyx components.

    Thread-safe. Components register themselves or are auto-discovered.
    The brain queries this to know what instruments are available.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._components: Dict[str, OnyxComponent] = {}
        self._discovered = False

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, component: OnyxComponent, *, replace: bool = False) -> None:
        """Register a component instance.

        Args:
            component: An OnyxComponent subclass instance.
            replace: If True, overwrite an existing registration.

        Raises:
            ValueError: If name already registered and replace is False.
        """
        with self._lock:
            name = component.name.lower()
            if name in self._components and not replace:
                raise ValueError(
                    f"Component '{name}' already registered. "
                    f"Use replace=True to overwrite."
                )
            self._components[name] = component
            _log.info("Registered component: %s (%s)",
                      name, component.display_name)

    def unregister(self, name: str) -> bool:
        """Remove a component from the registry."""
        with self._lock:
            return self._components.pop(name.lower(), None) is not None

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> int:
        """Auto-discover components from core/components/builtins/.

        Returns:
            Number of newly discovered components.
        """
        if self._discovered:
            return 0

        count = 0
        builtins_dir = os.path.join(os.path.dirname(__file__), "builtins")
        if not os.path.isdir(builtins_dir):
            os.makedirs(builtins_dir, exist_ok=True)
            # Create __init__.py if missing
            init_path = os.path.join(builtins_dir, "__init__.py")
            if not os.path.exists(init_path):
                with open(init_path, "w") as f:
                    f.write("")
            self._discovered = True
            return 0

        package = "core.components.builtins"
        for _importer, modname, _ispkg in pkgutil.iter_modules([builtins_dir]):
            try:
                mod = importlib.import_module(f"{package}.{modname}")
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (isinstance(attr, type)
                            and issubclass(attr, OnyxComponent)
                            and attr is not OnyxComponent
                            and not getattr(attr, '_skip_discovery', False)):
                        try:
                            instance = attr()
                            if instance.name.lower() not in self._components:
                                self.register(instance)
                                count += 1
                        except Exception as e:
                            _log.warning("Failed to instantiate %s: %s",
                                         attr_name, e)
            except Exception as e:
                _log.warning("Failed to import component module '%s': %s",
                             modname, e)

        self._discovered = True
        _log.info("Discovery complete: %d new components", count)
        return count

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[OnyxComponent]:
        """Get a component by name (case-insensitive)."""
        return self._components.get(name.lower())

    def list_all(self) -> List[OnyxComponent]:
        """Return all registered components."""
        return list(self._components.values())

    def list_names(self) -> List[str]:
        """Return names of all registered components."""
        return list(self._components.keys())

    def list_ready(self) -> List[OnyxComponent]:
        """Return only components that are ready to work."""
        return [c for c in self._components.values()
                if c.status == ComponentStatus.READY]

    def find_capable(self, action: str) -> List[OnyxComponent]:
        """Find all components that support a given action.

        The brain asks: "Who can render a video?"
        """
        result = []
        action_lower = action.lower()
        for comp in self._components.values():
            for a in comp.get_actions():
                if action_lower in a.name.lower() or action_lower in a.description.lower():
                    result.append(comp)
                    break
        return result

    def find_by_category(self, category: str) -> List[OnyxComponent]:
        """Find components in a specific category."""
        cat_lower = category.lower()
        return [c for c in self._components.values()
                if c.category.lower() == cat_lower]

    # ------------------------------------------------------------------
    # Execution (convenience — brain can also call component.execute directly)
    # ------------------------------------------------------------------

    def run(self, component_name: str, action: str,
            params: Optional[Dict] = None) -> "ComponentResult":
        """Execute an action on a named component.

        Convenience method so the brain can say:
            registry.run("blender", "build_scene", {"desc": "a cat"})
        """
        from core.components.base import ComponentResult

        comp = self.get(component_name)
        if comp is None:
            return ComponentResult(
                status="failed",
                error=f"Component '{component_name}' not found",
                summary=f"I don't have a '{component_name}' component.",
            )
        if comp.status == ComponentStatus.UNAVAILABLE:
            return ComponentResult(
                status="failed",
                error=f"Component '{component_name}' is unavailable",
                summary=f"{comp.display_name} isn't available right now.",
            )
        return comp._run(action, params)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict:
        """Get health status of all components."""
        report = {}
        for name, comp in self._components.items():
            report[name] = comp.health_check()
        return report

    # ------------------------------------------------------------------
    # Summary (for brain context)
    # ------------------------------------------------------------------

    def get_brain_context(self) -> str:
        """Generate a compact summary for Onyx's brain to reason about.

        Returns a string the brain can use to decide which component to pick.
        """
        if not self._components:
            return "No components registered."

        lines = ["Available components:"]
        for comp in self._components.values():
            actions = [a.name for a in comp.get_actions()]
            status_icon = {
                ComponentStatus.READY: "+",
                ComponentStatus.BUSY: "~",
                ComponentStatus.FAILED: "!",
                ComponentStatus.UNAVAILABLE: "-",
            }.get(comp.status, "?")
            lines.append(
                f"  [{status_icon}] {comp.display_name} ({comp.name}): "
                f"{comp.description}"
            )
            if actions:
                lines.append(f"      Actions: {', '.join(actions)}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._components)

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._components

    def __repr__(self) -> str:
        return f"<ComponentRegistry [{len(self._components)} components]>"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

component_registry = ComponentRegistry()
