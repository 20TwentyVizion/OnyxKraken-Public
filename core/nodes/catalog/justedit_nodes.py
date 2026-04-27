"""JustEdit nodes — thin wrappers that launch/use/terminate JustEdit.

Each node calls the JustEditConnector which delegates to the existing
JustEditModule (apps/modules/justedit.py). JustEdit is a browser-based
video editor (Vite dev server on port 5173).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

from core.nodes.base_node import BaseNode, Input, NodeSchema, Output
from core.nodes.types import NodeType

logger = logging.getLogger(__name__)


def _je():
    """Get the JustEdit connector (lazy)."""
    from core.nodes.connector import get_connector
    return get_connector("justedit")


# ---------------------------------------------------------------------------
# Service lifecycle
# ---------------------------------------------------------------------------

class JustEditStart(BaseNode):
    """Start the JustEdit dev server."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="justedit.service.Start",
            display_name="Start JustEdit",
            category="justedit/service",
            description="Launch the JustEdit dev server (port 5173).",
            icon="\U0001f680",
            extension="justedit",
            inputs=[],
            outputs=[
                Output("status", NodeType.STRING, "Startup result"),
                Output("url", NodeType.STRING, "Editor URL"),
            ],
        )

    def execute(self, **kw) -> Tuple:
        conn = _je()
        result = conn.execute("justedit_start")
        msg = result.get("message", str(result))
        url = result.get("url", "http://localhost:5173")
        return (msg, url)


class JustEditStop(BaseNode):
    """Shut down the JustEdit dev server."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="justedit.service.Stop",
            display_name="Stop JustEdit",
            category="justedit/service",
            description="Gracefully shut down the JustEdit dev server.",
            icon="\u23f9\ufe0f",
            extension="justedit",
            is_output_node=True,
            inputs=[
                Input.optional_input("passthrough", NodeType.ANY),
            ],
            outputs=[
                Output("status", NodeType.STRING, "Shutdown result"),
            ],
        )

    def execute(self, passthrough: Any = None, **kw) -> Tuple:
        conn = _je()
        conn.shutdown()
        return ("JustEdit stopped",)


# ---------------------------------------------------------------------------
# Project creation
# ---------------------------------------------------------------------------

class CreateProject(BaseNode):
    """Create a new JustEdit video project (.justedit.json)."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="justedit.project.Create",
            display_name="Create Project",
            category="justedit/project",
            description="Create a new .justedit.json project file with tracks.",
            icon="\U0001f3ac",
            extension="justedit",
            inputs=[
                Input.required_input("name", NodeType.STRING, tooltip="Project name"),
                Input.optional_input("duration", NodeType.FLOAT, default=300.0,
                                     min_val=10.0, max_val=7200.0, step=10.0,
                                     tooltip="Project duration in seconds"),
            ],
            outputs=[
                Output("project", NodeType.JE_PROJECT, "Project data dict"),
            ],
        )

    def execute(self, name: str = "Onyx Project",
                duration: float = 300.0, **kw) -> Tuple:
        conn = _je()
        result = conn.execute("justedit_create_project", {
            "name": name,
            "duration": duration,
        })
        return (result,)


class ImportRecordings(BaseNode):
    """Import Onyx screen recordings into a JustEdit project."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="justedit.import.Recordings",
            display_name="Import Recordings",
            category="justedit/import",
            description="Import Onyx screen recordings from data/recordings/ into a project.",
            icon="\U0001f4f9",
            extension="justedit",
            inputs=[
                Input.optional_input("recording_dir", NodeType.FILE_PATH, default="",
                                     tooltip="Directory with recordings (default: data/recordings)"),
                Input.optional_input("project_name", NodeType.STRING, default="Onyx Recordings"),
            ],
            outputs=[
                Output("project", NodeType.JE_PROJECT, "Project with imported recordings"),
                Output("recording_count", NodeType.INT, "Number of recordings imported"),
            ],
        )

    def execute(self, recording_dir: str = "",
                project_name: str = "Onyx Recordings", **kw) -> Tuple:
        conn = _je()
        params = {"name": project_name}
        if recording_dir:
            params["recording_dir"] = recording_dir
        result = conn.execute("justedit_import_recordings", params)
        count = result.get("recording_count", result.get("count", 0))
        return (result, count)


class ImportAudio(BaseNode):
    """Import an audio file as a resource into a JustEdit project."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="justedit.import.Audio",
            display_name="Import Audio",
            category="justedit/import",
            description="Import an audio file (e.g. from EVERA) into a JustEdit project.",
            icon="\U0001f3b5",
            extension="justedit",
            inputs=[
                Input.required_input("audio_path", NodeType.AUDIO_FILE,
                                     tooltip="Path to audio file (WAV/MP3)"),
                Input.optional_input("project_name", NodeType.STRING, default=""),
                Input.optional_input("track_name", NodeType.STRING, default="Audio"),
            ],
            outputs=[
                Output("project", NodeType.JE_PROJECT, "Project with imported audio"),
            ],
        )

    def execute(self, audio_path: str = "", project_name: str = "",
                track_name: str = "Audio", **kw) -> Tuple:
        conn = _je()
        params = {
            "audio_path": audio_path,
            "track_name": track_name,
        }
        if project_name:
            params["name"] = project_name
        result = conn.execute("justedit_import_audio", params)
        return (result,)


class SaveProject(BaseNode):
    """Save a JustEdit project to a .justedit.json file."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="justedit.output.SaveProject",
            display_name="Save Project",
            category="justedit/output",
            description="Export the project as a .justedit.json file.",
            icon="\U0001f4be",
            extension="justedit",
            is_output_node=True,
            inputs=[
                Input.required_input("project", NodeType.JE_PROJECT),
                Input.optional_input("path", NodeType.FILE_PATH, default="",
                                     tooltip="Output path (default: auto-generated)"),
            ],
            outputs=[
                Output("path", NodeType.FILE_PATH, "Path to saved project file"),
            ],
        )

    def execute(self, project: Any = None, path: str = "", **kw) -> Tuple:
        conn = _je()
        params = {}
        if isinstance(project, dict):
            params["project"] = project
        if path:
            params["path"] = path
        result = conn.execute("justedit_save_project", params)
        saved_path = result.get("path", result.get("file_path", ""))
        return (saved_path,)


class OpenEditor(BaseNode):
    """Open the JustEdit editor in the browser."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="justedit.output.OpenEditor",
            display_name="Open Editor",
            category="justedit/output",
            description="Open JustEdit in the browser for manual editing.",
            icon="\U0001f310",
            extension="justedit",
            is_output_node=True,
            inputs=[
                Input.optional_input("project_path", NodeType.FILE_PATH, default="",
                                     tooltip="Project file to open"),
            ],
            outputs=[
                Output("url", NodeType.STRING, "Editor URL"),
            ],
        )

    def execute(self, project_path: str = "", **kw) -> Tuple:
        conn = _je()
        # Ensure the server is running
        conn.ensure_running()
        import webbrowser
        url = "http://localhost:5173"
        if project_path:
            url += f"?project={project_path}"
        webbrowser.open(url)
        return (url,)
