"""Episode DSL — declarative scripted scenes.

Episodes are YAML files in data/episodes/ describing characters, beats,
choices, and state. The player walks the beats, dispatching face/body/
speak events on the drive bus.
"""
from core.episode.schema import (
    Episode,
    Beat,
    DialogueBeat,
    PoseBeat,
    EmotionBeat,
    AnimBeat,
    WaitBeat,
    ChoiceBeat,
    GotoBeat,
    SetBeat,
    SceneBeat,
    MusicBeat,
    SfxBeat,
    CameraBeat,
    LightingBeat,
    GazeBeat,
    parse_episode,
    load_episode,
)
from core.episode.player import (
    EpisodePlayer,
    play_episode,
    list_episodes,
)

__all__ = [
    "Episode", "Beat", "DialogueBeat", "PoseBeat", "EmotionBeat",
    "AnimBeat", "WaitBeat", "ChoiceBeat", "GotoBeat", "SetBeat", "SceneBeat",
    "MusicBeat", "SfxBeat", "CameraBeat", "LightingBeat", "GazeBeat",
    "parse_episode", "load_episode",
    "EpisodePlayer", "play_episode", "list_episodes",
]
