"""Node registry — discovers and registers all node classes.

Similar to EVERA's NodeRegistry: auto-discovery via pkgutil, singleton pattern.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Dict, List, Optional, Type

from .base_node import BaseNode, NodeSchema

logger = logging.getLogger(__name__)


class NodeRegistry:
    """Global registry of all available node classes."""

    def __init__(self):
        self._nodes: Dict[str, Type[BaseNode]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, node_class: Type[BaseNode]) -> None:
        """Register a single node class."""
        schema = node_class.get_schema()
        node_id = schema.node_id
        if node_id in self._nodes:
            logger.warning("Node %s already registered, overwriting", node_id)
        self._nodes[node_id] = node_class
        logger.debug("Registered node: %s (%s)", node_id, schema.display_name)

    def register_many(self, *classes: Type[BaseNode]) -> None:
        """Register multiple node classes."""
        for cls in classes:
            self.register(cls)

    # ------------------------------------------------------------------
    # Discovery — auto-import node modules
    # ------------------------------------------------------------------

    def discover(self, package_name: str = "core.nodes.catalog") -> int:
        """
        Auto-discover and register all BaseNode subclasses in a package.

        Imports every module in the package and registers any class that
        inherits from BaseNode and has define_schema() implemented.

        Returns count of registered nodes.
        """
        count_before = len(self._nodes)
        try:
            package = importlib.import_module(package_name)
        except ImportError as e:
            logger.error("Cannot import node package %s: %s", package_name, e)
            return 0

        package_path = getattr(package, "__path__", None)
        if not package_path:
            logger.error("Package %s has no __path__", package_name)
            return 0

        for _importer, modname, _ispkg in pkgutil.iter_modules(package_path):
            full_name = f"{package_name}.{modname}"
            try:
                module = importlib.import_module(full_name)
            except Exception as e:
                logger.warning("Failed to import %s: %s", full_name, e)
                continue

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseNode)
                    and attr is not BaseNode
                    and hasattr(attr, "define_schema")
                ):
                    try:
                        self.register(attr)
                    except Exception as e:
                        logger.warning(
                            "Failed to register %s.%s: %s", full_name, attr_name, e
                        )

        registered = len(self._nodes) - count_before
        logger.info(
            "Discovered %d nodes from %s (total: %d)",
            registered, package_name, len(self._nodes),
        )
        return registered

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, node_id: str) -> Optional[Type[BaseNode]]:
        """Get a node class by its node_id."""
        return self._nodes.get(node_id)

    def get_or_raise(self, node_id: str) -> Type[BaseNode]:
        """Get a node class or raise KeyError."""
        cls = self._nodes.get(node_id)
        if cls is None:
            raise KeyError(
                f"Unknown node type: {node_id}. "
                f"Available: {sorted(self._nodes.keys())}"
            )
        return cls

    def list_nodes(self) -> List[Dict]:
        """List all registered nodes as schema dicts."""
        return [cls.schema_dict() for cls in self._nodes.values()]

    def list_by_category(self) -> Dict[str, List[Dict]]:
        """Group registered nodes by category."""
        cats: Dict[str, List[Dict]] = {}
        for cls in self._nodes.values():
            schema = cls.get_schema()
            cat = schema.category
            if cat not in cats:
                cats[cat] = []
            cats[cat].append(schema.to_dict())
        return dict(sorted(cats.items()))

    def list_by_extension(self) -> Dict[str, List[Dict]]:
        """Group registered nodes by extension (onyx, evera, etc.)."""
        exts: Dict[str, List[Dict]] = {}
        for cls in self._nodes.values():
            schema = cls.get_schema()
            ext = schema.extension or "onyx"
            if ext not in exts:
                exts[ext] = []
            exts[ext].append(schema.to_dict())
        return dict(sorted(exts.items()))

    @property
    def count(self) -> int:
        return len(self._nodes)

    @property
    def node_ids(self) -> List[str]:
        return sorted(self._nodes.keys())


# Singleton instance
_global_registry: Optional[NodeRegistry] = None


def get_registry() -> NodeRegistry:
    """Get or create the global node registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = NodeRegistry()
    return _global_registry
