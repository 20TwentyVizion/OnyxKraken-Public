"""Toolsmith — Onyx's self-built tools ecosystem.

Manages tools that Onyx creates for itself:
  - Registry of built tools (calculator, notepad, etc.)
  - Launch internal tools instead of external apps when verified
  - Track tool status: draft → verified → preferred
  - Goal: Onyx builds its own functional ecosystem over time

Directory structure:
    tools/
    ├── registry.json          — Master catalog of all self-built tools
    ├── calculator/
    │   └── app.py             — The actual tool script
    ├── notepad/
    │   └── app.py
    └── ...
"""

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from typing import Optional

_log = logging.getLogger("core.toolsmith")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(_ROOT, "tools")
REGISTRY_PATH = os.path.join(TOOLS_DIR, "registry.json")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ToolEntry:
    """A single self-built tool."""
    name: str                   # e.g. "calculator"
    display_name: str           # e.g. "Onyx Calculator"
    description: str            # What it does
    script_path: str            # Relative path from tools/ e.g. "calculator/app.py"
    replaces: list[str]         # External apps this replaces e.g. ["calc", "calculator"]
    capabilities: list[str]     # What the tool can do e.g. ["arithmetic", "unit conversion"]
    status: str = "draft"       # "draft" | "verified" | "preferred"
    version: int = 1
    window_title: str = ""      # Title of the tkinter window when running

    @property
    def abs_path(self) -> str:
        return os.path.join(TOOLS_DIR, self.script_path)

    @property
    def is_verified(self) -> bool:
        return self.status in ("verified", "preferred")

    @property
    def is_preferred(self) -> bool:
        return self.status == "preferred"


# ---------------------------------------------------------------------------
# Registry management
# ---------------------------------------------------------------------------

def _ensure_dirs():
    os.makedirs(TOOLS_DIR, exist_ok=True)


def _load_registry() -> dict[str, dict]:
    """Load the tools registry from disk."""
    if not os.path.exists(REGISTRY_PATH):
        return {}
    try:
        with open(REGISTRY_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_registry(registry: dict[str, dict]):
    """Save the tools registry to disk."""
    _ensure_dirs()
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)


def list_tools() -> list[ToolEntry]:
    """List all self-built tools."""
    registry = _load_registry()
    return [ToolEntry(**v) for v in registry.values()]


def get_tool(name: str) -> Optional[ToolEntry]:
    """Get a tool by name."""
    registry = _load_registry()
    data = registry.get(name.lower())
    if data:
        return ToolEntry(**data)
    return None


def register_tool(entry: ToolEntry):
    """Register a new or updated tool."""
    _ensure_dirs()
    registry = _load_registry()
    registry[entry.name.lower()] = asdict(entry)
    _save_registry(registry)
    _log.info(f"Registered tool: {entry.name} (status={entry.status})")


def verify_tool(name: str) -> bool:
    """Mark a tool as user-verified. Returns True if found."""
    registry = _load_registry()
    key = name.lower()
    if key not in registry:
        return False
    registry[key]["status"] = "verified"
    _save_registry(registry)
    _log.info(f"Tool verified: {name}")
    return True


def prefer_tool(name: str) -> bool:
    """Mark a verified tool as preferred over external apps. Returns True if found."""
    registry = _load_registry()
    key = name.lower()
    if key not in registry:
        return False
    if registry[key]["status"] not in ("verified", "preferred"):
        _log.warning(f"Cannot prefer unverified tool: {name}")
        return False
    registry[key]["status"] = "preferred"
    _save_registry(registry)
    _log.info(f"Tool preferred: {name}")
    return True


def delete_tool(name: str) -> bool:
    """Delete a tool from the registry and optionally its files. Returns True if found."""
    registry = _load_registry()
    key = name.lower()
    if key not in registry:
        return False
    entry = registry.pop(key)
    _save_registry(registry)
    # Remove the tool's directory
    tool_dir = os.path.join(TOOLS_DIR, os.path.dirname(entry["script_path"]))
    if os.path.isdir(tool_dir):
        import shutil
        try:
            shutil.rmtree(tool_dir)
            _log.info(f"Deleted tool directory: {tool_dir}")
        except Exception as e:
            _log.warning(f"Could not delete tool directory {tool_dir}: {e}")
    _log.info(f"Deleted tool: {name}")
    return True


def edit_tool_code(name: str, change_description: str) -> tuple[bool, str]:
    """Use the LLM to modify a tool's source code based on user description.

    Returns (success, message).
    After editing, the tool is reset to 'draft' status (needs re-verification).
    """
    tool = get_tool(name)
    if tool is None:
        return False, f"Tool '{name}' not found."
    if not os.path.exists(tool.abs_path):
        return False, f"Tool script not found: {tool.abs_path}"

    # Read current source
    with open(tool.abs_path, "r", encoding="utf-8") as f:
        current_code = f.read()

    # Ask LLM to modify
    try:
        from agent.model_router import router
        prompt = (
            f"You are modifying a Python/tkinter application for OnyxKraken's self-built tool ecosystem.\n"
            f"Tool: {tool.display_name}\n"
            f"Description: {tool.description}\n\n"
            f"CURRENT SOURCE CODE:\n```python\n{current_code}\n```\n\n"
            f"USER'S REQUESTED CHANGES:\n{change_description}\n\n"
            f"RULES:\n"
            f"- Output ONLY the complete modified Python source code.\n"
            f"- Do NOT include markdown fences or explanations.\n"
            f"- Keep the same dark theme (colors starting with #0).\n"
            f"- Keep all existing functionality unless the user asked to remove it.\n"
            f"- The script must be runnable with `python app.py`.\n"
            f"- Maintain the if __name__ == '__main__' entry point.\n"
        )
        # Use dedicated build model for fast code generation
        import config as _cfg
        from agent.model_router import _get_ollama
        _build_model = getattr(_cfg, "BUILD_MODEL", "qwen3-coder:480b-cloud")
        _resp = _get_ollama().chat(model=_build_model,
                                    messages=[{"role": "user", "content": prompt}])
        modified = _resp.get("message", {}).get("content", "").strip()

        # Strip markdown fences if present
        import re
        modified = re.sub(r'^```(?:python)?\s*\n?', '', modified, flags=re.MULTILINE)
        modified = re.sub(r'\n?```\s*$', '', modified, flags=re.MULTILINE)
        modified = modified.strip()

        if not modified or "import" not in modified:
            return False, "LLM returned invalid code."

        # Write back
        with open(tool.abs_path, "w", encoding="utf-8") as f:
            f.write(modified)

        # Reset to draft — needs re-verification
        registry = _load_registry()
        key = name.lower()
        if key in registry:
            registry[key]["status"] = "draft"
            registry[key]["version"] = registry[key].get("version", 1) + 1
            _save_registry(registry)

        _log.info(f"Tool '{name}' edited and reset to draft (v{registry[key]['version']})")
        return True, f"Tool updated to v{registry[key]['version']}. Please test and verify."

    except Exception as e:
        _log.error(f"Failed to edit tool '{name}': {e}")
        return False, f"Edit failed: {e}"


def find_internal_replacement(app_name: str) -> Optional[ToolEntry]:
    """Check if there's a verified/preferred internal tool that replaces the given app.

    Returns the tool entry if one exists and is at least verified, else None.
    """
    app_lower = app_name.lower().strip()
    for tool in list_tools():
        if not tool.is_verified:
            continue
        # Check if this tool replaces the requested app
        for replacement in tool.replaces:
            if replacement.lower() == app_lower or app_lower in replacement.lower():
                return tool
    return None


# ---------------------------------------------------------------------------
# Tool launching
# ---------------------------------------------------------------------------

def launch_tool(name: str) -> Optional[subprocess.Popen]:
    """Launch a self-built tool by name. Returns the process or None."""
    tool = get_tool(name)
    if tool is None:
        _log.warning(f"Tool not found: {name}")
        return None
    if not os.path.exists(tool.abs_path):
        _log.error(f"Tool script not found: {tool.abs_path}")
        return None
    try:
        proc = subprocess.Popen(
            [sys.executable, tool.abs_path],
            cwd=os.path.dirname(tool.abs_path),
        )
        _log.info(f"Launched tool: {tool.display_name} (PID={proc.pid})")
        return proc
    except Exception as e:
        _log.error(f"Failed to launch tool {name}: {e}")
        return None


# ---------------------------------------------------------------------------
# Context for the planner/LLM
# ---------------------------------------------------------------------------

def get_toolsmith_context() -> str:
    """Return context string about available internal tools for the LLM planner."""
    tools = list_tools()
    if not tools:
        return (
            "\n[TOOLSMITH] Onyx has NO self-built tools yet. "
            "When a task requires basic utilities (calculator, notepad, etc.), "
            "Onyx should BUILD its own Python/tkinter version first, then use it. "
            "Use write_file to create tools/toolname/app.py, then run_command to test it. "
            "Self-built tools are preferred over external applications.\n"
        )

    lines = ["\n[TOOLSMITH] Onyx's self-built tools:"]
    for t in tools:
        status_icon = {"draft": "🔨", "verified": "✅", "preferred": "⭐"}.get(t.status, "?")
        lines.append(f"  {status_icon} {t.display_name} — {t.description} "
                      f"[status: {t.status}, replaces: {', '.join(t.replaces)}]")
        if t.is_preferred:
            lines.append(f"     → USE THIS instead of external {', '.join(t.replaces)}")

    # Emphasize self-built tools as extensions of Onyx
    lines.append("")
    lines.append("  IMPORTANT: Self-built tools are extensions of Onyx — like extra arms and hands.")
    lines.append("  Onyx can launch them, interact with their UI, and use them to complete tasks.")
    lines.append("  ALWAYS prefer self-built tools over external apps when a verified version exists.")
    lines.append("  To use a tool: launch_tool to open it, then interact via click/type/key_press.")
    lines.append("  When done using a tool, ALWAYS close it with close_window.")
    lines.append("")
    lines.append("  To build a NEW tool: write_file tools/toolname/app.py with a Python/tkinter app.")
    lines.append("  After building, test it with run_command. Once user verifies, it becomes preferred.\n")

    return "\n".join(lines)


def get_ecosystem_goal() -> str:
    """Return the long-term ecosystem goal for Onyx's self-improvement context."""
    tools = list_tools()
    verified = [t for t in tools if t.is_verified]
    preferred = [t for t in tools if t.is_preferred]

    return (
        f"[ECOSYSTEM GOAL] Onyx is building its own functional software ecosystem. "
        f"Currently: {len(tools)} tools built, {len(verified)} verified, {len(preferred)} preferred. "
        f"Long-term goal: replace all basic external utilities with self-built versions "
        f"that Onyx fully controls and can improve over time. "
        f"This demonstrates Onyx can create functional software, not just automate existing apps."
    )
