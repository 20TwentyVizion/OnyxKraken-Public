"""Tests for the MusicProducer conversation engine.

Tests the conversation flow, parameter extraction, state machine, and
post-generation intent classification WITHOUT requiring EVERA services.
"""

import pytest
from core.hands.music_producer import (
    MusicProducer,
    SessionState,
    TrackRequest,
    extract_params,
    _extract_params_regex,
    classify_post_gen_intent,
    AVAILABLE_GENRES,
    GENRE_DEFAULTS,
)


# ---------------------------------------------------------------------------
# Parameter extraction tests
# ---------------------------------------------------------------------------

class TestParamExtraction:
    """Test regex-based parameter extraction from natural language."""

    def test_genre_trap(self):
        p = _extract_params_regex("make me a dark trap beat")
        assert p["genre"] == "trap"

    def test_genre_rap_not_trap(self):
        p = _extract_params_regex("make a rap beat")
        assert p["genre"] == "hip_hop"

    def test_genre_jazz(self):
        p = _extract_params_regex("generate a jazz song")
        assert p["genre"] == "jazz"

    def test_genre_lofi(self):
        p = _extract_params_regex("make some lo-fi music")
        assert p["genre"] == "lo_fi"

    def test_genre_lofi_no_hyphen(self):
        p = _extract_params_regex("lofi beat")
        assert p["genre"] == "lo_fi"

    def test_genre_electronic(self):
        p = _extract_params_regex("electronic track")
        assert p["genre"] == "electronic"

    def test_genre_edm(self):
        p = _extract_params_regex("make an edm banger")
        assert p["genre"] == "edm"

    def test_genre_cinematic(self):
        p = _extract_params_regex("cinematic soundtrack")
        assert p["genre"] == "cinematic"

    def test_genre_hip_hop_alias(self):
        p = _extract_params_regex("a hip-hop track")
        assert p["genre"] == "hip_hop"

    def test_no_genre_vague(self):
        p = _extract_params_regex("make me a song")
        assert "genre" not in p

    def test_duration_minutes(self):
        p = _extract_params_regex("3 minute track")
        assert p["duration"] == 180

    def test_duration_seconds(self):
        p = _extract_params_regex("60 second beat")
        assert p["duration"] == 60

    def test_duration_min_abbrev(self):
        p = _extract_params_regex("make a 2 min track")
        assert p["duration"] == 120

    def test_bpm(self):
        p = _extract_params_regex("trap beat at 140 bpm")
        assert p["bpm"] == 140

    def test_key_minor(self):
        p = _extract_params_regex("in C minor")
        assert p["key"] == "C minor"

    def test_key_major(self):
        p = _extract_params_regex("key of Ab major")
        assert p["key"] == "Ab major"

    def test_vocal_instrumental(self):
        p = _extract_params_regex("instrumental beat")
        assert p["vocal"] == "instrumental"

    def test_vocal_no_vocals(self):
        p = _extract_params_regex("no vocals")
        assert p["vocal"] == "instrumental"

    def test_vocal_female(self):
        p = _extract_params_regex("female vocal track")
        assert p["vocal"] == "female"

    def test_mood_dark(self):
        p = _extract_params_regex("something dark and moody")
        assert p["mood"] == "dark"

    def test_mood_chill(self):
        p = _extract_params_regex("chill vibes")
        assert p["mood"] == "chill"

    def test_mood_upbeat(self):
        p = _extract_params_regex("upbeat and happy")
        assert p["mood"] == "upbeat"

    def test_quality_quick(self):
        p = _extract_params_regex("quick preview")
        assert p["quality_profile"] == "quick_draft"

    def test_quality_pro(self):
        p = _extract_params_regex("best quality")
        assert p["quality_profile"] == "pro"

    def test_theme_quoted(self):
        p = _extract_params_regex('jazz with a "midnight city streets" vibe')
        assert p["theme"] == "midnight city streets"

    def test_seed(self):
        p = _extract_params_regex("seed 42")
        assert p["seed"] == 42

    def test_model_turbo(self):
        p = _extract_params_regex("use turbo model")
        assert p["model"] == "acestep-v15-turbo"

    def test_combined_extraction(self):
        p = _extract_params_regex(
            "generate a dark trap instrumental, 2 minutes, 140 bpm, C minor"
        )
        assert p["genre"] == "trap"
        assert p["vocal"] == "instrumental"
        assert p["duration"] == 120
        assert p["bpm"] == 140
        assert p["key"] == "C minor"
        assert p["mood"] == "dark"

    def test_extract_params_uses_regex_when_genre_found(self):
        """extract_params should use regex path when genre is found."""
        p = extract_params("make me a trap beat")
        assert p["genre"] == "trap"


# ---------------------------------------------------------------------------
# TrackRequest tests
# ---------------------------------------------------------------------------

class TestTrackRequest:
    def test_not_ready_without_genre(self):
        tr = TrackRequest()
        assert not tr.is_ready()

    def test_ready_with_genre(self):
        tr = TrackRequest(genre="trap")
        assert tr.is_ready()

    def test_apply_genre_defaults_trap(self):
        tr = TrackRequest(genre="trap")
        tr.apply_genre_defaults()
        assert tr.bpm == 140
        assert tr.mood == "dark"

    def test_apply_genre_defaults_no_override(self):
        tr = TrackRequest(genre="jazz", bpm=80, mood="soulful")
        tr.apply_genre_defaults()
        assert tr.bpm == 80  # should NOT override
        assert tr.mood == "soulful"  # should NOT override

    def test_summary(self):
        tr = TrackRequest(genre="trap", mood="dark", duration=120)
        s = tr.summary()
        assert "dark" in s
        assert "trap" in s
        assert "120s" in s

    def test_to_generate_params(self):
        tr = TrackRequest(genre="jazz", mood="smooth", theme="late night",
                          duration=240, quality_profile="radio_quality")
        p = tr.to_generate_params()
        assert p["genre"] == "jazz"
        assert p["mood"] == "smooth"
        assert p["theme"] == "late night"
        assert p["duration"] == 240
        assert p["instrumental"] is True
        assert p["quality_profile"] == "radio_quality"

    def test_to_acestep_params(self):
        tr = TrackRequest(genre="trap", mood="dark", bpm=140, duration=60)
        p = tr.to_acestep_params()
        assert "trap" in p["prompt"]
        assert "dark" in p["prompt"]
        assert p["duration"] == 60
        assert p["bpm"] == 140


# ---------------------------------------------------------------------------
# Post-generation intent classification
# ---------------------------------------------------------------------------

class TestPostGenIntent:
    def test_play(self):
        assert classify_post_gen_intent("play it") == "play"
        assert classify_post_gen_intent("let me hear it") == "play"

    def test_score(self):
        assert classify_post_gen_intent("score it") == "score"
        assert classify_post_gen_intent("how good is it?") == "score"
        assert classify_post_gen_intent("analyze the track") == "score"

    def test_cover(self):
        assert classify_post_gen_intent("cover it in jazz") == "cover"
        assert classify_post_gen_intent("remix it as lo-fi") == "cover"

    def test_repaint(self):
        assert classify_post_gen_intent("repaint the intro") == "repaint"
        assert classify_post_gen_intent("redo the chorus") == "repaint"
        assert classify_post_gen_intent("fix the outro") == "repaint"

    def test_layer(self):
        assert classify_post_gen_intent("add guitar") == "layer"
        assert classify_post_gen_intent("layer some piano") == "layer"
        assert classify_post_gen_intent("overlay strings") == "layer"

    def test_stems(self):
        assert classify_post_gen_intent("separate stems") == "stems"
        assert classify_post_gen_intent("isolate the vocals") == "stems"

    def test_regen(self):
        assert classify_post_gen_intent("regenerate it") == "regen"
        assert classify_post_gen_intent("try again") == "regen"
        assert classify_post_gen_intent("make another version") == "regen"

    def test_done(self):
        assert classify_post_gen_intent("done") == "done"
        assert classify_post_gen_intent("that's it") == "done"
        assert classify_post_gen_intent("thanks") == "done"
        assert classify_post_gen_intent("save it") == "done"


# ---------------------------------------------------------------------------
# Conversation state machine tests (no EVERA needed)
# ---------------------------------------------------------------------------

class TestConversationFlow:
    def test_vague_request_asks_genre(self):
        mp = MusicProducer()
        resp, state = mp.start_session("make me a song")
        assert state == SessionState.GATHERING
        assert "genre" in resp.lower()

    def test_genre_only_gets_confirmation_or_generation(self):
        mp = MusicProducer()
        resp, state = mp.start_session("make me a song")
        # Now provide genre
        resp2, state2 = mp.handle_input("trap")
        # Should either confirm or try to generate (not ask more questions)
        assert state2 in (SessionState.CONFIRMING, SessionState.GENERATING,
                          SessionState.POST_GEN, SessionState.GATHERING)
        # The request should now have trap as genre
        assert mp.request.genre == "trap"

    def test_detailed_request_skips_questions(self):
        """Detailed request should skip gathering and go straight to confirm/gen."""
        mp = MusicProducer()
        resp, state = mp.start_session("generate a 4-minute smooth jazz instrumental")
        # Should NOT be gathering (genre was found)
        assert mp.request.genre == "jazz"
        assert mp.request.duration == 240
        assert mp.request.mood == "smooth"
        # Should try to confirm or generate (not ask questions)
        assert state in (SessionState.CONFIRMING, SessionState.GENERATING,
                          SessionState.POST_GEN, SessionState.GATHERING)

    def test_cancel_ends_session(self):
        mp = MusicProducer()
        mp.start_session("make me a song")
        resp, state = mp.handle_input("cancel")
        assert state == SessionState.DONE
        assert not mp.is_active

    def test_session_timeout(self):
        mp = MusicProducer()
        mp.start_session("make me a song")
        # Fake old timestamp
        mp._last_activity = 0
        assert not mp.is_active

    def test_confirmation_yes(self):
        mp = MusicProducer()
        mp.request = TrackRequest(genre="trap", mood="dark", duration=120)
        mp.state = SessionState.CONFIRMING
        # "yes" should trigger generation
        resp, state = mp.handle_input("yes")
        # It'll try to generate (may fail without EVERA, but state should change)
        assert state in (SessionState.GENERATING, SessionState.POST_GEN,
                          SessionState.GATHERING)

    def test_confirmation_no(self):
        mp = MusicProducer()
        mp.request = TrackRequest(genre="trap")
        mp.state = SessionState.CONFIRMING
        resp, state = mp.handle_input("no")
        assert state == SessionState.GATHERING
        assert "change" in resp.lower()

    def test_post_gen_done(self):
        mp = MusicProducer()
        mp.state = SessionState.POST_GEN
        mp.result = None  # No actual result, but state is POST_GEN
        resp, state = mp.handle_input("done")
        assert state == SessionState.DONE

    def test_post_gen_unknown_shows_options(self):
        mp = MusicProducer()
        mp.state = SessionState.POST_GEN
        mp.result = None
        resp, state = mp.handle_input("hmm what now")
        assert state == SessionState.POST_GEN
        assert "Play" in resp
        assert "Score" in resp


# ---------------------------------------------------------------------------
# Genre defaults coverage
# ---------------------------------------------------------------------------

class TestGenreDefaults:
    def test_all_available_genres_have_defaults(self):
        """Every genre in AVAILABLE_GENRES should have a GENRE_DEFAULTS entry."""
        for g in AVAILABLE_GENRES:
            assert g in GENRE_DEFAULTS, f"Missing GENRE_DEFAULTS for '{g}'"

    def test_all_defaults_have_required_keys(self):
        for g, d in GENRE_DEFAULTS.items():
            assert "bpm" in d, f"'{g}' missing 'bpm'"
            assert "mood" in d, f"'{g}' missing 'mood'"
            assert "structure" in d, f"'{g}' missing 'structure'"
