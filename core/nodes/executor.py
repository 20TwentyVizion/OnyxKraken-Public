"""Workflow execution engine — DAG traversal with progress reporting.

Takes a workflow JSON dict, resolves the dependency graph, and executes
nodes in topological order with caching.

Execution strategy (from agentic AI best-practices):
  - Parallel tasks  → independent DAG branches run concurrently
                       (orchestrated centralized executor)
  - Sequential tasks → single-threaded chain, no inter-thread overhead
  - Connectors      → batch pre-started in parallel before execution
                       (decentralized lifecycle, centralized orchestration)

No VRAM scheduler — Onyx orchestrates external apps (EVERA, SmartEngine,
JustEdit) as services. Each extension connector handles its own resource
management.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .base_node import BaseNode
from .cache import ExecutionCache
from .registry import NodeRegistry

logger = logging.getLogger(__name__)


class WorkflowError(Exception):
    """Base error for workflow execution."""
    pass


class NodeValidationError(WorkflowError):
    """A node failed validation before execution."""
    def __init__(self, node_id: str, message: str):
        self.node_id = node_id
        super().__init__(f"Node {node_id}: {message}")


class CyclicGraphError(WorkflowError):
    """The workflow graph has a cycle (invalid DAG)."""
    pass


class WorkflowExecutor:
    """Execute a workflow JSON through the node graph."""

    def __init__(
        self,
        registry: Optional[NodeRegistry] = None,
        cache: Optional[ExecutionCache] = None,
        progress_callback: Optional[Callable] = None,
    ):
        from .registry import get_registry
        self.registry = registry or get_registry()
        self.cache = cache or ExecutionCache()
        self.progress_callback = progress_callback

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    def execute(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a complete workflow.

        Uses level-parallel execution: nodes at the same topological
        depth with no mutual dependencies run concurrently.  Sequential
        chains stay single-threaded to avoid error cascades.

        Args:
            workflow: Dict with "nodes" key containing node definitions.
                      Each node: {"class_type": str, "inputs": {...}}

        Returns:
            Dict mapping node_id -> output tuple for every executed node.
        """
        graph = workflow.get("nodes", workflow)
        if not graph:
            raise WorkflowError("Empty workflow — no nodes defined")

        t0 = time.time()
        self._emit_workflow_status("started", {"node_count": len(graph)})

        # 1. Validate all node types exist
        self._validate_node_types(graph)

        # 2. Pre-start required connectors in parallel
        self._prestart_connectors(graph)

        # 3. Build execution levels (parallel groups)
        levels = self._topological_levels(graph)
        flat_order = [nid for level in levels for nid in level]
        logger.info("Execution levels: %s",
                    " | ".join(" ".join(lv) for lv in levels))

        # 4. Execute level-by-level
        results: Dict[str, Any] = {}
        errors: Dict[str, str] = {}
        results_lock = threading.Lock()

        for depth, level in enumerate(levels):
            if len(level) == 1:
                # Single node — run inline (sequential tip: no overhead)
                node_id = level[0]
                self._run_one(node_id, graph, results, errors, results_lock)
            else:
                # Multiple independent nodes — run in parallel
                self._run_parallel(level, graph, results, errors, results_lock)

        elapsed = time.time() - t0
        self._emit_workflow_status("completed", {
            "total_time": round(elapsed, 2),
            "node_count": len(graph),
            "errors": errors,
        })

        logger.info(
            "Workflow complete: %d nodes in %d levels, %.1fs, %d errors",
            len(graph), len(levels), elapsed, len(errors),
        )
        return results

    # ------------------------------------------------------------------
    # Level-parallel helpers
    # ------------------------------------------------------------------

    def _run_one(
        self,
        node_id: str,
        graph: Dict[str, Dict],
        results: Dict[str, Any],
        errors: Dict[str, str],
        lock: threading.Lock,
    ):
        """Execute a single node inline."""
        node_def = graph[node_id]
        class_type = node_def["class_type"]
        try:
            output = self._execute_node(node_id, node_def, graph, results)
            with lock:
                results[node_id] = output
        except Exception as e:
            logger.error("Node %s (%s) failed: %s", node_id, class_type, e)
            with lock:
                errors[node_id] = str(e)
                results[node_id] = None
            self._emit_node_status(node_id, "error", {"error": str(e)})

    def _run_parallel(
        self,
        level: List[str],
        graph: Dict[str, Dict],
        results: Dict[str, Any],
        errors: Dict[str, str],
        lock: threading.Lock,
    ):
        """Execute independent nodes in parallel (orchestrated centralized)."""
        max_workers = min(len(level), 4)
        with ThreadPoolExecutor(max_workers=max_workers,
                                thread_name_prefix="wf-node") as pool:
            futures = {
                pool.submit(self._run_one, nid, graph, results, errors, lock): nid
                for nid in level
            }
            for future in as_completed(futures):
                nid = futures[future]
                exc = future.exception()
                if exc:
                    logger.error("Node %s thread exception: %s", nid, exc)
                    with lock:
                        errors[nid] = str(exc)
                        results[nid] = None

    # ------------------------------------------------------------------
    # Single node execution
    # ------------------------------------------------------------------

    def _execute_node(
        self,
        node_id: str,
        node_def: Dict[str, Any],
        graph: Dict[str, Dict],
        results: Dict[str, Any],
    ) -> Tuple:
        """Execute a single node, resolving inputs from results/cache."""
        class_type = node_def["class_type"]
        node_class = self.registry.get_or_raise(class_type)
        schema = node_class.get_schema()

        # Resolve inputs
        resolved = self._resolve_inputs(
            node_def.get("inputs", {}), schema, results
        )

        # Check cache
        cached = self.cache.get(node_id, class_type, resolved)
        if cached is not None:
            self._emit_node_status(node_id, "cached")
            return cached

        # Instantiate and validate
        node = node_class()
        node._node_id = node_id
        node._progress_callback = self._make_progress_callback()

        error = node.validate(**resolved)
        if error:
            raise NodeValidationError(node_id, error)

        # Execute
        self._emit_node_status(node_id, "running", {"class_type": class_type})
        t0 = time.time()

        output = node.execute(**resolved)

        elapsed = time.time() - t0
        self._emit_node_status(node_id, "done", {
            "class_type": class_type,
            "elapsed": round(elapsed, 2),
        })

        # Cache the result
        self.cache.store(node_id, class_type, resolved, output)

        logger.info("Node %s (%s): %.1fs", node_id, class_type, elapsed)
        return output

    # ------------------------------------------------------------------
    # Input resolution
    # ------------------------------------------------------------------

    def _resolve_inputs(
        self,
        raw_inputs: Dict[str, Any],
        schema: Any,
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Resolve node inputs from workflow JSON.

        - Direct values (strings, numbers, bools) pass through
        - Connections [node_id, output_index] are resolved from results
        - Missing optional inputs use schema defaults
        """
        resolved: Dict[str, Any] = {}

        for input_name, input_value in raw_inputs.items():
            if isinstance(input_value, list) and len(input_value) == 2:
                # Connection: [source_node_id, output_index]
                source_id = str(input_value[0])
                output_idx = int(input_value[1])

                if source_id not in results or results[source_id] is None:
                    raise WorkflowError(
                        f"Input '{input_name}' references node {source_id} "
                        f"which has no output (failed or not yet executed)"
                    )

                source_output = results[source_id]
                if isinstance(source_output, tuple):
                    if output_idx >= len(source_output):
                        raise WorkflowError(
                            f"Input '{input_name}' references output index "
                            f"{output_idx} from node {source_id}, but it "
                            f"only has {len(source_output)} outputs"
                        )
                    resolved[input_name] = source_output[output_idx]
                else:
                    resolved[input_name] = source_output
            else:
                # Direct value
                resolved[input_name] = input_value

        # Fill in defaults for missing optional inputs
        if schema:
            for inp in schema.inputs:
                if inp.name not in resolved and not inp.required:
                    resolved[inp.name] = inp.default

        return resolved

    # ------------------------------------------------------------------
    # Topological sort (Kahn's algorithm)
    # ------------------------------------------------------------------

    def _build_graph_meta(self, graph: Dict[str, Dict]):
        """Compute in-degrees and dependency map. Shared by sort & levels."""
        in_degree: Dict[str, int] = {nid: 0 for nid in graph}
        dependents: Dict[str, List[str]] = defaultdict(list)

        for node_id, node_def in graph.items():
            for _input_name, input_val in node_def.get("inputs", {}).items():
                if isinstance(input_val, list) and len(input_val) == 2:
                    source_id = str(input_val[0])
                    if source_id in graph:
                        in_degree[node_id] = in_degree.get(node_id, 0) + 1
                        dependents[source_id].append(node_id)
        return in_degree, dependents

    def _topological_sort(self, graph: Dict[str, Dict]) -> List[str]:
        """Sort nodes in dependency order. Raises CyclicGraphError on cycles."""
        in_degree, dependents = self._build_graph_meta(graph)

        queue: deque = deque()
        for nid in graph:
            if in_degree.get(nid, 0) == 0:
                queue.append(nid)

        order: List[str] = []
        while queue:
            node_id = queue.popleft()
            order.append(node_id)
            for dep in dependents.get(node_id, []):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

        if len(order) != len(graph):
            remaining = set(graph.keys()) - set(order)
            raise CyclicGraphError(
                f"Workflow has a cycle involving nodes: {remaining}"
            )
        return order

    def _topological_levels(self, graph: Dict[str, Dict]) -> List[List[str]]:
        """Group nodes into parallel execution levels.

        Level 0 = all source nodes (no dependencies).
        Level N = nodes whose deps are all in levels < N.
        Nodes within the same level are independent and can run in parallel.
        """
        in_degree, dependents = self._build_graph_meta(graph)

        queue: deque = deque()
        for nid in graph:
            if in_degree.get(nid, 0) == 0:
                queue.append(nid)

        levels: List[List[str]] = []
        visited = 0

        while queue:
            level = list(queue)
            levels.append(level)
            visited += len(level)
            queue.clear()
            for node_id in level:
                for dep in dependents.get(node_id, []):
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(dep)

        if visited != len(graph):
            remaining = set(graph.keys()) - {n for lv in levels for n in lv}
            raise CyclicGraphError(
                f"Workflow has a cycle involving nodes: {remaining}"
            )
        return levels

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_node_types(self, graph: Dict[str, Dict]):
        """Check all node class_types are registered."""
        for node_id, node_def in graph.items():
            class_type = node_def.get("class_type")
            if not class_type:
                raise WorkflowError(f"Node {node_id} missing 'class_type'")
            if self.registry.get(class_type) is None:
                raise WorkflowError(
                    f"Node {node_id}: unknown class_type '{class_type}'. "
                    f"Registered: {self.registry.node_ids}"
                )

    def validate_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a workflow without executing it. Returns validation result."""
        graph = workflow.get("nodes", workflow)
        errors = []

        # Check node types
        for node_id, node_def in graph.items():
            class_type = node_def.get("class_type", "")
            if not self.registry.get(class_type):
                errors.append(f"Node {node_id}: unknown class_type '{class_type}'")

        # Check for cycles
        order = []
        try:
            order = self._topological_sort(graph)
        except Exception as e:
            errors.append(str(e))

        # Check connections reference existing nodes
        for node_id, node_def in graph.items():
            for input_name, input_val in node_def.get("inputs", {}).items():
                if isinstance(input_val, list) and len(input_val) == 2:
                    source_id = str(input_val[0])
                    if source_id not in graph:
                        errors.append(
                            f"Node {node_id} input '{input_name}' references "
                            f"non-existent node {source_id}"
                        )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "node_count": len(graph),
            "execution_order": order if not errors else [],
        }

    # ------------------------------------------------------------------
    # Progress emission
    # ------------------------------------------------------------------

    def _emit_node_status(
        self, node_id: str, status: str, data: Optional[Dict] = None
    ):
        if self.progress_callback:
            self.progress_callback({
                "type": f"node_{status}",
                "node_id": node_id,
                **(data or {}),
            })

    def _emit_workflow_status(
        self, status: str, data: Optional[Dict] = None
    ):
        if self.progress_callback:
            self.progress_callback({
                "type": f"workflow_{status}",
                **(data or {}),
            })

    def _make_progress_callback(self) -> Callable:
        """Create a per-node progress callback."""
        def cb(node_id: str, current: int, total: int, message: str = ""):
            if self.progress_callback:
                self.progress_callback({
                    "type": "node_progress",
                    "node_id": node_id,
                    "progress": current / max(total, 1),
                    "current": current,
                    "total": total,
                    "message": message,
                })
        return cb

    # ------------------------------------------------------------------
    # Connector pre-start (decentralized lifecycle, central orchestration)
    # ------------------------------------------------------------------

    def _prestart_connectors(self, graph: Dict[str, Dict]):
        """Identify which extensions are needed and start them in parallel.

        This avoids the sequential pattern where each Start node blocks
        waiting for its extension to boot — instead they all boot at once.
        """
        needed: Set[str] = set()
        for node_def in graph.values():
            ct = node_def.get("class_type", "")
            parts = ct.split(".")
            if parts[0] in ("evera", "smartengine", "justedit"):
                needed.add(parts[0])

        if not needed:
            return

        from .connector import get_connector

        def _start(ext_name: str):
            conn = get_connector(ext_name)
            if conn and not conn.is_running():
                logger.info("Pre-starting %s connector", ext_name)
                conn.ensure_running()

        self._emit_workflow_status("prestart", {"extensions": list(needed)})

        if len(needed) == 1:
            _start(needed.pop())
        else:
            with ThreadPoolExecutor(max_workers=len(needed),
                                    thread_name_prefix="wf-prestart") as pool:
                list(pool.map(_start, needed))
