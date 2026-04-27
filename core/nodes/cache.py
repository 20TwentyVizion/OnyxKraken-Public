"""Execution cache — stores intermediate node outputs for re-run efficiency.

If a node's inputs haven't changed, skip re-execution and return cached output.
Invalidates downstream when upstream changes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Set

from .types import hash_value

logger = logging.getLogger(__name__)


class ExecutionCache:
    """Cache node outputs keyed by (class_type, input_content_hash)."""

    def __init__(self):
        self._cache: Dict[str, Any] = {}  # cache_key -> output tuple
        self._key_map: Dict[str, str] = {}  # node_id -> cache_key (last run)

    def _make_key(self, class_type: str, resolved_inputs: Dict[str, Any]) -> str:
        """Build a deterministic cache key from node type + input values."""
        parts = [class_type]
        for name in sorted(resolved_inputs.keys()):
            val = resolved_inputs[name]
            parts.append(f"{name}={hash_value(val)}")
        return "|".join(parts)

    def get(
        self, node_id: str, class_type: str, resolved_inputs: Dict[str, Any]
    ) -> Optional[Any]:
        """Look up cached output. Returns None on miss."""
        key = self._make_key(class_type, resolved_inputs)
        cached = self._cache.get(key)
        if cached is not None:
            logger.debug("Cache HIT for node %s (%s)", node_id, class_type)
        return cached

    def store(
        self, node_id: str, class_type: str,
        resolved_inputs: Dict[str, Any], output: Any,
    ):
        """Store a node's output in cache."""
        key = self._make_key(class_type, resolved_inputs)
        self._cache[key] = output
        self._key_map[node_id] = key
        logger.debug("Cached output for node %s (%s)", node_id, class_type)

    def invalidate(self, node_id: str):
        """Remove a specific node's cached output."""
        key = self._key_map.pop(node_id, None)
        if key:
            self._cache.pop(key, None)
            logger.debug("Invalidated cache for node %s", node_id)

    def invalidate_downstream(
        self, node_id: str, graph: Dict[str, Dict]
    ) -> Set[str]:
        """Invalidate all nodes downstream of node_id."""
        invalidated: Set[str] = set()
        dependents = self._find_dependents(node_id, graph)
        for dep_id in dependents:
            self.invalidate(dep_id)
            invalidated.add(dep_id)
        return invalidated

    def _find_dependents(
        self, node_id: str, graph: Dict[str, Dict]
    ) -> Set[str]:
        """Find all nodes that (transitively) depend on node_id."""
        dependents: Set[str] = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            for other_id, node_def in graph.items():
                if other_id in dependents:
                    continue
                for _input_name, input_val in node_def.get("inputs", {}).items():
                    if isinstance(input_val, list) and len(input_val) == 2:
                        source_id = str(input_val[0])
                        if source_id == current:
                            dependents.add(other_id)
                            queue.append(other_id)
                            break
        return dependents

    def clear(self):
        """Clear all cached data."""
        self._cache.clear()
        self._key_map.clear()
        logger.debug("Cache cleared")

    @property
    def size(self) -> int:
        return len(self._cache)
