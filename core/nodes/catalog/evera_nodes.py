"""EVERA nodes — thin wrappers that launch/use/terminate EVERA via connector.

Each node calls the EveraConnector which delegates to the existing
EveraModule (apps/modules/evera.py). EVERA is started on first use
and can be shut down when the workflow completes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from core.nodes.base_node import BaseNode, Input, NodeSchema, Output
from core.nodes.types import NodeType

logger = logging.getLogger(__name__)


def _evera():
    """Get the EVERA connector (lazy)."""
    from core.nodes.connector import get_connector
    return get_connector("evera")


# ---------------------------------------------------------------------------
# Service lifecycle
# ---------------------------------------------------------------------------

class EveraStart(BaseNode):
    """Start EVERA services (Ollama, ACE-Step)."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="evera.service.Start",
            display_name="Start EVERA",
            category="evera/service",
            description="Launch EVERA services. Auto-starts Ollama and ACE-Step.",
            icon="\U0001f680",
            extension="evera",
            inputs=[],
            outputs=[
                Output("status", NodeType.STRING, "Startup result message"),
            ],
        )

    def execute(self, **kw) -> Tuple:
        conn = _evera()
        result = conn.execute("evera_start")
        msg = result.get("message", str(result))
        logger.info("EVERA start: %s", msg)
        return (msg,)


class EveraStop(BaseNode):
    """Shut down EVERA services."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="evera.service.Stop",
            display_name="Stop EVERA",
            category="evera/service",
            description="Gracefully shut down EVERA services.",
            icon="\u23f9\ufe0f",
            extension="evera",
            is_output_node=True,
            inputs=[
                Input.optional_input("passthrough", NodeType.ANY,
                                     tooltip="Chain after final EVERA node"),
            ],
            outputs=[
                Output("status", NodeType.STRING, "Shutdown result"),
            ],
        )

    def execute(self, passthrough: Any = None, **kw) -> Tuple:
        conn = _evera()
        conn.shutdown()
        return ("EVERA stopped",)


class EveraStatus(BaseNode):
    """Check EVERA system health and catalog stats."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="evera.service.Status",
            display_name="EVERA Status",
            category="evera/service",
            description="Returns health info: Ollama, ACE-Step, catalog stats.",
            icon="\U0001f4ca",
            extension="evera",
            inputs=[],
            outputs=[
                Output("status", NodeType.ANY, "Health status dict"),
                Output("running", NodeType.BOOL, "True if EVERA is healthy"),
            ],
        )

    def execute(self, **kw) -> Tuple:
        conn = _evera()
        health = conn.health()
        running = health.get("running", False) or health.get("ollama", False)
        return (health, running)


# ---------------------------------------------------------------------------
# Artist management
# ---------------------------------------------------------------------------

class CreateArtist(BaseNode):
    """Create a new EVERA artist profile."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="evera.artist.CreateArtist",
            display_name="Create Artist",
            category="evera/artist",
            description="Create a new artist with name, genre, mood, and vocal style.",
            icon="\U0001f3a4",
            extension="evera",
            inputs=[
                Input.required_input("name", NodeType.STRING, tooltip="Artist name"),
                Input.optional_input("genre", NodeType.STRING, default="pop"),
                Input.optional_input("mood", NodeType.STRING, default="energetic"),
                Input.optional_input("vocal_style", NodeType.STRING, default="",
                                     tooltip="Vocal description for ACE-Step"),
                Input.optional_input("description", NodeType.STRING, default=""),
            ],
            outputs=[
                Output("artist", NodeType.ARTIST, "Created artist data dict"),
                Output("artist_id", NodeType.STRING, "Artist ID"),
            ],
        )

    def execute(self, name: str = "", genre: str = "pop",
                mood: str = "energetic", vocal_style: str = "",
                description: str = "", **kw) -> Tuple:
        conn = _evera()
        result = conn.execute("evera_create_artist", {
            "name": name,
            "genres": [genre] if genre else [],
            "moods": [mood] if mood else [],
            "voice_prompt": vocal_style,
            "description": description,
        })
        artist_id = result.get("artist_id", result.get("id", ""))
        return (result, str(artist_id))


class ListArtists(BaseNode):
    """List all artists in the EVERA catalog."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="evera.artist.ListArtists",
            display_name="List Artists",
            category="evera/artist",
            description="Returns all artists in the EVERA catalog.",
            icon="\U0001f465",
            extension="evera",
            inputs=[],
            outputs=[
                Output("artists", NodeType.ANY, "List of artist dicts"),
                Output("count", NodeType.INT, "Number of artists"),
            ],
        )

    def execute(self, **kw) -> Tuple:
        from core.nodes.connector import get_bus
        bus = get_bus()
        cached = bus.get("evera", "list_artists")
        if cached is not None:
            return (cached, len(cached))
        conn = _evera()
        result = conn.execute("evera_list_artists")
        artists = result.get("artists", [])
        bus.publish("evera", "list_artists", artists)
        return (artists, len(artists))


# ---------------------------------------------------------------------------
# Track generation
# ---------------------------------------------------------------------------

class GenerateTrack(BaseNode):
    """Generate a music track via EVERA (concept -> lyrics -> audio)."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="evera.generate.Track",
            display_name="Generate Track",
            category="evera/generate",
            description="Full pipeline: concept, lyrics, VRAM switch, ACE-Step generation, quality scoring.",
            icon="\U0001f3b5",
            extension="evera",
            inputs=[
                Input.required_input("genre", NodeType.STRING,
                                     tooltip="pop, rock, jazz, electronic, hip_hop, etc."),
                Input.optional_input("mood", NodeType.STRING, default=""),
                Input.optional_input("theme", NodeType.STRING, default="", multiline=True),
                Input.optional_input("duration", NodeType.INT, default=240,
                                     min_val=30, max_val=300, step=30),
                Input.optional_input("instrumental", NodeType.BOOL, default=False),
                Input.optional_input("quality_profile", NodeType.STRING, default="standard",
                                     options=["quick_draft", "draft", "standard",
                                              "radio_quality", "pro"]),
                Input.optional_input("artist_id", NodeType.STRING, default="",
                                     tooltip="Generate as a specific artist"),
            ],
            outputs=[
                Output("track_info", NodeType.TRACK_INFO, "Track metadata dict"),
                Output("audio_path", NodeType.AUDIO_FILE, "Path to generated WAV"),
                Output("quality_score", NodeType.FLOAT, "Quality score 0-10"),
            ],
        )

    def execute(self, genre: str = "pop", mood: str = "", theme: str = "",
                duration: int = 240, instrumental: bool = False,
                quality_profile: str = "standard", artist_id: str = "",
                **kw) -> Tuple:
        conn = _evera()
        params = {
            "genre": genre,
            "duration": duration,
            "quality_profile": quality_profile,
        }
        if mood:
            params["mood"] = mood
        if theme:
            params["theme"] = theme
        if instrumental:
            params["instrumental"] = True
        if artist_id:
            params["artist_id"] = artist_id

        self.on_progress(0, 1, f"Generating {genre} track...")
        result = conn.execute("evera_generate", params)
        self.on_progress(1, 1, "Track generated")

        audio_path = result.get("path", result.get("audio_path", ""))
        score = result.get("quality_score", result.get("score", 0.0))
        return (result, audio_path, float(score))


class GenerateAlbum(BaseNode):
    """Generate a full album for an artist."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="evera.generate.Album",
            display_name="Generate Album",
            category="evera/generate",
            description="Full album pipeline: concept, per-track lyrics, generation, assembly.",
            icon="\U0001f4bf",
            extension="evera",
            inputs=[
                Input.required_input("artist_id", NodeType.STRING),
                Input.optional_input("num_tracks", NodeType.INT, default=9,
                                     min_val=3, max_val=18, step=1),
                Input.optional_input("theme", NodeType.STRING, default="", multiline=True),
                Input.optional_input("quality_profile", NodeType.STRING, default="standard",
                                     options=["quick_draft", "draft", "standard",
                                              "radio_quality", "pro"]),
            ],
            outputs=[
                Output("album_info", NodeType.ANY, "Album metadata dict"),
                Output("album_dir", NodeType.FILE_PATH, "Path to album folder"),
            ],
        )

    def execute(self, artist_id: str = "", num_tracks: int = 9,
                theme: str = "", quality_profile: str = "standard", **kw) -> Tuple:
        conn = _evera()
        params = {
            "artist_id": artist_id,
            "num_tracks": num_tracks,
            "quality_profile": quality_profile,
        }
        if theme:
            params["theme"] = theme

        self.on_progress(0, 1, f"Generating {num_tracks}-track album...")
        result = conn.execute("evera_album", params)
        self.on_progress(1, 1, "Album complete")

        album_dir = result.get("album_dir", result.get("output_dir", ""))
        return (result, album_dir)


# ---------------------------------------------------------------------------
# Catalog queries
# ---------------------------------------------------------------------------

class ListTracks(BaseNode):
    """List tracks in the EVERA catalog."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="evera.catalog.ListTracks",
            display_name="List Tracks",
            category="evera/catalog",
            description="Query the EVERA track catalog with optional filters.",
            icon="\U0001f4c0",
            extension="evera",
            inputs=[
                Input.optional_input("genre", NodeType.STRING, default=""),
                Input.optional_input("mood", NodeType.STRING, default=""),
                Input.optional_input("min_quality", NodeType.FLOAT, default=0.0),
                Input.optional_input("limit", NodeType.INT, default=20),
            ],
            outputs=[
                Output("tracks", NodeType.ANY, "List of track dicts"),
                Output("count", NodeType.INT, "Number of tracks found"),
            ],
        )

    def execute(self, genre: str = "", mood: str = "",
                min_quality: float = 0.0, limit: int = 20, **kw) -> Tuple:
        from core.nodes.connector import get_bus
        bus = get_bus()
        cache_key = f"list_tracks:{genre}:{mood}:{min_quality}:{limit}"
        cached = bus.get("evera", cache_key)
        if cached is not None:
            return (cached, len(cached))
        conn = _evera()
        params = {"limit": limit}
        if genre:
            params["genre"] = genre
        if mood:
            params["mood"] = mood
        if min_quality > 0:
            params["min_quality"] = min_quality
        result = conn.execute("evera_list_tracks", params)
        tracks = result.get("tracks", [])
        bus.publish("evera", cache_key, tracks)
        return (tracks, len(tracks))


class DownloadTrack(BaseNode):
    """Download/copy a generated track to a local folder."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="evera.catalog.DownloadTrack",
            display_name="Download Track",
            category="evera/catalog",
            description="Copy a track from EVERA catalog to a local destination.",
            icon="\u2b07\ufe0f",
            extension="evera",
            is_output_node=True,
            inputs=[
                Input.required_input("track_id", NodeType.STRING),
                Input.optional_input("dest", NodeType.FILE_PATH, default=""),
            ],
            outputs=[
                Output("path", NodeType.AUDIO_FILE, "Path to downloaded file"),
            ],
        )

    def execute(self, track_id: str = "", dest: str = "", **kw) -> Tuple:
        conn = _evera()
        params = {"track_id": track_id}
        if dest:
            params["dest"] = dest
        result = conn.execute("evera_download", params)
        path = result.get("path", result.get("dest_path", ""))
        return (path,)


class ListGenres(BaseNode):
    """List all available EVERA genres."""

    @classmethod
    def define_schema(cls) -> NodeSchema:
        return NodeSchema(
            node_id="evera.catalog.ListGenres",
            display_name="List Genres",
            category="evera/catalog",
            description="Returns all 20 available genres with details.",
            icon="\U0001f3b6",
            extension="evera",
            inputs=[],
            outputs=[
                Output("genres", NodeType.ANY, "List of genre dicts"),
            ],
        )

    def execute(self, **kw) -> Tuple:
        from core.nodes.connector import get_bus
        bus = get_bus()
        cached = bus.get("evera", "genres")
        if cached is not None:
            return (cached,)
        conn = _evera()
        result = conn.execute("evera_genres")
        genres = result.get("genres", result)
        bus.publish("evera", "genres", genres)
        return (genres,)
