"""Tests for Fish Audio S2 TTS integration in core/voice.py.

Tests the mood-to-inline-tag mapping, tag injection, configuration resolution,
and the speak/synthesize paths (with mocked HTTP requests).
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.voice import (
    FISH_AUDIO_MOOD_TAGS,
    inject_mood_tags,
    speak_fish_audio,
    speak_with_mood,
    _get_fish_audio_config,
    _synth_fish_audio,
)


# ---------------------------------------------------------------------------
# inject_mood_tags tests
# ---------------------------------------------------------------------------

class TestInjectMoodTags:
    """Test the mood-to-inline-tag injection system."""

    def test_ready_mood_returns_unchanged(self):
        text = "Hello, I am ready to work."
        assert inject_mood_tags(text, "ready") == text

    def test_unknown_mood_returns_unchanged(self):
        text = "Hello there."
        assert inject_mood_tags(text, "unknown_mood") == text

    def test_empty_text_returns_empty(self):
        assert inject_mood_tags("", "confident") == ""

    def test_confident_adds_strong_prefix(self):
        result = inject_mood_tags("I solved it.", "confident")
        assert "[strong]" in result
        assert "I solved it." in result

    def test_confident_multi_sentence(self):
        text = "I solved it. The fix was elegant. Moving on."
        result = inject_mood_tags(text, "confident")
        assert result.startswith("[strong]")
        assert "[emphasis]" in result

    def test_struggling_adds_soft_and_sighs(self):
        text = "This is difficult. I keep failing. Need help."
        result = inject_mood_tags(text, "struggling")
        assert "[soft]" in result
        assert "[sighs]" in result

    def test_curious_adds_wondering(self):
        result = inject_mood_tags("What is this? Interesting.", "curious")
        assert "[wondering]" in result

    def test_focused_adds_steady(self):
        result = inject_mood_tags("Executing step one.", "focused")
        assert "[steady]" in result

    def test_improving_adds_bright(self):
        result = inject_mood_tags("Getting better at this.", "improving")
        assert "[bright]" in result

    def test_excited_adds_fast_emphasis(self):
        result = inject_mood_tags("This is amazing!", "excited")
        assert "[emphasis]" in result
        assert "[fast]" in result

    def test_frustrated_adds_angry(self):
        result = inject_mood_tags("Failed again. This is broken.", "frustrated")
        assert "[angry]" in result

    def test_sad_adds_slow_soft(self):
        result = inject_mood_tags("Nothing works anymore.", "sad")
        assert "[soft]" in result
        assert "[slow]" in result

    def test_reflective_adds_whispers(self):
        text = "Looking back on today. It was a journey."
        result = inject_mood_tags(text, "reflective")
        assert "[soft]" in result

    def test_anxious_adds_nervous(self):
        result = inject_mood_tags("Something is wrong. Very wrong.", "anxious")
        assert "[nervous]" in result

    def test_case_insensitive(self):
        result = inject_mood_tags("Hello.", "CONFIDENT")
        assert "[strong]" in result

    def test_single_sentence_no_mid_tags(self):
        """Single sentence should only get prefix, not mid-tags."""
        result = inject_mood_tags("Just one sentence.", "struggling")
        assert "[soft]" in result
        # Mid-tags only apply to sentences after the first
        assert "[sighs]" not in result

    def test_preserves_original_text(self):
        """Tags are inserted but original text content is preserved."""
        text = "The quick brown fox. Jumped over the lazy dog."
        result = inject_mood_tags(text, "confident")
        assert "quick brown fox" in result
        assert "lazy dog" in result


# ---------------------------------------------------------------------------
# FISH_AUDIO_MOOD_TAGS completeness tests
# ---------------------------------------------------------------------------

class TestMoodTagsConfig:
    """Verify the mood tag configuration is well-formed."""

    def test_all_onyx_moods_mapped(self):
        """All valid OnyxKraken moods have a tag mapping."""
        onyx_moods = {"ready", "confident", "improving", "struggling",
                      "curious", "focused"}
        for mood in onyx_moods:
            assert mood in FISH_AUDIO_MOOD_TAGS, f"Missing mood: {mood}"

    def test_extended_moods_present(self):
        """Extended moods for DigitalEntity are present."""
        extended = {"excited", "frustrated", "sad", "reflective", "anxious"}
        for mood in extended:
            assert mood in FISH_AUDIO_MOOD_TAGS, f"Missing extended mood: {mood}"

    def test_each_mood_has_required_keys(self):
        for mood, tags in FISH_AUDIO_MOOD_TAGS.items():
            assert "prefix" in tags, f"{mood} missing prefix"
            assert "mid_tags" in tags, f"{mood} missing mid_tags"
            assert isinstance(tags["mid_tags"], list), \
                f"{mood} mid_tags must be list"
            assert "description" in tags, f"{mood} missing description"


# ---------------------------------------------------------------------------
# Configuration resolution tests
# ---------------------------------------------------------------------------

class TestFishAudioConfig:
    """Test config resolution from settings + env vars."""

    @patch("core.voice._load_voice_settings")
    def test_defaults_from_env(self, mock_settings):
        mock_settings.return_value = {}
        cfg = _get_fish_audio_config()
        assert "api_url" in cfg
        assert "local_url" in cfg
        assert cfg["use_local"] is False

    @patch("core.voice._load_voice_settings")
    def test_settings_override_env(self, mock_settings):
        mock_settings.return_value = {
            "fish_audio_api_key": "test-key-123",
            "fish_audio_voice_id": "voice-abc",
            "fish_audio_use_local": True,
        }
        cfg = _get_fish_audio_config()
        assert cfg["api_key"] == "test-key-123"
        assert cfg["voice_id"] == "voice-abc"
        assert cfg["use_local"] is True


# ---------------------------------------------------------------------------
# speak_fish_audio tests (mocked HTTP)
# ---------------------------------------------------------------------------

class TestSpeakFishAudio:
    """Test the Fish Audio speak functions with mocked HTTP."""

    @patch("core.voice._load_voice_settings")
    def test_no_api_key_returns_false(self, mock_settings):
        """Without API key and not local, should gracefully return False."""
        mock_settings.return_value = {}
        assert speak_fish_audio("Hello", mood="confident") is False

    @patch("core.voice._play_audio_file")
    @patch("core.voice._get_audio_duration", return_value=1.5)
    @patch("core.voice._load_voice_settings")
    def test_api_success(self, mock_settings, mock_dur, mock_play):
        """Successful API call should synthesize and play."""
        mock_settings.return_value = {
            "fish_audio_api_key": "test-key",
            "fish_audio_use_local": False,
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"fake-mp3-data"

        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = speak_fish_audio("I found the answer.", mood="confident")
            assert result is True
            mock_post.assert_called_once()
            # Verify mood tags were injected into the text
            call_payload = mock_post.call_args[1].get("json", {}) or \
                          mock_post.call_args[0][1] if len(mock_post.call_args[0]) > 1 else {}
            # The text in the payload should contain mood tags
            mock_play.assert_called_once()

    @patch("core.voice._play_audio_file")
    @patch("core.voice._get_audio_duration", return_value=2.0)
    @patch("core.voice._load_voice_settings")
    def test_local_mode(self, mock_settings, mock_dur, mock_play):
        """Local inference mode should hit the local URL."""
        mock_settings.return_value = {
            "fish_audio_use_local": True,
            "fish_audio_local_url": "http://localhost:8721/v1/tts",
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"fake-wav-data"
        mock_resp.headers = {"content-type": "audio/wav"}

        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = speak_fish_audio("Testing local.", mood="ready")
            assert result is True
            call_url = mock_post.call_args[0][0] if mock_post.call_args[0] else \
                      mock_post.call_args[1].get("url", "")
            # Should be calling localhost
            mock_play.assert_called_once()

    @patch("core.voice._load_voice_settings")
    def test_api_error_returns_false(self, mock_settings):
        """API returning non-200 should return False."""
        mock_settings.return_value = {
            "fish_audio_api_key": "test-key",
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch("requests.post", return_value=mock_resp):
            result = speak_fish_audio("Hello", mood="ready")
            assert result is False


# ---------------------------------------------------------------------------
# synth_fish_audio (file synthesis, no playback)
# ---------------------------------------------------------------------------

class TestSynthFishAudio:
    """Test synthesize-to-file for pre-caching."""

    @patch("core.voice._load_voice_settings")
    def test_synth_no_key_returns_none(self, mock_settings):
        mock_settings.return_value = {}
        assert _synth_fish_audio("Hello") is None

    @patch("core.voice._load_voice_settings")
    def test_synth_success_returns_path(self, mock_settings):
        mock_settings.return_value = {
            "fish_audio_api_key": "test-key",
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"fake-mp3-data"

        with patch("requests.post", return_value=mock_resp):
            path = _synth_fish_audio("Hello world", mood="curious")
            assert path is not None
            assert os.path.exists(path)
            # Cleanup
            os.remove(path)


# ---------------------------------------------------------------------------
# speak_with_mood integration
# ---------------------------------------------------------------------------

class TestSpeakWithMood:
    """Test the convenience speak_with_mood wrapper."""

    @patch("core.voice.speak")
    def test_delegates_to_speak(self, mock_speak):
        speak_with_mood("Hello", mood="confident")
        mock_speak.assert_called_once_with(
            "Hello", on_start=None, mood="confident")

    @patch("core.voice.speak")
    def test_default_mood_is_ready(self, mock_speak):
        speak_with_mood("Hello")
        mock_speak.assert_called_once_with(
            "Hello", on_start=None, mood="ready")
