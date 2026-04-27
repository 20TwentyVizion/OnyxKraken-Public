"""SmartEngine nodes — thin wrappers that launch/use/terminate SmartEngine.

Each node calls the SmartEngineConnector which delegates to the existing
SmartEngineModule (apps/modules/smartengine.py). SmartEngine is a FastAPI
server started on first use and shut down when done.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from core.nodes.base_node import BaseNode, Input, NodeSchema, Output
from core.nodes.types import NodeType

logger = logging.getLogger(__name__)


def _se():
    """Get the SmartEngine connector (lazy)."""
    from core.nodes.connector import get_connector
    return get_connector("smartengine")


# ---------------------------------------------------------------------------
# Service lifecycle
# ---------------------------------------------------------------------------

class SmartEngineStart(BaseNode):
    """Start the SmartEngine FastAPI server."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="smartengine.service.Start",
            display_name="Start SmartEngine",
            category="smartengine/service",
            description="Launch the SmartEngine writing server (port 8000).",
            icon="\U0001f680",
            extension="smartengine",
            inputs=[],
            outputs=[
                Output("status", NodeType.STRING, "Startup result"),
            ],
        )

    def execute(self, **kw) -> Tuple:
        conn = _se()
        result = conn.execute("smartengine_start")
        return (result.get("message", str(result)),)


class SmartEngineStop(BaseNode):
    """Shut down the SmartEngine server."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="smartengine.service.Stop",
            display_name="Stop SmartEngine",
            category="smartengine/service",
            description="Gracefully shut down the SmartEngine server.",
            icon="\u23f9\ufe0f",
            extension="smartengine",
            is_output_node=True,
            inputs=[
                Input.optional_input("passthrough", NodeType.ANY),
            ],
            outputs=[
                Output("status", NodeType.STRING, "Shutdown result"),
            ],
        )

    def execute(self, passthrough: Any = None, **kw) -> Tuple:
        conn = _se()
        conn.shutdown()
        return ("SmartEngine stopped",)


# ---------------------------------------------------------------------------
# Project management
# ---------------------------------------------------------------------------

class CreateProject(BaseNode):
    """Create a new SmartEngine writing project."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="smartengine.project.Create",
            display_name="Create Project",
            category="smartengine/project",
            description="Create a new writing project in SmartEngine.",
            icon="\U0001f4d6",
            extension="smartengine",
            inputs=[
                Input.required_input("name", NodeType.STRING, tooltip="Project name"),
            ],
            outputs=[
                Output("project", NodeType.SE_PROJECT, "Project data dict"),
                Output("project_id", NodeType.STRING, "Project ID"),
            ],
        )

    def execute(self, name: str = "", **kw) -> Tuple:
        conn = _se()
        result = conn.execute("smartengine_create_project", {"name": name})
        pid = result.get("project_id", result.get("id", ""))
        return (result, str(pid))


class ListProjects(BaseNode):
    """List all SmartEngine writing projects."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="smartengine.project.List",
            display_name="List Projects",
            category="smartengine/project",
            description="Returns all writing projects.",
            icon="\U0001f4da",
            extension="smartengine",
            inputs=[],
            outputs=[
                Output("projects", NodeType.ANY, "List of project dicts"),
                Output("count", NodeType.INT, "Number of projects"),
            ],
        )

    def execute(self, **kw) -> Tuple:
        from core.nodes.connector import get_bus
        bus = get_bus()
        cached = bus.get("smartengine", "list_projects")
        if cached is not None:
            return (cached, len(cached))
        conn = _se()
        result = conn.execute("smartengine_list_projects")
        projects = result if isinstance(result, list) else result.get("projects", [])
        bus.publish("smartengine", "list_projects", projects)
        return (projects, len(projects))


# ---------------------------------------------------------------------------
# Discovery (story DNA interview)
# ---------------------------------------------------------------------------

class Discover(BaseNode):
    """Run story discovery — extract story DNA from an idea."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="smartengine.discover.Discover",
            display_name="Discover Story",
            category="smartengine/discover",
            description="Send a message to the story discovery interview. "
                        "Extracts genre, theme, characters, world from your idea.",
            icon="\U0001f50d",
            extension="smartengine",
            inputs=[
                Input.required_input("project_id", NodeType.STRING),
                Input.required_input("message", NodeType.STRING, multiline=True,
                                     tooltip="Your story idea or answer to discovery question"),
            ],
            outputs=[
                Output("response", NodeType.STRING, "Discovery response text"),
                Output("result", NodeType.ANY, "Full discovery result dict"),
            ],
        )

    def execute(self, project_id: str = "", message: str = "", **kw) -> Tuple:
        conn = _se()
        result = conn.execute("smartengine_discover", {
            "project_id": project_id,
            "message": message,
        })
        response = result.get("response", result.get("message", str(result)))
        return (response, result)


# ---------------------------------------------------------------------------
# Architecture (generate structure)
# ---------------------------------------------------------------------------

class GenerateStructure(BaseNode):
    """Generate story architecture (world bible, characters, plot)."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="smartengine.architect.Generate",
            display_name="Generate Structure",
            category="smartengine/architect",
            description="Build story structure from discovery results: "
                        "world bible, character profiles, chapter outline.",
            icon="\U0001f3d7\ufe0f",
            extension="smartengine",
            inputs=[
                Input.required_input("project_id", NodeType.STRING),
                Input.optional_input("discovery_summary", NodeType.STRING, default="",
                                     multiline=True),
            ],
            outputs=[
                Output("structure", NodeType.ANY, "Generated structure dict"),
            ],
        )

    def execute(self, project_id: str = "",
                discovery_summary: str = "", **kw) -> Tuple:
        conn = _se()
        result = conn.execute("smartengine_generate_structure", {
            "project_id": project_id,
            "discovery_summary": discovery_summary,
        })
        return (result,)


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

class WriteScene(BaseNode):
    """Write a single scene."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="smartengine.write.Scene",
            display_name="Write Scene",
            category="smartengine/write",
            description="Generate prose for a specific scene.",
            icon="\u270d\ufe0f",
            extension="smartengine",
            inputs=[
                Input.required_input("project_id", NodeType.STRING),
                Input.required_input("scene_id", NodeType.STRING),
                Input.optional_input("granularity", NodeType.STRING, default="page",
                                     options=["paragraph", "page", "chapter"]),
                Input.optional_input("user_notes", NodeType.STRING, default="", multiline=True),
            ],
            outputs=[
                Output("scene_text", NodeType.SCENE_TEXT, "Written scene text"),
                Output("result", NodeType.ANY, "Full write result dict"),
            ],
        )

    def execute(self, project_id: str = "", scene_id: str = "",
                granularity: str = "page", user_notes: str = "", **kw) -> Tuple:
        conn = _se()
        result = conn.execute("smartengine_write_scene", {
            "project_id": project_id,
            "scene_id": scene_id,
            "granularity": granularity,
            "user_notes": user_notes,
        })
        text = result.get("text", result.get("content", str(result)))
        return (text, result)


class WriteChapter(BaseNode):
    """Write an entire chapter."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="smartengine.write.Chapter",
            display_name="Write Chapter",
            category="smartengine/write",
            description="Generate prose for an entire chapter (all scenes).",
            icon="\U0001f4d1",
            extension="smartengine",
            inputs=[
                Input.required_input("project_id", NodeType.STRING),
                Input.required_input("chapter_number", NodeType.INT),
                Input.optional_input("granularity", NodeType.STRING, default="page",
                                     options=["paragraph", "page", "chapter"]),
                Input.optional_input("user_notes", NodeType.STRING, default="", multiline=True),
            ],
            outputs=[
                Output("chapter_text", NodeType.TEXT_DOCUMENT, "Written chapter text"),
                Output("result", NodeType.ANY, "Full write result dict"),
            ],
        )

    def execute(self, project_id: str = "", chapter_number: int = 1,
                granularity: str = "page", user_notes: str = "", **kw) -> Tuple:
        conn = _se()
        result = conn.execute("smartengine_write_chapter", {
            "project_id": project_id,
            "chapter_number": chapter_number,
            "granularity": granularity,
            "user_notes": user_notes,
        })
        text = result.get("text", result.get("content", str(result)))
        return (text, result)


class WriteBook(BaseNode):
    """Write the entire book."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="smartengine.write.Book",
            display_name="Write Book",
            category="smartengine/write",
            description="Generate the entire book from structure.",
            icon="\U0001f4d5",
            extension="smartengine",
            inputs=[
                Input.required_input("project_id", NodeType.STRING),
                Input.optional_input("granularity", NodeType.STRING, default="page",
                                     options=["paragraph", "page", "chapter"]),
                Input.optional_input("user_notes", NodeType.STRING, default="", multiline=True),
            ],
            outputs=[
                Output("manuscript", NodeType.MANUSCRIPT, "Full manuscript text"),
                Output("result", NodeType.ANY, "Full write result dict"),
            ],
        )

    def execute(self, project_id: str = "", granularity: str = "page",
                user_notes: str = "", **kw) -> Tuple:
        conn = _se()
        self.on_progress(0, 1, "Writing book...")
        result = conn.execute("smartengine_write_book", {
            "project_id": project_id,
            "granularity": granularity,
            "user_notes": user_notes,
        })
        self.on_progress(1, 1, "Book complete")
        text = result.get("text", result.get("content", str(result)))
        return (text, result)


# ---------------------------------------------------------------------------
# Critique
# ---------------------------------------------------------------------------

class CritiqueScene(BaseNode):
    """AI critique of a written scene."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="smartengine.critique.Scene",
            display_name="Critique Scene",
            category="smartengine/critique",
            description="Run AI critique on a specific scene.",
            icon="\U0001f9d0",
            extension="smartengine",
            inputs=[
                Input.required_input("project_id", NodeType.STRING),
                Input.required_input("scene_id", NodeType.STRING),
            ],
            outputs=[
                Output("critique", NodeType.STRING, "Critique feedback text"),
                Output("result", NodeType.ANY, "Full critique result dict"),
            ],
        )

    def execute(self, project_id: str = "", scene_id: str = "", **kw) -> Tuple:
        conn = _se()
        result = conn.execute("smartengine_critique", {
            "project_id": project_id,
            "scene_id": scene_id,
        })
        critique = result.get("critique", result.get("feedback", str(result)))
        return (critique, result)


# ---------------------------------------------------------------------------
# Manuscript output
# ---------------------------------------------------------------------------

class CompileManuscript(BaseNode):
    """Compile the full manuscript from all written scenes."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="smartengine.output.Manuscript",
            display_name="Compile Manuscript",
            category="smartengine/output",
            description="Assemble all written content into a final manuscript.",
            icon="\U0001f4dc",
            extension="smartengine",
            is_output_node=True,
            inputs=[
                Input.required_input("project_id", NodeType.STRING),
            ],
            outputs=[
                Output("manuscript", NodeType.MANUSCRIPT, "Full manuscript text"),
                Output("result", NodeType.ANY, "Manuscript result dict"),
            ],
        )

    def execute(self, project_id: str = "", **kw) -> Tuple:
        conn = _se()
        result = conn.execute("smartengine_manuscript", {
            "project_id": project_id,
        })
        text = result.get("manuscript", result.get("text", str(result)))
        return (text, result)


# ---------------------------------------------------------------------------
# Image generation (uses SmartEngine's multi-backend image_gen.py)
# ---------------------------------------------------------------------------

class GenerateImage(BaseNode):
    """Generate an image from a text prompt via SmartEngine's image backends."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="smartengine.image.Generate",
            display_name="Generate Image",
            category="smartengine/image",
            description="Generate an image from a text prompt. "
                        "Backends: pollinations (free), flux_pro, openai_gpt_image.",
            icon="\U0001f3a8",
            extension="smartengine",
            inputs=[
                Input.required_input("prompt", NodeType.STRING, multiline=True,
                                     tooltip="Text description of the image"),
                Input.optional_input("width", NodeType.INT, default=1024,
                                     min_val=256, max_val=2048),
                Input.optional_input("height", NodeType.INT, default=1024,
                                     min_val=256, max_val=2048),
                Input.optional_input("negative_prompt", NodeType.STRING, default="",
                                     tooltip="Things to avoid in the image"),
                Input.optional_input("output_path", NodeType.FILE_PATH, default="",
                                     tooltip="Where to save (auto if empty)"),
                Input.optional_input("backend", NodeType.STRING, default="pollinations",
                                     options=["pollinations", "flux_pro",
                                              "openai_gpt_image", "openai_mini"]),
                Input.optional_input("seed", NodeType.INT, default=0),
            ],
            outputs=[
                Output("image_path", NodeType.FILE_PATH, "Path to generated image"),
                Output("result", NodeType.ANY, "Full result dict"),
            ],
        )

    def execute(self, prompt: str = "", width: int = 1024, height: int = 1024,
                negative_prompt: str = "", output_path: str = "",
                backend: str = "pollinations", seed: int = 0, **kw) -> Tuple:
        conn = _se()
        if not output_path:
            import os, hashlib
            from pathlib import Path
            covers_dir = Path(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))) / ".." / "data" / "images"
            covers_dir = covers_dir.resolve()
            covers_dir.mkdir(parents=True, exist_ok=True)
            h = hashlib.md5(f"{prompt}{seed}".encode()).hexdigest()[:8]
            output_path = str(covers_dir / f"img_{h}.png")

        self.on_progress(0, 1, f"Generating image [{backend}]...")
        result = conn.generate_image(
            prompt=prompt,
            output_path=output_path,
            width=width, height=height,
            negative_prompt=negative_prompt,
            seed=seed if seed else None,
            backend=backend,
        )
        self.on_progress(1, 1, "Image generated")
        return (result.get("path", output_path), result)


class GenerateAlbumCover(BaseNode):
    """Generate a square album cover with AI background + professional text overlay."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="smartengine.image.AlbumCover",
            display_name="Generate Album Cover",
            category="smartengine/image",
            description="Full album cover pipeline: AI-generated background image "
                        "(1024x1024 square) + professional title/artist text overlay "
                        "using SmartEngine's typography system (10 style templates). "
                        "Background is blurred under text zones for readability.",
            icon="\U0001f4bf",
            extension="smartengine",
            inputs=[
                Input.required_input("title", NodeType.STRING,
                                     tooltip="Album or track title"),
                Input.optional_input("artist", NodeType.STRING, default="",
                                     tooltip="Artist name"),
                Input.optional_input("genre", NodeType.STRING, default="jazz",
                                     tooltip="Genre for visual style"),
                Input.optional_input("output_path", NodeType.FILE_PATH, default="",
                                     tooltip="Where to save (auto if empty)"),
                Input.optional_input("backend", NodeType.STRING, default="pollinations",
                                     options=["pollinations", "flux_pro",
                                              "openai_gpt_image", "openai_mini"]),
                Input.optional_input("seed", NodeType.INT, default=0),
            ],
            outputs=[
                Output("cover_path", NodeType.FILE_PATH, "Path to album cover PNG"),
                Output("result", NodeType.ANY, "Full result dict with dimensions"),
            ],
        )

    def execute(self, title: str = "", artist: str = "", genre: str = "jazz",
                output_path: str = "", backend: str = "pollinations",
                seed: int = 0, **kw) -> Tuple:
        conn = _se()
        self.on_progress(0, 1, f"Generating {genre} album cover...")
        result = conn.generate_album_cover(
            title=title,
            artist=artist,
            genre=genre,
            output_path=output_path,
            seed=seed if seed else None,
            backend=backend,
        )
        self.on_progress(1, 1, "Album cover complete")
        return (result.get("path", output_path), result)
