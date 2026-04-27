"""Tests for production beat types (music, sfx, camera, lighting, gaze)."""

import pytest
from pathlib import Path

from core.episode import (
    parse_episode, load_episode,
    MusicBeat, SfxBeat, CameraBeat, LightingBeat, GazeBeat,
)


def test_music_beat_parsing():
    """Test MusicBeat parses from dict."""
    raw = {
        "music": "ambient_tech",
        "action": "play",
        "volume": 0.5,
        "fade_ms": 2000,
    }
    ep = parse_episode({"id": "test", "beats": [raw]})
    assert len(ep.beats) == 1
    beat = ep.beats[0]
    assert isinstance(beat, MusicBeat)
    assert beat.track == "ambient_tech"
    assert beat.action == "play"
    assert beat.volume == 0.5
    assert beat.fade_ms == 2000


def test_sfx_beat_parsing():
    """Test SfxBeat parses from dict."""
    raw = {
        "sfx": "whoosh",
        "volume": 0.7,
        "delay_ms": 200,
    }
    ep = parse_episode({"id": "test", "beats": [raw]})
    beat = ep.beats[0]
    assert isinstance(beat, SfxBeat)
    assert beat.sound == "whoosh"
    assert beat.volume == 0.7
    assert beat.delay_ms == 200


def test_camera_beat_parsing():
    """Test CameraBeat parses from dict."""
    raw = {
        "camera": "zoom",
        "target": "onyx",
        "duration_ms": 1500,
        "easing": "ease_in",
    }
    ep = parse_episode({"id": "test", "beats": [raw]})
    beat = ep.beats[0]
    assert isinstance(beat, CameraBeat)
    assert beat.action == "zoom"
    assert beat.target == "onyx"
    assert beat.duration_ms == 1500
    assert beat.easing == "ease_in"


def test_lighting_beat_parsing():
    """Test LightingBeat parses from dict."""
    raw = {
        "lighting": "dramatic",
        "intensity": 0.8,
        "color": "#ff6600",
        "transition_ms": 1000,
    }
    ep = parse_episode({"id": "test", "beats": [raw]})
    beat = ep.beats[0]
    assert isinstance(beat, LightingBeat)
    assert beat.preset == "dramatic"
    assert beat.intensity == 0.8
    assert beat.color == "#ff6600"
    assert beat.transition_ms == 1000


def test_gaze_beat_parsing():
    """Test GazeBeat parses from dict."""
    raw = {
        "gaze": "xyno",
        "who": "onyx",
    }
    ep = parse_episode({"id": "test", "beats": [raw]})
    beat = ep.beats[0]
    assert isinstance(beat, GazeBeat)
    assert beat.target == "xyno"
    assert beat.who == "onyx"


def test_gaze_beat_with_position():
    """Test GazeBeat with world-space position."""
    raw = {
        "gaze": "",
        "who": "onyx",
        "x": 100.0,
        "y": -50.0,
    }
    ep = parse_episode({"id": "test", "beats": [raw]})
    beat = ep.beats[0]
    assert isinstance(beat, GazeBeat)
    assert beat.target == ""
    assert beat.x == 100.0
    assert beat.y == -50.0


def test_production_episode_loads():
    """Test demo_production.yaml loads with all beat types."""
    path = Path("data/episodes/demo_production.yaml")
    if not path.exists():
        pytest.skip("demo_production.yaml not found")
    
    ep = load_episode(path)
    assert ep.id == "demo_production"
    assert len(ep.beats) > 0
    
    # Check we have all production beat types
    beat_types = {type(b).__name__ for b in ep.beats}
    assert "MusicBeat" in beat_types
    assert "SfxBeat" in beat_types
    assert "CameraBeat" in beat_types
    assert "LightingBeat" in beat_types


def test_enhanced_council_episode():
    """Test demo_council.yaml loads with enhanced production beats."""
    path = Path("data/episodes/demo_council.yaml")
    if not path.exists():
        pytest.skip("demo_council.yaml not found")
    
    ep = load_episode(path)
    assert ep.id == "demo_council"
    
    # Check for production beats
    beat_types = {type(b).__name__ for b in ep.beats}
    assert "MusicBeat" in beat_types
    assert "SfxBeat" in beat_types
    assert "CameraBeat" in beat_types
    assert "LightingBeat" in beat_types
    assert "GazeBeat" in beat_types


def test_beat_defaults():
    """Test beat types use correct defaults."""
    # Music defaults
    raw = {"music": "track"}
    ep = parse_episode({"id": "test", "beats": [raw]})
    beat = ep.beats[0]
    assert beat.action == "play"
    assert beat.volume == 1.0
    assert beat.fade_ms == 1000
    
    # SFX defaults
    raw = {"sfx": "sound"}
    ep = parse_episode({"id": "test", "beats": [raw]})
    beat = ep.beats[0]
    assert beat.volume == 1.0
    assert beat.delay_ms == 0
    
    # Camera defaults
    raw = {"camera": "cut"}
    ep = parse_episode({"id": "test", "beats": [raw]})
    beat = ep.beats[0]
    assert beat.target == ""
    assert beat.duration_ms == 1000
    assert beat.easing == "ease"
    
    # Lighting defaults
    raw = {"lighting": "neutral"}
    ep = parse_episode({"id": "test", "beats": [raw]})
    beat = ep.beats[0]
    assert beat.intensity == 1.0
    assert beat.color == ""
    assert beat.transition_ms == 500


def test_beat_guards_work():
    """Test that production beats respect if/unless guards."""
    raw = [
        {"music": "track", "if": "mood == 'ready'"},
        {"sfx": "sound", "unless": "quiet_mode"},
    ]
    ep = parse_episode({"id": "test", "beats": raw, "vars": {"mood": "ready"}})
    
    # Both beats should parse
    assert len(ep.beats) == 2
    assert ep.beats[0].if_ == "mood == 'ready'"
    assert ep.beats[1].unless == "quiet_mode"


def test_backward_compatibility():
    """Test that existing episodes without production beats still work."""
    raw = {
        "id": "simple",
        "beats": [
            {"say": "Hello", "who": "onyx"},
            {"emotion": "happy", "who": "onyx"},
            {"wait_ms": 500},
        ]
    }
    ep = parse_episode(raw)
    assert len(ep.beats) == 3
    # No production beats, but should parse fine


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
