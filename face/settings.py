"""Onyx Settings — Persistent user preferences stored in JSON."""
import json
import os
import logging

_log = logging.getLogger("face.settings")

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "settings.json")

DEFAULTS = {
    "user_name": "",
    "elevenlabs_voice_id": "",
    "elevenlabs_api_key": "",
    "tts_enabled": True,
    "tts_engine": "auto",              # auto / fish / elevenlabs / edge / system
    "edge_tts_voice": "en-US-GuyNeural",
    "fish_audio_api_key": "",
    "fish_audio_voice_id": "",
    "xyno_voice_id": "iBo5PWT1qLiEyqhM7TrG",   # Xyno's ElevenLabs voice
    "xyno_enabled": True,                        # allow Xyno segments in episodes
    "elevenlabs_sfx_budget": 10,                 # max sound-gen calls per episode
    "hands_free": False,
    "theme": "dark",
    "idle_tasks_enabled": True,
    "idle_night_mode": True,       # 3am-6am constructive tasks
    "personality_preset": "OnyxKraken Default",  # active personality preset
    # Face customization
    "face_theme": "cyan",          # color theme key from face_spec.json
    "eye_style": "default",        # eye shape variant
    "face_shape": "default",       # face plate shape
    "accessory": "none",           # overlay accessory
    "scan_lines": True,            # CRT scan line overlay
    "custom_accent_color": "",     # hex color override (empty = use theme)
    "geometry": {},                # geometry overrides dict (eye_width, eye_height, etc.)
    "animation": {},               # animation overrides dict (blink_min, gaze_speed, etc.)
    "face_presets": {},            # saved named face presets {name: {theme, eye_style, ...}}
    # Body settings
    "body_offset_x": 0,            # horizontal offset from center (pixels)
    "body_offset_y": 0,            # vertical offset from default neck position (pixels)
    "body_scale": 1.0,             # body size multiplier (0.3–2.0)
    "body_visible": True,          # show/hide body overlay
    "active_character": "onyx",    # character template key (onyx, xyno, volt, nova, sage, blaze, frost, ember)
}


def _ensure_dir():
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)


def load_settings() -> dict:
    """Load settings from disk, returning defaults for missing keys."""
    settings = dict(DEFAULTS)
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
            settings.update(stored)
    except Exception as e:
        _log.warning(f"Failed to load settings: {e}")
    return settings


def save_settings(settings: dict):
    """Save settings to disk."""
    try:
        _ensure_dir()
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        _log.error(f"Failed to save settings: {e}")


def get(key: str, default=None):
    """Get a single setting value."""
    settings = load_settings()
    return settings.get(key, default)


def set(key: str, value):
    """Set a single setting value and save."""
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
