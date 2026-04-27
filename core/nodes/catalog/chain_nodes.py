"""Chain workflow nodes — visual nodes wrapping each chain workflow step.

These nodes map 1:1 to the step functions in core.chain_workflow, but expose
typed inputs/outputs so they can be wired together in the visual node canvas.

Each node delegates to the actual step function and unpacks the StepResult
data into typed output ports.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Tuple

from core.nodes.base_node import BaseNode, Input, NodeSchema, Output
from core.nodes.types import NodeType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Record Demo
# ---------------------------------------------------------------------------

class RecordDemoNode(BaseNode):
    """Screen-record Onyx performing demo tasks (Notepad + Browser)."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="chain.record.RecordDemo",
            display_name="Record Demo",
            category="chain/recording",
            description="Screen-record Onyx performing desktop tasks — opens Notepad, types, opens browser",
            icon="\U0001f3ac",
            extension="onyx",
            inputs=[
                Input.optional_input("demo_name", NodeType.STRING, default="chain_demo",
                                     tooltip="Base filename for the recording"),
                Input.optional_input("demo_duration", NodeType.FLOAT, default=30.0,
                                     tooltip="Fallback duration if pyautogui unavailable",
                                     min_val=5.0, max_val=300.0, step=5.0),
            ],
            outputs=[
                Output("recording_path", NodeType.VIDEO_FILE, "Path to the recorded MP4"),
                Output("duration", NodeType.FLOAT, "Recording duration in seconds"),
                Output("size_mb", NodeType.FLOAT, "File size in megabytes"),
            ],
        )

    def execute(self, demo_name: str = "chain_demo",
                demo_duration: float = 30.0, **kw) -> Tuple:
        from core.chain_workflow import _step_record_demo
        ctx = {"demo_name": demo_name, "demo_duration": demo_duration}
        result = _step_record_demo(ctx)
        if not result.success:
            raise RuntimeError(result.error)
        return (
            result.data.get("recording_path", ""),
            result.data.get("recording_duration", 0.0),
            result.data.get("recording_size_mb", 0.0),
        )


# ---------------------------------------------------------------------------
# Probe Duration
# ---------------------------------------------------------------------------

class ProbeDurationNode(BaseNode):
    """Analyze a video file's duration using ffprobe."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="chain.probe.ProbeDuration",
            display_name="Probe Duration",
            category="chain/analysis",
            description="Get exact video duration using ffprobe (falls back to file-size estimate)",
            icon="\U0001f50d",
            extension="onyx",
            inputs=[
                Input.required_input("recording_path", NodeType.VIDEO_FILE,
                                     tooltip="Path to the video file to analyze"),
            ],
            outputs=[
                Output("video_duration", NodeType.FLOAT, "Duration in seconds"),
            ],
        )

    def execute(self, recording_path: str = "", **kw) -> Tuple:
        from core.chain_workflow import _step_probe_duration
        ctx = {"recording_path": recording_path}
        result = _step_probe_duration(ctx)
        if not result.success:
            raise RuntimeError(result.error)
        return (result.data.get("video_duration", 60.0),)


# ---------------------------------------------------------------------------
# Generate Music
# ---------------------------------------------------------------------------

class GenerateMusicNode(BaseNode):
    """Generate background music matching the video using DJ Mode / EVERA."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="chain.music.GenerateMusic",
            display_name="Generate Music",
            category="chain/music",
            description="Generate background music via DJ Mode or EVERA to match video duration",
            icon="\U0001f3b5",
            extension="onyx",
            inputs=[
                Input.required_input("video_duration", NodeType.FLOAT,
                                     tooltip="Target duration in seconds"),
                Input.optional_input("music_genre", NodeType.STRING, default="lo-fi",
                                     tooltip="Music genre",
                                     options=["lo-fi", "house", "ambient", "synthwave",
                                              "jazz", "hip-hop", "classical", "electronic"]),
                Input.optional_input("music_quality", NodeType.STRING, default="quick_draft",
                                     tooltip="Generation quality",
                                     options=["quick_draft", "balanced", "high_quality"]),
            ],
            outputs=[
                Output("music_path", NodeType.AUDIO_FILE, "Path to the generated audio"),
                Output("music_genre", NodeType.STRING, "Genre used"),
                Output("track_count", NodeType.INT, "Number of tracks generated"),
            ],
        )

    def execute(self, video_duration: float = 60.0,
                music_genre: str = "lo-fi",
                music_quality: str = "quick_draft", **kw) -> Tuple:
        from core.chain_workflow import _step_generate_music
        ctx = {
            "video_duration": video_duration,
            "music_genre": music_genre,
            "music_quality": music_quality,
        }
        result = _step_generate_music(ctx)
        if not result.success:
            raise RuntimeError(result.error)
        return (
            result.data.get("music_path", ""),
            result.data.get("music_genre", music_genre),
            result.data.get("music_tracks_count", 1),
        )


# ---------------------------------------------------------------------------
# Assemble in JustEdit
# ---------------------------------------------------------------------------

class AssembleJustEditNode(BaseNode):
    """Combine video + music into a JustEdit project."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="chain.edit.AssembleJustEdit",
            display_name="Assemble (JustEdit)",
            category="chain/editing",
            description="Combine recorded video and music into a JustEdit project with title cards",
            icon="\U0001f3ac",
            extension="justedit",
            inputs=[
                Input.required_input("recording_path", NodeType.VIDEO_FILE,
                                     tooltip="Path to the source video"),
                Input.optional_input("music_path", NodeType.AUDIO_FILE,
                                     tooltip="Background music (optional)"),
                Input.optional_input("video_title", NodeType.STRING, default="OnyxKraken",
                                     tooltip="Title text for the video"),
            ],
            outputs=[
                Output("project_path", NodeType.FILE_PATH, "JustEdit project path"),
            ],
        )

    def execute(self, recording_path: str = "", music_path: str = "",
                video_title: str = "OnyxKraken", **kw) -> Tuple:
        from core.chain_workflow import _step_assemble_justedit
        ctx = {
            "recording_path": recording_path,
            "music_path": music_path,
            "video_title": video_title,
        }
        result = _step_assemble_justedit(ctx)
        if not result.success:
            raise RuntimeError(result.error)
        return (result.data.get("justedit_project", ""),)


# ---------------------------------------------------------------------------
# Export Video
# ---------------------------------------------------------------------------

class ExportVideoNode(BaseNode):
    """Render final MP4 by muxing video + audio with ffmpeg."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="chain.export.ExportVideo",
            display_name="Export MP4",
            category="chain/export",
            description="Mux video and audio into a final MP4 using ffmpeg",
            icon="\U0001f4e4",
            extension="onyx",
            is_output_node=True,
            inputs=[
                Input.required_input("recording_path", NodeType.VIDEO_FILE,
                                     tooltip="Source video file"),
                Input.optional_input("music_path", NodeType.AUDIO_FILE,
                                     tooltip="Background music (optional)"),
                Input.optional_input("video_duration", NodeType.FLOAT,
                                     tooltip="Video duration (for metadata)"),
            ],
            outputs=[
                Output("final_video", NodeType.VIDEO_FILE, "Path to the exported MP4"),
                Output("size_mb", NodeType.FLOAT, "File size in MB"),
            ],
        )

    def execute(self, recording_path: str = "", music_path: str = "",
                video_duration: float = 0.0, **kw) -> Tuple:
        from core.chain_workflow import _step_export_video
        ctx = {
            "recording_path": recording_path,
            "music_path": music_path,
            "video_duration": video_duration,
        }
        result = _step_export_video(ctx)
        if not result.success:
            raise RuntimeError(result.error)
        return (
            result.data.get("final_video", ""),
            result.data.get("final_size_mb", 0.0),
        )


# ---------------------------------------------------------------------------
# Collect Recordings
# ---------------------------------------------------------------------------

class CollectRecordingsNode(BaseNode):
    """Scan the recordings directory for existing MP4 files."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="chain.record.CollectRecordings",
            display_name="Collect Recordings",
            category="chain/recording",
            description="Find existing screen recordings in data/recordings/",
            icon="\U0001f4c1",
            extension="onyx",
            inputs=[
                Input.optional_input("directory", NodeType.FILE_PATH,
                                     default="data/recordings",
                                     tooltip="Directory to scan"),
                Input.optional_input("max_files", NodeType.INT, default=10,
                                     tooltip="Maximum files to collect",
                                     min_val=1, max_val=100),
            ],
            outputs=[
                Output("recording_path", NodeType.VIDEO_FILE, "Most recent recording"),
                Output("all_paths", NodeType.ANY, "List of all recording paths"),
                Output("count", NodeType.INT, "Number of recordings found"),
            ],
        )

    def execute(self, directory: str = "data/recordings",
                max_files: int = 10, **kw) -> Tuple:
        from core.chain_workflow import _step_collect_recordings
        ctx = {"recordings_dir": directory, "max_recordings": max_files}
        result = _step_collect_recordings(ctx)
        if not result.success:
            raise RuntimeError(result.error)
        return (
            result.data.get("recording_path", ""),
            result.data.get("recording_paths", []),
            result.data.get("recording_count", 0),
        )


# ---------------------------------------------------------------------------
# Blender Build & Record
# ---------------------------------------------------------------------------

class BlenderBuildRecordNode(BaseNode):
    """Build a 3D scene in Blender and record the process."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="chain.blender.BuildAndRecord",
            display_name="Blender Build + Record",
            category="chain/3d",
            description="Launch Blender, build a house demo, and screen-record the process",
            icon="\U0001f3d7",
            extension="onyx",
            inputs=[
                Input.optional_input("build_type", NodeType.STRING, default="house",
                                     tooltip="Type of Blender build",
                                     options=["house", "office", "cabin", "tower"]),
                Input.optional_input("demo_name", NodeType.STRING, default="blender_showcase",
                                     tooltip="Recording filename"),
            ],
            outputs=[
                Output("recording_path", NodeType.VIDEO_FILE, "Path to recorded video"),
                Output("duration", NodeType.FLOAT, "Recording duration"),
            ],
        )

    def execute(self, build_type: str = "house",
                demo_name: str = "blender_showcase", **kw) -> Tuple:
        from core.chain_workflow import _step_blender_build_and_record
        ctx = {"build_type": build_type, "demo_name": demo_name}
        result = _step_blender_build_and_record(ctx)
        if not result.success:
            raise RuntimeError(result.error)
        return (
            result.data.get("recording_path", ""),
            result.data.get("recording_duration", 0.0),
        )


# ---------------------------------------------------------------------------
# Service Config nodes (provide settings to downstream nodes)
# ---------------------------------------------------------------------------

class MusicSettingsNode(BaseNode):
    """Configure music generation settings."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="chain.config.MusicSettings",
            display_name="Music Settings",
            category="chain/config",
            description="Configure genre, quality, and other music generation parameters",
            icon="\U0001f3b6",
            extension="onyx",
            inputs=[
                Input.optional_input("genre", NodeType.STRING, default="lo-fi",
                                     options=["lo-fi", "house", "ambient", "synthwave",
                                              "jazz", "hip-hop", "classical", "electronic"]),
                Input.optional_input("quality", NodeType.STRING, default="quick_draft",
                                     options=["quick_draft", "balanced", "high_quality"]),
            ],
            outputs=[
                Output("genre", NodeType.STRING, "Selected genre"),
                Output("quality", NodeType.STRING, "Selected quality"),
            ],
        )

    def execute(self, genre: str = "lo-fi", quality: str = "quick_draft", **kw) -> Tuple:
        return (genre, quality)


class VideoSettingsNode(BaseNode):
    """Configure video title and export settings."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="chain.config.VideoSettings",
            display_name="Video Settings",
            category="chain/config",
            description="Configure video title, demo name, and other parameters",
            icon="\U0001f4f9",
            extension="onyx",
            inputs=[
                Input.optional_input("title", NodeType.STRING, default="OnyxKraken"),
                Input.optional_input("demo_name", NodeType.STRING, default="chain_demo"),
            ],
            outputs=[
                Output("title", NodeType.STRING, "Video title text"),
                Output("demo_name", NodeType.STRING, "Demo recording name"),
            ],
        )

    def execute(self, title: str = "OnyxKraken",
                demo_name: str = "chain_demo", **kw) -> Tuple:
        return (title, demo_name)
