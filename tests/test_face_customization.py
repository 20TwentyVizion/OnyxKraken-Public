"""Tests for the face customization system.

Covers:
  - FaceCanvas geometry/animation instance properties
  - apply_geometry / apply_animation / apply_customization
  - Settings persistence (geometry, animation, presets, custom accent)
  - Face customization API routes
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ---------------------------------------------------------------------------
# FaceCanvas customization methods (no GUI needed — just test the data layer)
# ---------------------------------------------------------------------------

class TestFaceCanvasCustomization:
    """Test apply_geometry, apply_animation, apply_customization on FaceCanvas."""

    def _make_canvas_stub(self):
        """Create a minimal FaceCanvas-like object with customization methods."""
        from face.face_gui import (
            _EYE_WIDTH, _EYE_HEIGHT, _EYE_SPACING, _EYE_Y,
            _PUPIL_RADIUS, _PUPIL_MAX_OX, _PUPIL_MAX_OY,
            _MOUTH_Y, _MOUTH_WIDTH, _MOUTH_HEIGHT,
            BLINK_INTERVAL_MIN, BLINK_INTERVAL_MAX, BLINK_DURATION,
            DOUBLE_BLINK_CHANCE, GAZE_CHANGE_MIN, GAZE_CHANGE_MAX, GAZE_SPEED,
            _THEMES, _EYE_STYLES, _FACE_SHAPES, _ACCESSORIES,
        )

        class Stub:
            pass

        s = Stub()
        # Geometry defaults
        s._geo_eye_width = _EYE_WIDTH
        s._geo_eye_height = _EYE_HEIGHT
        s._geo_eye_spacing = _EYE_SPACING
        s._geo_eye_y = _EYE_Y
        s._geo_pupil_radius = _PUPIL_RADIUS
        s._geo_pupil_max_ox = _PUPIL_MAX_OX
        s._geo_pupil_max_oy = _PUPIL_MAX_OY
        s._geo_mouth_y = _MOUTH_Y
        s._geo_mouth_width = _MOUTH_WIDTH
        s._geo_mouth_height = _MOUTH_HEIGHT
        # Animation defaults
        s._anim_blink_min = BLINK_INTERVAL_MIN
        s._anim_blink_max = BLINK_INTERVAL_MAX
        s._anim_blink_duration = BLINK_DURATION
        s._anim_double_blink_chance = DOUBLE_BLINK_CHANCE
        s._anim_gaze_change_min = GAZE_CHANGE_MIN
        s._anim_gaze_change_max = GAZE_CHANGE_MAX
        s._anim_gaze_speed = GAZE_SPEED
        # Theme state
        s._theme_accent_bright = "#00d4ff"
        s._theme_accent_mid = "#006688"
        s._theme_accent_dim = "#0e2a3d"
        s._theme_accent_vdim = "#091520"
        s._theme_eye_pupil = "#00d4ff"
        s._theme_eye_glow_inner = "#005580"
        s._theme_eye_glow_outer = "#002838"
        s._theme_face_border = "#0e2a3d"
        s._eye_style = "default"
        s._face_shape = "default"
        s._accessory = "none"
        s._scan_lines = True

        # Bind the real methods
        from face.face_gui import FaceCanvas
        import types
        s.apply_geometry = types.MethodType(FaceCanvas.apply_geometry, s)
        s.apply_animation = types.MethodType(FaceCanvas.apply_animation, s)
        s.apply_theme = types.MethodType(FaceCanvas.apply_theme, s)
        s.apply_customization = types.MethodType(FaceCanvas.apply_customization, s)
        return s

    def test_apply_geometry_changes_eye_width(self):
        s = self._make_canvas_stub()
        original = s._geo_eye_width
        s.apply_geometry(eye_width=80)
        assert s._geo_eye_width == 80.0
        assert s._geo_eye_width != original

    def test_apply_geometry_changes_multiple(self):
        s = self._make_canvas_stub()
        s.apply_geometry(eye_height=90, eye_spacing=120, mouth_y=280)
        assert s._geo_eye_height == 90.0
        assert s._geo_eye_spacing == 120.0
        assert s._geo_mouth_y == 280.0

    def test_apply_geometry_ignores_unknown_keys(self):
        s = self._make_canvas_stub()
        before = s._geo_eye_width
        s.apply_geometry(unknown_key=999)
        assert s._geo_eye_width == before

    def test_apply_animation_changes_blink(self):
        s = self._make_canvas_stub()
        s.apply_animation(blink_min=1.0, blink_max=4.0)
        assert s._anim_blink_min == 1.0
        assert s._anim_blink_max == 4.0

    def test_apply_animation_changes_gaze(self):
        s = self._make_canvas_stub()
        s.apply_animation(gaze_speed=10.0, gaze_change_min=0.5)
        assert s._anim_gaze_speed == 10.0
        assert s._anim_gaze_change_min == 0.5

    def test_apply_customization_theme(self):
        s = self._make_canvas_stub()
        s.apply_customization(theme="emerald")
        assert s._theme_accent_bright == "#00ff88"

    def test_apply_customization_eye_style(self):
        s = self._make_canvas_stub()
        s.apply_customization(eye_style="round")
        assert s._eye_style == "round"

    def test_apply_customization_invalid_eye_style_ignored(self):
        s = self._make_canvas_stub()
        s.apply_customization(eye_style="nonexistent")
        assert s._eye_style == "default"

    def test_apply_customization_face_shape(self):
        s = self._make_canvas_stub()
        s.apply_customization(face_shape="hexagon")
        assert s._face_shape == "hexagon"

    def test_apply_customization_accessory(self):
        s = self._make_canvas_stub()
        s.apply_customization(accessory="visor")
        assert s._accessory == "visor"

    def test_apply_customization_custom_accent(self):
        s = self._make_canvas_stub()
        s.apply_customization(custom_accent="#ff0000")
        assert s._theme_accent_bright == "#ff0000"

    def test_apply_customization_invalid_accent_ignored(self):
        s = self._make_canvas_stub()
        original = s._theme_accent_bright
        s.apply_customization(custom_accent="not-a-color")
        assert s._theme_accent_bright == original

    def test_apply_customization_geometry_dict(self):
        s = self._make_canvas_stub()
        s.apply_customization(geometry={"eye_width": 70, "pupil_radius": 20})
        assert s._geo_eye_width == 70.0
        assert s._geo_pupil_radius == 20.0

    def test_apply_customization_animation_dict(self):
        s = self._make_canvas_stub()
        s.apply_customization(animation={"gaze_speed": 8.0})
        assert s._anim_gaze_speed == 8.0

    def test_apply_customization_scan_lines(self):
        s = self._make_canvas_stub()
        s.apply_customization(scan_lines=False)
        assert s._scan_lines is False


# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------

class TestSettingsPersistence:
    """Test that geometry, animation, presets persist via settings."""

    def test_geometry_round_trips(self):
        from face.settings import load_settings, save_settings, SETTINGS_FILE
        # Use a temp file
        import face.settings as mod
        orig = mod.SETTINGS_FILE
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                tmp = f.name
            mod.SETTINGS_FILE = tmp
            s = load_settings()
            s["geometry"] = {"eye_width": 75, "eye_spacing": 110}
            save_settings(s)
            s2 = load_settings()
            assert s2["geometry"]["eye_width"] == 75
            assert s2["geometry"]["eye_spacing"] == 110
        finally:
            mod.SETTINGS_FILE = orig
            os.unlink(tmp)

    def test_animation_round_trips(self):
        import face.settings as mod
        orig = mod.SETTINGS_FILE
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                tmp = f.name
            mod.SETTINGS_FILE = tmp
            s = mod.load_settings()
            s["animation"] = {"gaze_speed": 8.5, "blink_min": 1.5}
            mod.save_settings(s)
            s2 = mod.load_settings()
            assert s2["animation"]["gaze_speed"] == 8.5
            assert s2["animation"]["blink_min"] == 1.5
        finally:
            mod.SETTINGS_FILE = orig
            os.unlink(tmp)

    def test_face_presets_round_trips(self):
        import face.settings as mod
        orig = mod.SETTINGS_FILE
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                tmp = f.name
            mod.SETTINGS_FILE = tmp
            s = mod.load_settings()
            s["face_presets"] = {
                "MyPreset": {"face_theme": "emerald", "eye_style": "round"}
            }
            mod.save_settings(s)
            s2 = mod.load_settings()
            assert "MyPreset" in s2["face_presets"]
            assert s2["face_presets"]["MyPreset"]["face_theme"] == "emerald"
        finally:
            mod.SETTINGS_FILE = orig
            os.unlink(tmp)

    def test_custom_accent_color_round_trips(self):
        import face.settings as mod
        orig = mod.SETTINGS_FILE
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                tmp = f.name
            mod.SETTINGS_FILE = tmp
            s = mod.load_settings()
            s["custom_accent_color"] = "#ff4488"
            mod.save_settings(s)
            s2 = mod.load_settings()
            assert s2["custom_accent_color"] == "#ff4488"
        finally:
            mod.SETTINGS_FILE = orig
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

class TestFaceCustomizeRoutes:
    """Test the face customization API routes."""

    def test_route_module_imports(self):
        from routes.face_customize import router
        assert router.prefix == "/face/customize"

    def test_get_customization_endpoint_exists(self):
        from routes.face_customize import get_customization
        assert callable(get_customization)

    def test_set_customization_endpoint_exists(self):
        from routes.face_customize import set_customization
        assert callable(set_customization)

    def test_list_presets_endpoint_exists(self):
        from routes.face_customize import list_presets
        assert callable(list_presets)

    def test_save_preset_endpoint_exists(self):
        from routes.face_customize import save_preset
        assert callable(save_preset)

    def test_delete_preset_endpoint_exists(self):
        from routes.face_customize import delete_preset
        assert callable(delete_preset)

    def test_get_face_spec_endpoint_exists(self):
        from routes.face_customize import get_face_spec
        assert callable(get_face_spec)

    def test_reset_endpoint_exists(self):
        from routes.face_customize import reset_customization
        assert callable(reset_customization)

    def test_server_has_face_customize_router(self):
        from server import app
        routes = [r.path for r in app.routes]
        assert "/face/customize" in routes
        assert "/face/customize/presets" in routes
        assert "/face/customize/spec" in routes
        assert "/face/customize/reset" in routes


# ---------------------------------------------------------------------------
# Face spec structure
# ---------------------------------------------------------------------------

class TestFaceSpec:
    """Verify face spec has all required customization catalogs."""

    def test_spec_has_themes(self):
        from face.face_gui import _THEMES
        assert len(_THEMES) >= 9
        assert "cyan" in _THEMES
        assert "emerald" in _THEMES

    def test_spec_has_eye_styles(self):
        from face.face_gui import _EYE_STYLES
        assert len(_EYE_STYLES) >= 5
        assert "default" in _EYE_STYLES

    def test_spec_has_face_shapes(self):
        from face.face_gui import _FACE_SHAPES
        assert len(_FACE_SHAPES) >= 5
        assert "default" in _FACE_SHAPES

    def test_spec_has_accessories(self):
        from face.face_gui import _ACCESSORIES
        assert len(_ACCESSORIES) >= 6
        assert "none" in _ACCESSORIES

    def test_spec_has_geometry(self):
        from face.face_gui import _SPEC
        geo = _SPEC["geometry"]
        for key in ("eye_width", "eye_height", "eye_spacing", "eye_y",
                     "pupil_radius", "mouth_y", "mouth_width", "mouth_height"):
            assert key in geo

    def test_spec_has_animation(self):
        from face.face_gui import _SPEC
        anim = _SPEC["animation"]
        for key in ("blink_interval_min", "blink_interval_max", "blink_duration",
                     "gaze_speed", "gaze_change_min", "gaze_change_max"):
            assert key in anim

    def test_spec_has_emotion_presets(self):
        from face.face_gui import _SPEC
        presets = _SPEC["emotion_presets"]
        assert len(presets) >= 16
        assert "neutral" in presets
        assert "happy" in presets
