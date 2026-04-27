"""Onyx utility nodes — file I/O, text, routing, delay.

These are the core building blocks available in every workflow,
independent of any external extension.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from core.nodes.base_node import BaseNode, Input, NodeSchema, Output
from core.nodes.types import NodeType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input nodes — manual values
# ---------------------------------------------------------------------------

class TextInput(BaseNode):
    """Manual text entry node."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="onyx.input.TextInput",
            display_name="Text Input",
            category="onyx/input",
            description="Enter text manually — use for prompts, descriptions, file paths",
            icon="\U0001f4dd",
            extension="onyx",
            inputs=[
                Input.required_input("text", NodeType.STRING, multiline=True),
            ],
            outputs=[
                Output("text", NodeType.STRING, "Text value"),
            ],
        )

    def execute(self, text: str = "", **kw) -> Tuple:
        return (text,)


class NumberInput(BaseNode):
    """Manual number entry with optional slider."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="onyx.input.NumberInput",
            display_name="Number Input",
            category="onyx/input",
            description="Number value (float or int)",
            icon="\U0001f522",
            extension="onyx",
            inputs=[
                Input.required_input(
                    "value", NodeType.FLOAT,
                    min_val=-100000.0, max_val=100000.0, step=1.0,
                ),
            ],
            outputs=[
                Output("value", NodeType.FLOAT, "Number value"),
                Output("as_int", NodeType.INT, "Rounded to integer"),
            ],
        )

    def execute(self, value: float = 0.0, **kw) -> Tuple:
        return (value, int(round(value)))


class BoolInput(BaseNode):
    """Boolean toggle."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="onyx.input.BoolInput",
            display_name="Bool Input",
            category="onyx/input",
            description="True/False toggle",
            icon="\u2714\ufe0f",
            extension="onyx",
            inputs=[
                Input.required_input("value", NodeType.BOOL),
            ],
            outputs=[
                Output("value", NodeType.BOOL, "Boolean value"),
            ],
        )

    def execute(self, value: bool = True, **kw) -> Tuple:
        return (value,)


# ---------------------------------------------------------------------------
# File I/O nodes
# ---------------------------------------------------------------------------

class ReadFile(BaseNode):
    """Read a text file from disk."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="onyx.file.ReadFile",
            display_name="Read File",
            category="onyx/file",
            description="Read a text file and output its contents",
            icon="\U0001f4c4",
            extension="onyx",
            inputs=[
                Input.required_input("path", NodeType.FILE_PATH, tooltip="Absolute or relative file path"),
            ],
            outputs=[
                Output("content", NodeType.STRING, "File contents"),
                Output("path", NodeType.FILE_PATH, "Resolved absolute path"),
            ],
        )

    def validate(self, **kw) -> Optional[str]:
        path = kw.get("path", "")
        if not path:
            return "path is required"
        if not os.path.exists(path):
            return f"File not found: {path}"
        return None

    def execute(self, path: str = "", **kw) -> Tuple:
        abs_path = os.path.abspath(path)
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        return (content, abs_path)


class WriteFile(BaseNode):
    """Write text content to a file."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="onyx.file.WriteFile",
            display_name="Write File",
            category="onyx/file",
            description="Write text content to a file on disk",
            icon="\U0001f4be",
            extension="onyx",
            is_output_node=True,
            inputs=[
                Input.required_input("path", NodeType.FILE_PATH),
                Input.required_input("content", NodeType.STRING),
                Input.optional_input("append", NodeType.BOOL, default=False),
            ],
            outputs=[
                Output("path", NodeType.FILE_PATH, "Path to written file"),
                Output("size", NodeType.INT, "File size in bytes"),
            ],
        )

    def execute(self, path: str = "", content: str = "",
                append: bool = False, **kw) -> Tuple:
        abs_path = os.path.abspath(path)
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
        mode = "a" if append else "w"
        with open(abs_path, mode, encoding="utf-8") as f:
            f.write(content)
        size = os.path.getsize(abs_path)
        return (abs_path, size)


class ListFiles(BaseNode):
    """List files in a directory."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="onyx.file.ListFiles",
            display_name="List Files",
            category="onyx/file",
            description="List files in a directory, optionally filtered by extension",
            icon="\U0001f4c1",
            extension="onyx",
            inputs=[
                Input.required_input("directory", NodeType.FILE_PATH),
                Input.optional_input("extension", NodeType.STRING, default="",
                                     tooltip="Filter by extension (e.g. '.wav')"),
            ],
            outputs=[
                Output("files", NodeType.ANY, "List of file paths"),
                Output("count", NodeType.INT, "Number of files found"),
            ],
        )

    def execute(self, directory: str = "", extension: str = "", **kw) -> Tuple:
        if not os.path.isdir(directory):
            return ([], 0)
        files = []
        for entry in sorted(os.listdir(directory)):
            full = os.path.join(directory, entry)
            if os.path.isfile(full):
                if extension and not entry.lower().endswith(extension.lower()):
                    continue
                files.append(full)
        return (files, len(files))


# ---------------------------------------------------------------------------
# Routing / control flow
# ---------------------------------------------------------------------------

class Switch(BaseNode):
    """Conditional routing — pick A or B based on a boolean."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="onyx.flow.Switch",
            display_name="Switch",
            category="onyx/flow",
            description="Output A if condition is True, else B",
            icon="\U0001f500",
            extension="onyx",
            inputs=[
                Input.required_input("condition", NodeType.BOOL),
                Input.required_input("if_true", NodeType.ANY),
                Input.required_input("if_false", NodeType.ANY),
            ],
            outputs=[
                Output("result", NodeType.ANY, "Selected value"),
            ],
        )

    def execute(self, condition: bool = True, if_true: Any = None,
                if_false: Any = None, **kw) -> Tuple:
        return (if_true if condition else if_false,)


class Collect(BaseNode):
    """Gather multiple inputs into a list."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="onyx.flow.Collect",
            display_name="Collect",
            category="onyx/flow",
            description="Gather up to 8 items into a list",
            icon="\U0001f4e5",
            extension="onyx",
            inputs=[
                Input.optional_input(f"item_{i}", NodeType.ANY) for i in range(8)
            ],
            outputs=[
                Output("items", NodeType.ANY, "List of collected items"),
                Output("count", NodeType.INT, "Number of non-None items"),
            ],
        )

    def execute(self, **kw) -> Tuple:
        items = []
        for i in range(8):
            val = kw.get(f"item_{i}")
            if val is not None:
                items.append(val)
        return (items, len(items))


class Delay(BaseNode):
    """Pause execution for a specified duration."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="onyx.flow.Delay",
            display_name="Delay",
            category="onyx/flow",
            description="Pause for N seconds before passing data through",
            icon="\u23f3",
            extension="onyx",
            inputs=[
                Input.required_input("passthrough", NodeType.ANY),
                Input.optional_input("seconds", NodeType.FLOAT, default=1.0,
                                     min_val=0.0, max_val=300.0, step=0.5),
            ],
            outputs=[
                Output("passthrough", NodeType.ANY, "Same value, unchanged"),
            ],
        )

    def execute(self, passthrough: Any = None, seconds: float = 1.0, **kw) -> Tuple:
        if seconds > 0:
            time.sleep(seconds)
        return (passthrough,)


class JoinText(BaseNode):
    """Concatenate multiple text strings."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="onyx.text.JoinText",
            display_name="Join Text",
            category="onyx/text",
            description="Concatenate multiple text inputs with a separator",
            icon="\U0001f517",
            extension="onyx",
            inputs=[
                Input.optional_input("text_0", NodeType.STRING, default=""),
                Input.optional_input("text_1", NodeType.STRING, default=""),
                Input.optional_input("text_2", NodeType.STRING, default=""),
                Input.optional_input("text_3", NodeType.STRING, default=""),
                Input.optional_input("separator", NodeType.STRING, default="\n"),
            ],
            outputs=[
                Output("result", NodeType.STRING, "Joined text"),
            ],
        )

    def execute(self, separator: str = "\n", **kw) -> Tuple:
        parts = []
        for i in range(4):
            val = kw.get(f"text_{i}", "")
            if val:
                parts.append(str(val))
        return (separator.join(parts),)


class FormatTemplate(BaseNode):
    """Fill a template string with named values."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="onyx.text.FormatTemplate",
            display_name="Format Template",
            category="onyx/text",
            description="Python-style string formatting: {var1}, {var2}, etc.",
            icon="\U0001f4cb",
            extension="onyx",
            inputs=[
                Input.required_input("template", NodeType.STRING, multiline=True,
                                     tooltip="Template with {placeholders}"),
                Input.optional_input("var1", NodeType.STRING, default=""),
                Input.optional_input("var2", NodeType.STRING, default=""),
                Input.optional_input("var3", NodeType.STRING, default=""),
                Input.optional_input("var4", NodeType.STRING, default=""),
            ],
            outputs=[
                Output("result", NodeType.STRING, "Formatted text"),
            ],
        )

    def execute(self, template: str = "", **kw) -> Tuple:
        try:
            result = template.format(
                var1=kw.get("var1", ""),
                var2=kw.get("var2", ""),
                var3=kw.get("var3", ""),
                var4=kw.get("var4", ""),
            )
        except (KeyError, IndexError, ValueError):
            result = template
        return (result,)


# ---------------------------------------------------------------------------
# Debug / output
# ---------------------------------------------------------------------------

class LogOutput(BaseNode):
    """Log a value to the console (terminal node)."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="onyx.output.Log",
            display_name="Log Output",
            category="onyx/output",
            description="Log any value to the Onyx console for debugging",
            icon="\U0001f4ac",
            extension="onyx",
            is_output_node=True,
            inputs=[
                Input.required_input("value", NodeType.ANY),
                Input.optional_input("label", NodeType.STRING, default=""),
            ],
            outputs=[
                Output("value", NodeType.ANY, "Pass-through of the input"),
            ],
        )

    def execute(self, value: Any = None, label: str = "", **kw) -> Tuple:
        prefix = f"[{label}] " if label else ""
        logger.info("%s%s", prefix, value)
        return (value,)
