"""Base node framework — every Onyx workflow node inherits from BaseNode.

Adapted from EVERA's node pattern (itself modeled after ComfyUI):
  - define_schema() declares inputs, outputs, category
  - execute(**kwargs) runs the node logic, returns tuple of outputs
  - validate(**kwargs) optional pre-flight check
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .types import NodeType


# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

@dataclass
class Input:
    """Declares a node input socket."""

    name: str
    type: NodeType
    required: bool = True
    default: Any = None
    tooltip: str = ""
    options: Optional[List[Any]] = None  # for dropdown/combo inputs
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    step: Optional[float] = None
    multiline: bool = False  # for STRING text areas
    display: str = "default"  # "default", "slider", "hidden"

    @classmethod
    def required_input(cls, name: str, type: NodeType, **kw) -> "Input":
        return cls(name=name, type=type, required=True, **kw)

    @classmethod
    def optional_input(cls, name: str, type: NodeType, default: Any = None, **kw) -> "Input":
        return cls(name=name, type=type, required=False, default=default, **kw)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "name": self.name,
            "type": self.type.value,
            "required": self.required,
        }
        if self.default is not None:
            d["default"] = self.default
        if self.tooltip:
            d["tooltip"] = self.tooltip
        if self.options:
            d["options"] = self.options
        if self.min_val is not None:
            d["min"] = self.min_val
        if self.max_val is not None:
            d["max"] = self.max_val
        if self.step is not None:
            d["step"] = self.step
        if self.multiline:
            d["multiline"] = True
        if self.display != "default":
            d["display"] = self.display
        return d


@dataclass
class Output:
    """Declares a node output socket."""

    name: str
    type: NodeType
    tooltip: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "name": self.name,
            "type": self.type.value,
        }
        if self.tooltip:
            d["tooltip"] = self.tooltip
        return d


@dataclass
class NodeSchema:
    """Complete schema for a node class."""

    node_id: str            # e.g. "onyx.voice.Speak"
    display_name: str       # e.g. "Speak (TTS)"
    category: str           # e.g. "onyx/voice"
    inputs: List[Input] = field(default_factory=list)
    outputs: List[Output] = field(default_factory=list)
    description: str = ""
    is_output_node: bool = False  # terminal node (SaveFile, Preview, etc.)
    icon: str = ""
    extension: str = ""     # which extension this belongs to: "onyx", "evera", etc.

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "display_name": self.display_name,
            "category": self.category,
            "description": self.description,
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": [o.to_dict() for o in self.outputs],
            "is_output_node": self.is_output_node,
            "icon": self.icon,
            "extension": self.extension,
        }

    def input_by_name(self, name: str) -> Optional[Input]:
        for inp in self.inputs:
            if inp.name == name:
                return inp
        return None


# ---------------------------------------------------------------------------
# BaseNode — all nodes inherit from this
# ---------------------------------------------------------------------------

class BaseNode:
    """Abstract base for all Onyx workflow nodes."""

    # Set by the executor before execute()
    _progress_callback: Optional[Callable] = None
    _node_id: str = ""  # instance ID within a workflow

    @classmethod
    def define_schema(cls) -> NodeSchema:
        """Declare inputs, outputs, category, display name. Must override."""
        raise NotImplementedError(f"{cls.__name__} must implement define_schema()")

    def execute(self, **kwargs) -> Tuple:
        """
        Run the node logic.

        Receives all inputs as keyword arguments (matching schema input names).
        Returns a tuple of outputs in the same order as schema outputs.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement execute()")

    def validate(self, **kwargs) -> Optional[str]:
        """
        Optional pre-execution validation.

        Returns an error message string if validation fails, None if OK.
        """
        return None

    def on_progress(self, current: int, total: int, message: str = ""):
        """Emit a progress update (forwarded to GUI by executor)."""
        if self._progress_callback:
            self._progress_callback(self._node_id, current, total, message)

    @classmethod
    def get_schema(cls) -> NodeSchema:
        """Convenience: get schema and cache it on the class."""
        if not hasattr(cls, "_cached_schema"):
            cls._cached_schema = cls.define_schema()
        return cls._cached_schema

    @classmethod
    def schema_dict(cls) -> Dict[str, Any]:
        """Schema as JSON-serializable dict."""
        return cls.get_schema().to_dict()
