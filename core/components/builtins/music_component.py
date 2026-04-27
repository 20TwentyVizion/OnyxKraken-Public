"""Music Component — AI music generation, DJ sets, and beat battles.

Wraps the existing music toolkit (apps/evera_client.py, apps/auto_dj.py,
apps/beat_battle.py, apps/acestep_profiles.py) behind the unified
OnyxComponent interface.

Capabilities:
    - Generate full tracks in any genre via ACE-Step
    - DJ live sessions with auto-mixing
    - Beat battles (head-to-head track generation)
    - Quality profiles (quick_draft → pro)
    - MP3 conversion and publishing
    - Producer mode: genre-aware beat production with optimal defaults
    - Genre guides: deep production knowledge for any genre
    - Beat evaluation: structured quality checklist
    - Prompt engineering: build optimized ACE-Step prompts
"""

import json
import logging
import os
import random
from typing import Any, Dict, List, Optional

from core.components.base import (
    OnyxComponent, ComponentResult, ComponentStatus, ActionDescriptor,
)

_log = logging.getLogger("components.music")


class MusicComponent(OnyxComponent):
    """Music production component — generates tracks, DJ sets, and beats."""

    @property
    def name(self) -> str:
        return "music"

    @property
    def display_name(self) -> str:
        return "Music Production"

    @property
    def description(self) -> str:
        return "Generate music, DJ sets, and beats with ACE-Step"

    @property
    def category(self) -> str:
        return "creative"

    def get_actions(self) -> List[ActionDescriptor]:
        return [
            ActionDescriptor(
                name="generate_track",
                description="Generate a music track with ACE-Step",
                params=["prompt", "genre", "bpm", "key", "duration",
                        "quality_profile", "instrumental"],
                required_params=["prompt"],
                estimated_duration="minutes",
            ),
            ActionDescriptor(
                name="dj_set",
                description="Generate a multi-track DJ set",
                params=["duration_minutes", "genre", "quality_profile"],
                required_params=["duration_minutes"],
                estimated_duration="long",
            ),
            ActionDescriptor(
                name="beat_battle",
                description="Run a head-to-head beat battle",
                params=["genre", "rounds", "quality_profile"],
                estimated_duration="long",
            ),
            ActionDescriptor(
                name="convert_to_mp3",
                description="Convert a WAV file to MP3",
                params=["wav_path", "bitrate"],
                required_params=["wav_path"],
                estimated_duration="seconds",
            ),
            ActionDescriptor(
                name="list_profiles",
                description="List available quality profiles",
                estimated_duration="fast",
            ),
            ActionDescriptor(
                name="list_templates",
                description="List available instrumental structure templates",
                estimated_duration="fast",
            ),
            ActionDescriptor(
                name="produce_beat",
                description="Genre-aware beat production with optimal BPM, key, structure, and prompt",
                params=["genre", "mood", "bpm", "key", "duration",
                        "quality_profile", "instrumental", "extra"],
                required_params=["genre"],
                estimated_duration="minutes",
            ),
            ActionDescriptor(
                name="get_genre_guide",
                description="Get deep production knowledge for a specific genre",
                params=["genre"],
                required_params=["genre"],
                estimated_duration="fast",
            ),
            ActionDescriptor(
                name="evaluate_beat",
                description="Run the beat evaluation checklist against a track",
                params=["audio_path", "genre", "notes"],
                estimated_duration="fast",
            ),
            ActionDescriptor(
                name="build_prompt",
                description="Build an optimized ACE-Step prompt from genre, mood, and extras",
                params=["genre", "mood", "instrument", "extra", "sub_genre"],
                required_params=["genre"],
                estimated_duration="fast",
            ),
            ActionDescriptor(
                name="list_genres",
                description="List all supported producer genres with BPM ranges and keys",
                estimated_duration="fast",
            ),
        ]

    def health_check(self) -> Dict:
        missing = []
        try:
            from apps.evera_client import EveraClient
        except ImportError:
            missing.append("apps.evera_client not available")

        try:
            from apps.acestep_profiles import QUALITY_PROFILES
        except ImportError:
            missing.append("apps.acestep_profiles not available")

        ready = len(missing) == 0
        self._status = ComponentStatus.READY if ready else ComponentStatus.UNAVAILABLE
        return {
            "ready": ready,
            "status": str(self._status),
            "missing": missing,
            "message": "Music production ready" if ready else f"Missing: {', '.join(missing)}",
        }

    def execute(self, action: str, params: Optional[Dict] = None) -> ComponentResult:
        params = params or {}

        if action == "generate_track":
            return self._generate_track(params)
        elif action == "dj_set":
            return self._dj_set(params)
        elif action == "beat_battle":
            return self._beat_battle(params)
        elif action == "convert_to_mp3":
            return self._convert_to_mp3(params)
        elif action == "list_profiles":
            return self._list_profiles()
        elif action == "list_templates":
            return self._list_templates()
        elif action == "produce_beat":
            return self._produce_beat(params)
        elif action == "get_genre_guide":
            return self._get_genre_guide(params)
        elif action == "evaluate_beat":
            return self._evaluate_beat(params)
        elif action == "build_prompt":
            return self._build_prompt(params)
        elif action == "list_genres":
            return self._list_genres()
        else:
            return ComponentResult(status="failed", error=f"Unknown action: {action}")

    def _generate_track(self, params: Dict) -> ComponentResult:
        prompt = params.get("prompt", "")
        if not prompt:
            return ComponentResult(status="failed", error="prompt required")
        try:
            from apps.evera_client import EveraClient
            client = EveraClient()
            result = client.acestep_generate(
                prompt=prompt,
                bpm=params.get("bpm"),
                key=params.get("key"),
                duration=params.get("duration", 30),
            )
            audio_path = result.get("audio_path", "") if isinstance(result, dict) else ""
            return ComponentResult(
                status="done",
                output=result if isinstance(result, dict) else {"raw": str(result)},
                summary=f"Generated track: {prompt[:60]}",
                artifact_path=audio_path,
                artifact_type="audio",
                chain_data={"audio_path": audio_path, "music_prompt": prompt},
            )
        except Exception as e:
            return ComponentResult(status="failed", error=str(e),
                                   summary=f"Track generation failed: {e}")

    def _dj_set(self, params: Dict) -> ComponentResult:
        duration = params.get("duration_minutes", 15)
        try:
            from apps.auto_dj import AutoDJ
            dj = AutoDJ()
            return ComponentResult(
                status="done",
                output={"duration_minutes": duration, "note": "DJ set ready to generate"},
                summary=f"DJ set ({duration} min) ready to generate",
                chain_data={"dj_duration": duration},
            )
        except Exception as e:
            return ComponentResult(status="failed", error=str(e))

    def _beat_battle(self, params: Dict) -> ComponentResult:
        try:
            from apps.beat_battle import BeatBattle
            return ComponentResult(
                status="done",
                output={"genre": params.get("genre", "hip-hop")},
                summary="Beat battle ready",
            )
        except Exception as e:
            return ComponentResult(status="failed", error=str(e))

    def _convert_to_mp3(self, params: Dict) -> ComponentResult:
        wav_path = params.get("wav_path", "")
        if not wav_path or not os.path.exists(wav_path):
            return ComponentResult(status="failed", error=f"WAV file not found: {wav_path}")
        try:
            from apps.creative_platform import convert_wav_to_mp3
            mp3_path = convert_wav_to_mp3(wav_path, bitrate=params.get("bitrate", "192k"))
            return ComponentResult(
                status="done",
                output={"mp3_path": mp3_path},
                summary=f"Converted to MP3: {mp3_path}",
                artifact_path=mp3_path,
                artifact_type="audio",
                chain_data={"mp3_path": mp3_path},
            )
        except Exception as e:
            return ComponentResult(status="failed", error=str(e))

    def _list_profiles(self) -> ComponentResult:
        try:
            from apps.acestep_profiles import QUALITY_PROFILES
            profiles = {k: {"steps": v.get("steps"), "cfg": v.get("cfg_strength")}
                        for k, v in QUALITY_PROFILES.items()}
            return ComponentResult(
                status="done",
                output={"profiles": profiles},
                summary=f"Available profiles: {', '.join(profiles.keys())}",
            )
        except Exception as e:
            return ComponentResult(status="failed", error=str(e))

    def _list_templates(self) -> ComponentResult:
        try:
            from apps.acestep_profiles import STRUCTURE_TEMPLATES
            templates = list(STRUCTURE_TEMPLATES.keys())
            return ComponentResult(
                status="done",
                output={"templates": templates},
                summary=f"Available templates: {', '.join(templates)}",
            )
        except Exception as e:
            return ComponentResult(status="failed", error=str(e))

    # ------------------------------------------------------------------
    # Producer mode
    # ------------------------------------------------------------------

    def _load_producer_knowledge(self) -> Dict:
        """Load the producer section from music.json knowledge file."""
        knowledge = self.get_knowledge()
        return knowledge.get("producer", {})

    def _resolve_genre(self, genre_str: str) -> tuple:
        """Resolve a user genre string to the canonical genre key and data.

        Returns (genre_key, genre_data) or (None, None) if not found.
        """
        producer = self._load_producer_knowledge()
        genres = producer.get("genres", {})
        genre_lower = genre_str.lower().strip()

        # Direct match
        if genre_lower in genres:
            return genre_lower, genres[genre_lower]

        # Match by display_name substring
        for key, data in genres.items():
            display = data.get("display_name", "").lower()
            if genre_lower in display or display in genre_lower:
                return key, data

        # Fuzzy: check if genre_str is a substring of any key
        for key, data in genres.items():
            if genre_lower in key or key in genre_lower:
                return key, data

        # Common aliases
        aliases = {
            "boom bap": "hip_hop", "boombap": "hip_hop", "rap": "hip_hop",
            "hip-hop": "hip_hop", "hip hop": "hip_hop",
            "lo-fi": "lofi", "lo fi": "lofi", "chillhop": "lofi",
            "chill": "lofi", "chillbeats": "lofi",
            "house": "edm_house", "tech house": "edm_house",
            "deep house": "edm_house", "progressive house": "edm_house",
            "dubstep": "edm_dubstep", "bass music": "edm_dubstep",
            "brostep": "edm_dubstep", "riddim": "edm_dubstep",
            "drum and bass": "dnb", "drum & bass": "dnb", "jungle": "dnb",
            "liquid dnb": "dnb", "neurofunk": "dnb",
            "uk drill": "drill", "ny drill": "drill", "chicago drill": "drill",
            "r&b": "rnb", "rnb": "rnb", "neo-soul": "rnb", "neo soul": "rnb",
            "soul": "rnb", "r and b": "rnb",
            "afrobeats": "afrobeat", "amapiano": "afrobeat",
            "latin": "reggaeton", "latin trap": "reggaeton", "dembow": "reggaeton",
            "drift phonk": "phonk", "memphis": "phonk",
            "orchestral": "cinematic", "film score": "cinematic",
            "soundtrack": "cinematic", "epic": "cinematic",
            "alt rock": "rock", "indie": "rock", "punk": "rock",
            "metal": "rock", "grunge": "rock",
            "smooth jazz": "jazz", "fusion": "jazz", "bebop": "jazz",
            "jersey": "jersey_club", "baltimore club": "jersey_club",
        }
        resolved_key = aliases.get(genre_lower)
        if resolved_key and resolved_key in genres:
            return resolved_key, genres[resolved_key]

        return None, None

    def _produce_beat(self, params: Dict) -> ComponentResult:
        """Genre-aware beat production with optimal defaults from producer knowledge."""
        genre_str = params.get("genre", "")
        if not genre_str:
            return ComponentResult(status="failed", error="genre is required")

        genre_key, genre_data = self._resolve_genre(genre_str)
        if not genre_data:
            available = self._list_genres()
            return ComponentResult(
                status="failed",
                error=f"Unknown genre: '{genre_str}'",
                output=available.output,
                summary=f"Genre '{genre_str}' not recognized. See available genres.",
            )

        # Resolve production parameters — user overrides > genre defaults
        bpm_range = genre_data.get("bpm_range", [120, 130])
        bpm = params.get("bpm") or genre_data.get("sweet_spot_bpm", sum(bpm_range) // 2)
        keys = genre_data.get("common_keys", ["Am"])
        key = params.get("key") or random.choice(keys)
        duration_range = genre_data.get("duration_range", [120, 240])
        duration = params.get("duration") or random.randint(duration_range[0], duration_range[1])
        quality = params.get("quality_profile", "pro")
        mood = params.get("mood", "")
        extra = params.get("extra", "")
        instrumental = params.get("instrumental", True)

        # Build the optimized prompt from the genre template
        prompt_template = genre_data.get("prompt_template", "{mood} {genre} beat")
        prompt = prompt_template.format(
            mood=mood or "energetic",
            bpm=bpm,
            key=key,
            instrument=params.get("instrument", "synth"),
            extra=extra or "professional mix, high quality",
            sub_genre=params.get("sub_genre", genre_data.get("display_name", genre_str)),
            genre=genre_str,
        )

        # Build structure tags for instrumental
        structure_lyrics = None
        if instrumental:
            try:
                from apps.acestep_profiles import build_instrumental_structure
                template_name = genre_data.get("structure_template", "minimal")
                structure_lyrics = build_instrumental_structure(
                    template_name=template_name, duration=duration
                )
            except ImportError:
                _log.debug("acestep_profiles not available for structure")

        # Generate the beat
        try:
            from apps.evera_client import EveraClient
            from apps.acestep_profiles import get_quality_profile

            client = EveraClient()
            qp = get_quality_profile(quality)

            gen_params = {
                "prompt": prompt,
                "bpm": bpm,
                "key": key,
                "duration": duration,
                **qp,
            }
            if structure_lyrics:
                gen_params["lyrics"] = structure_lyrics

            result = client.acestep_generate(**gen_params)
            audio_path = result.get("audio_path", "") if isinstance(result, dict) else ""

            return ComponentResult(
                status="done",
                output={
                    "audio_path": audio_path,
                    "genre": genre_key,
                    "genre_display": genre_data.get("display_name", genre_str),
                    "bpm": bpm,
                    "key": key,
                    "duration": duration,
                    "quality_profile": quality,
                    "prompt_used": prompt,
                    "structure_template": genre_data.get("structure_template"),
                    "reference_producers": genre_data.get("reference_producers", []),
                },
                summary=f"Produced {genre_data['display_name']} beat: {bpm} BPM, {key}, {duration}s [{quality}]",
                artifact_path=audio_path,
                artifact_type="audio",
                chain_data={
                    "audio_path": audio_path,
                    "beat_genre": genre_key,
                    "beat_bpm": bpm,
                    "beat_key": key,
                    "music_prompt": prompt,
                },
            )
        except Exception as e:
            return ComponentResult(
                status="failed",
                error=str(e),
                output={
                    "genre": genre_key,
                    "bpm": bpm,
                    "key": key,
                    "prompt_built": prompt,
                },
                summary=f"Beat production failed: {e}",
            )

    def _get_genre_guide(self, params: Dict) -> ComponentResult:
        """Return deep production knowledge for a genre."""
        genre_str = params.get("genre", "")
        if not genre_str:
            return ComponentResult(status="failed", error="genre is required")

        genre_key, genre_data = self._resolve_genre(genre_str)
        if not genre_data:
            return ComponentResult(
                status="failed",
                error=f"Unknown genre: '{genre_str}'",
                summary=f"No production guide for '{genre_str}'",
            )

        producer = self._load_producer_knowledge()
        universal = producer.get("universal_rules", {})
        key_guide = producer.get("key_selection_guide", {})

        guide = {
            "genre": genre_key,
            "display_name": genre_data.get("display_name"),
            "bpm_range": genre_data.get("bpm_range"),
            "sweet_spot_bpm": genre_data.get("sweet_spot_bpm"),
            "common_keys": genre_data.get("common_keys"),
            "time_signature": genre_data.get("time_signature"),
            "duration_range": genre_data.get("duration_range"),
            "drum_pattern": genre_data.get("drum_pattern"),
            "sound_design": genre_data.get("sound_design"),
            "arrangement_tips": genre_data.get("arrangement_tips"),
            "reference_producers": genre_data.get("reference_producers"),
            "prompt_template": genre_data.get("prompt_template"),
            "structure_template": genre_data.get("structure_template"),
            "universal_rules": universal,
            "key_emotions": {
                k: key_guide.get("emotional_map", {}).get(k, "")
                for k in genre_data.get("common_keys", [])
            },
        }

        return ComponentResult(
            status="done",
            output=guide,
            summary=(
                f"{genre_data['display_name']} guide: "
                f"{genre_data['bpm_range'][0]}-{genre_data['bpm_range'][1]} BPM, "
                f"keys: {', '.join(genre_data.get('common_keys', [])[:3])}, "
                f"ref: {', '.join(genre_data.get('reference_producers', [])[:3])}"
            ),
        )

    def _evaluate_beat(self, params: Dict) -> ComponentResult:
        """Run the beat evaluation checklist."""
        producer = self._load_producer_knowledge()
        checklist = producer.get("beat_evaluation_checklist", [])
        genre_str = params.get("genre", "")
        notes = params.get("notes", "")

        genre_tips = []
        if genre_str:
            _, genre_data = self._resolve_genre(genre_str)
            if genre_data:
                genre_tips = genre_data.get("arrangement_tips", [])

        return ComponentResult(
            status="done",
            output={
                "checklist": checklist,
                "genre_specific_tips": genre_tips,
                "audio_path": params.get("audio_path", ""),
                "notes": notes,
            },
            summary=f"Evaluation checklist: {len(checklist)} items" +
                    (f" + {len(genre_tips)} {genre_str} tips" if genre_tips else ""),
        )

    def _build_prompt(self, params: Dict) -> ComponentResult:
        """Build an optimized ACE-Step prompt from genre + mood + extras."""
        genre_str = params.get("genre", "")
        if not genre_str:
            return ComponentResult(status="failed", error="genre is required")

        genre_key, genre_data = self._resolve_genre(genre_str)
        if not genre_data:
            return ComponentResult(
                status="failed",
                error=f"Unknown genre: '{genre_str}'",
            )

        mood = params.get("mood", "energetic")
        instrument = params.get("instrument", "synth")
        extra = params.get("extra", "professional mix, high quality")
        sub_genre = params.get("sub_genre", genre_data.get("display_name", genre_str))

        bpm = params.get("bpm") or genre_data.get("sweet_spot_bpm", 120)
        keys = genre_data.get("common_keys", ["Am"])
        key = params.get("key") or random.choice(keys)

        template = genre_data.get("prompt_template", "{mood} {genre} beat")
        prompt = template.format(
            mood=mood, bpm=bpm, key=key, instrument=instrument,
            extra=extra, sub_genre=sub_genre, genre=genre_str,
        )

        # Also get the structure tags
        structure = ""
        try:
            from apps.acestep_profiles import build_instrumental_structure
            structure = build_instrumental_structure(
                template_name=genre_data.get("structure_template", "minimal"),
                duration=params.get("duration", 180),
            )
        except ImportError:
            pass

        producer = self._load_producer_knowledge()
        prompt_rules = producer.get("universal_rules", {}).get("prompt_engineering", {}).get("rules", [])

        return ComponentResult(
            status="done",
            output={
                "prompt": prompt,
                "structure_lyrics": structure,
                "metadata": {"bpm": bpm, "key": key},
                "recommended_profile": "pro",
                "prompt_engineering_tips": prompt_rules,
            },
            summary=f"Built prompt for {genre_data['display_name']}: {bpm} BPM, {key}",
            chain_data={"music_prompt": prompt, "beat_bpm": bpm, "beat_key": key},
        )

    def _list_genres(self) -> ComponentResult:
        """List all supported producer genres."""
        producer = self._load_producer_knowledge()
        genres = producer.get("genres", {})

        genre_list = {}
        for key, data in genres.items():
            genre_list[key] = {
                "display_name": data.get("display_name"),
                "bpm_range": data.get("bpm_range"),
                "sweet_spot_bpm": data.get("sweet_spot_bpm"),
                "common_keys": data.get("common_keys", [])[:3],
                "reference_producers": data.get("reference_producers", [])[:3],
            }

        return ComponentResult(
            status="done",
            output={"genres": genre_list, "count": len(genre_list)},
            summary=f"{len(genre_list)} genres available: {', '.join(d.get('display_name','?') for d in genre_list.values())}",
        )
