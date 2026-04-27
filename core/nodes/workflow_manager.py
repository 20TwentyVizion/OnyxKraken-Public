"""Workflow manager — load, save, validate, execute workflows.

Central API for the rest of OnyxKraken to interact with the node system.
Used by both the GUI (list-based builder, visual canvas) and the agent.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .cache import ExecutionCache
from .executor import WorkflowExecutor, WorkflowError
from .registry import NodeRegistry, get_registry

logger = logging.getLogger(__name__)

# Default paths
_ROOT = Path(__file__).parent.parent.parent  # OnyxKraken root
PRESETS_DIR = Path(__file__).parent / "presets"
USER_WORKFLOWS_DIR = _ROOT / "data" / "workflows"


class WorkflowManager:
    """High-level API for workflow operations.

    Thread-safe — execution runs in background threads with callbacks.
    """

    def __init__(
        self,
        registry: Optional[NodeRegistry] = None,
        progress_callback: Optional[Callable] = None,
    ):
        self.registry = registry or get_registry()
        self.progress_callback = progress_callback
        self._cache = ExecutionCache()
        self._running: Dict[str, threading.Thread] = {}
        self._results: Dict[str, Any] = {}
        self._initialized = False

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self) -> int:
        """Discover and register all nodes. Returns count of registered nodes."""
        if self._initialized:
            return self.registry.count
        count = self.registry.discover("core.nodes.catalog")
        self._initialized = True
        logger.info("WorkflowManager initialized: %d nodes", count)
        return count

    # ------------------------------------------------------------------
    # Node queries
    # ------------------------------------------------------------------

    def list_nodes(self) -> List[Dict]:
        """List all registered node schemas."""
        self.initialize()
        return self.registry.list_nodes()

    def list_by_category(self) -> Dict[str, List[Dict]]:
        """Nodes grouped by category."""
        self.initialize()
        return self.registry.list_by_category()

    def list_by_extension(self) -> Dict[str, List[Dict]]:
        """Nodes grouped by extension (onyx, evera, smartengine, justedit)."""
        self.initialize()
        return self.registry.list_by_extension()

    def get_node_schema(self, node_id: str) -> Optional[Dict]:
        """Get schema for a specific node type."""
        self.initialize()
        cls = self.registry.get(node_id)
        return cls.schema_dict() if cls else None

    # ------------------------------------------------------------------
    # Preset workflows
    # ------------------------------------------------------------------

    def list_presets(self) -> List[Dict]:
        """List all built-in preset workflows."""
        result = []
        if PRESETS_DIR.exists():
            for f in sorted(PRESETS_DIR.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    meta = data.get("meta", {})
                    meta["id"] = f.stem
                    meta["node_count"] = len(data.get("nodes", {}))
                    meta["file"] = str(f)
                    result.append(meta)
                except Exception as e:
                    logger.warning("Failed to load preset %s: %s", f.name, e)
        return result

    def load_preset(self, preset_id: str) -> Optional[Dict]:
        """Load a preset workflow by ID (filename without .json)."""
        path = PRESETS_DIR / f"{preset_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["meta"]["id"] = path.stem
            return data
        except Exception as e:
            logger.error("Failed to load preset %s: %s", preset_id, e)
            return None

    # ------------------------------------------------------------------
    # User workflows
    # ------------------------------------------------------------------

    def list_user_workflows(self) -> List[Dict]:
        """List user-saved workflows from data/workflows/."""
        result = []
        if USER_WORKFLOWS_DIR.exists():
            for f in sorted(USER_WORKFLOWS_DIR.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    meta = data.get("meta", {})
                    meta["id"] = f.stem
                    meta["node_count"] = len(data.get("nodes", {}))
                    meta["file"] = str(f)
                    result.append(meta)
                except Exception:
                    continue
        return result

    def save_workflow(self, workflow: Dict, name: str = "") -> str:
        """Save a workflow to data/workflows/. Returns file path."""
        USER_WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
        wf_name = name or workflow.get("meta", {}).get("name", "untitled")
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in wf_name)
        safe_name = safe_name.strip().replace(" ", "_").lower() or "workflow"
        path = USER_WORKFLOWS_DIR / f"{safe_name}.json"

        # Don't overwrite — append number
        counter = 1
        base = path.stem
        while path.exists():
            path = USER_WORKFLOWS_DIR / f"{base}_{counter}.json"
            counter += 1

        path.write_text(json.dumps(workflow, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Saved workflow: %s", path)
        return str(path)

    def load_workflow(self, path: str) -> Optional[Dict]:
        """Load a workflow from a file path."""
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Failed to load workflow %s: %s", path, e)
            return None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, workflow: Dict) -> Dict:
        """Validate a workflow without executing. Returns validation result."""
        self.initialize()
        executor = WorkflowExecutor(registry=self.registry)
        return executor.validate_workflow(workflow)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute_sync(self, workflow: Dict) -> Dict[str, Any]:
        """Execute a workflow synchronously. Returns results dict."""
        self.initialize()
        executor = WorkflowExecutor(
            registry=self.registry,
            cache=self._cache,
            progress_callback=self.progress_callback,
        )
        return executor.execute(workflow)

    def execute_async(
        self,
        workflow: Dict,
        workflow_id: str = "",
        on_complete: Optional[Callable] = None,
    ) -> str:
        """Execute a workflow in a background thread. Returns workflow_id."""
        import uuid
        wf_id = workflow_id or uuid.uuid4().hex[:8]

        def _run():
            try:
                results = self.execute_sync(workflow)
                self._results[wf_id] = {"status": "completed", "results": results}
                if on_complete:
                    on_complete(wf_id, results, None)
            except Exception as e:
                self._results[wf_id] = {"status": "error", "error": str(e)}
                if on_complete:
                    on_complete(wf_id, None, e)
            finally:
                self._running.pop(wf_id, None)

        self._results[wf_id] = {"status": "running"}
        t = threading.Thread(target=_run, name=f"workflow-{wf_id}", daemon=True)
        self._running[wf_id] = t
        t.start()
        logger.info("Workflow %s started in background", wf_id)
        return wf_id

    def get_status(self, workflow_id: str) -> Optional[Dict]:
        """Get the status of a running or completed workflow."""
        return self._results.get(workflow_id)

    def is_running(self, workflow_id: str) -> bool:
        """Check if a workflow is currently executing."""
        return workflow_id in self._running

    def clear_cache(self):
        """Clear the execution cache."""
        self._cache.clear()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_manager: Optional[WorkflowManager] = None


def get_workflow_manager(
    progress_callback: Optional[Callable] = None,
) -> WorkflowManager:
    """Get or create the global WorkflowManager."""
    global _manager
    if _manager is None:
        _manager = WorkflowManager(progress_callback=progress_callback)
    elif progress_callback and _manager.progress_callback is None:
        _manager.progress_callback = progress_callback
    return _manager
