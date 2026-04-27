"""OnyxComponent — the unified contract every capability implements.

Onyx is the brain. Components are the instruments it picks up.
Each component is a black box:
  - Onyx says: "blender.execute('build_scene', {'description': 'a cat'})"
  - Component replies: ComponentResult(status=done, output={...})

Components NEVER talk to each other directly. All communication
flows through Onyx (the pipeline orchestrator).

Contract:
    name          — unique id ("blender", "music", "youtube")
    display_name  — human-readable ("Blender 3D")
    description   — what it does
    category      — "creative", "production", "learning", "platform"
    status        — ready / busy / failed / unavailable
    capabilities  — list of action names it supports
    knowledge_file — path to its compartmentalized knowledge JSON

    execute(action, params) → ComponentResult
    get_actions()           → list of action descriptors
    health_check()          → readiness report
    get_knowledge()         → load its own knowledge file
    save_knowledge(data)    — persist updated knowledge
"""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from enum import StrEnum
from typing import Any, Dict, List, Optional

_log = logging.getLogger("core.components")

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_KNOWLEDGE_DIR = os.path.join(_ROOT, "data", "knowledge")


# ---------------------------------------------------------------------------
# Status & Result
# ---------------------------------------------------------------------------

class ComponentStatus(StrEnum):
    """Current state of a component."""
    READY = "ready"
    BUSY = "busy"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass
class ComponentResult:
    """Standardized result from any component action.

    Every component returns this — the brain never sees raw internals.
    """
    status: str = "done"        # done, failed, partial, skipped
    output: Dict = field(default_factory=dict)
    error: str = ""
    duration: float = 0.0       # seconds
    # If this action produces an artifact (file, URL, etc.)
    artifact_path: str = ""
    artifact_type: str = ""     # "video", "audio", "image", "blend", "json"
    # For chaining — downstream components can read this
    chain_data: Dict = field(default_factory=dict)
    # Human-readable summary for Onyx to narrate
    summary: str = ""

    @property
    def ok(self) -> bool:
        return self.status in ("done", "partial")

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Action descriptor
# ---------------------------------------------------------------------------

@dataclass
class ActionDescriptor:
    """Describes a single action a component can perform."""
    name: str
    description: str
    params: List[str] = field(default_factory=list)
    required_params: List[str] = field(default_factory=list)
    returns: str = ""           # what the output dict contains
    risk_level: str = "low"     # low, medium, high (for safety checks)
    estimated_duration: str = ""  # "fast", "seconds", "minutes", "long"

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Base component
# ---------------------------------------------------------------------------

class OnyxComponent(ABC):
    """Abstract base class for all Onyx components.

    Subclass this for each capability domain:
        class BlenderComponent(OnyxComponent):
            name = "blender"
            ...
    """

    # -- Identity (override in subclass) --

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique component identifier (e.g. 'blender', 'music')."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name (e.g. 'Blender 3D')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line description of what this component does."""
        ...

    @property
    def category(self) -> str:
        """Component category for grouping."""
        return "general"

    @property
    def version(self) -> str:
        """Component version string."""
        return "1.0.0"

    # -- Status --

    def __init__(self):
        self._status: ComponentStatus = ComponentStatus.READY
        self._last_error: str = ""
        self._action_count: int = 0
        self._total_duration: float = 0.0
        self._last_action_at: float = 0.0

    @property
    def status(self) -> ComponentStatus:
        return self._status

    @status.setter
    def status(self, value: ComponentStatus):
        self._status = value

    # -- Core contract --

    @abstractmethod
    def get_actions(self) -> List[ActionDescriptor]:
        """Return all actions this component supports.

        The brain uses this to know what it can ask for.
        """
        ...

    @abstractmethod
    def execute(self, action: str, params: Optional[Dict] = None) -> ComponentResult:
        """Execute an action. This is the ONLY entry point.

        Args:
            action: Action name (must be in get_actions()).
            params: Action-specific parameters.

        Returns:
            ComponentResult with status, output, and optional artifacts.
        """
        ...

    def health_check(self) -> Dict[str, Any]:
        """Check if this component is ready to work.

        Returns dict with:
            ready: bool
            status: ComponentStatus
            missing: list of missing dependencies
            message: human-readable status
        """
        return {
            "ready": self._status == ComponentStatus.READY,
            "status": str(self._status),
            "missing": [],
            "message": f"{self.display_name} is {self._status}",
        }

    # -- Knowledge compartmentalization --

    @property
    def knowledge_file(self) -> str:
        """Path to this component's knowledge JSON."""
        return os.path.join(_KNOWLEDGE_DIR, f"{self.name}.json")

    def get_knowledge(self) -> Dict:
        """Load this component's compartmentalized knowledge."""
        try:
            if os.path.exists(self.knowledge_file):
                with open(self.knowledge_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            _log.warning("Failed to load knowledge for %s: %s", self.name, e)
        return {}

    def save_knowledge(self, data: Dict) -> bool:
        """Persist updated knowledge for this component."""
        try:
            os.makedirs(os.path.dirname(self.knowledge_file), exist_ok=True)
            with open(self.knowledge_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            _log.error("Failed to save knowledge for %s: %s", self.name, e)
            return False

    # -- Execution wrapper (tracks metrics) --

    def _run(self, action: str, params: Optional[Dict] = None) -> ComponentResult:
        """Wrapper around execute() that tracks metrics and handles errors.

        Subclasses should NOT override this — override execute() instead.
        """
        params = params or {}
        start = time.time()
        self._status = ComponentStatus.BUSY
        self._last_action_at = start

        try:
            result = self.execute(action, params)
            duration = time.time() - start
            result.duration = duration
            self._action_count += 1
            self._total_duration += duration

            if result.ok:
                self._status = ComponentStatus.READY
                self._last_error = ""
            else:
                self._status = ComponentStatus.FAILED
                self._last_error = result.error

            return result

        except Exception as e:
            duration = time.time() - start
            self._status = ComponentStatus.FAILED
            self._last_error = str(e)
            _log.error("Component %s action %s failed: %s", self.name, action, e)
            return ComponentResult(
                status="failed",
                error=str(e),
                duration=duration,
                summary=f"{self.display_name} failed: {e}",
            )

    # -- Stats --

    def get_stats(self) -> Dict:
        """Return component usage statistics."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "status": str(self._status),
            "action_count": self._action_count,
            "total_duration": round(self._total_duration, 2),
            "last_error": self._last_error,
            "last_action_at": self._last_action_at,
        }

    # -- String representation --

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} '{self.name}' [{self._status}]>"

    def __str__(self) -> str:
        actions = [a.name for a in self.get_actions()]
        return (f"{self.display_name} ({self.name}) — {self.description}\n"
                f"  Status: {self._status}\n"
                f"  Actions: {', '.join(actions)}")
