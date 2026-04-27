"""Tests for webcam motion capture system (face/stage/webcam_mocap.py).

Tests cover:
    - Model management (paths, availability checks)
    - TrackingFrame data structure
    - WebcamCapture (init, camera listing)
    - MediaPipeTracker (geometry helpers, angle computation)
    - RetargetMapper (face mapping, body mapping, smoothing, dead zones)
    - MocapRecorder (record, bake to clip, save/load)
    - WebcamMocap orchestrator (state management, stats)
"""

import json
import math
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import numpy as np

from face.stage.webcam_mocap import (
    # Constants
    _MODEL_DIR, FACE_MODEL_FILE, POSE_MODEL_FILE,
    DEFAULT_FACE_ALPHA, DEFAULT_BODY_ALPHA, DEFAULT_DEAD_ZONE,
    PoseLandmark,
    # Model management
    ensure_model_dir, get_model_path, model_available, ensure_models,
    # Data
    TrackingFrame,
    # Classes
    WebcamCapture, MediaPipeTracker, RetargetMapper,
    MocapRecorder, MocapState, WebcamMocap,
)


# ===========================================================================
# Model management
# ===========================================================================

class TestModelManagement:
    """Tests for model file management utilities."""

    def test_model_dir_path(self):
        assert _MODEL_DIR.name == "mediapipe"
        assert _MODEL_DIR.parent.name == "models"

    def test_get_model_path(self):
        p = get_model_path("test.task")
        assert p == _MODEL_DIR / "test.task"

    def test_model_available_missing(self):
        assert model_available("nonexistent_model.task") is False

    def test_ensure_model_dir(self):
        ensure_model_dir()
        assert _MODEL_DIR.is_dir()

    def test_ensure_models_returns_dict(self):
        # Without actual downloads, models won't be available
        # but the function should return a dict
        with patch("face.stage.webcam_mocap.download_model", return_value=True):
            result = ensure_models(face=True, pose=True)
        assert FACE_MODEL_FILE in result
        assert POSE_MODEL_FILE in result

    def test_ensure_models_face_only(self):
        with patch("face.stage.webcam_mocap.download_model", return_value=True):
            result = ensure_models(face=True, pose=False)
        assert FACE_MODEL_FILE in result
        assert POSE_MODEL_FILE not in result

    def test_ensure_models_pose_only(self):
        with patch("face.stage.webcam_mocap.download_model", return_value=True):
            result = ensure_models(face=False, pose=True)
        assert FACE_MODEL_FILE not in result
        assert POSE_MODEL_FILE in result


# ===========================================================================
# PoseLandmark constants
# ===========================================================================

class TestPoseLandmark:
    """Tests for pose landmark index constants."""

    def test_nose_is_zero(self):
        assert PoseLandmark.NOSE == 0

    def test_shoulder_indices(self):
        assert PoseLandmark.LEFT_SHOULDER == 11
        assert PoseLandmark.RIGHT_SHOULDER == 12

    def test_elbow_indices(self):
        assert PoseLandmark.LEFT_ELBOW == 13
        assert PoseLandmark.RIGHT_ELBOW == 14

    def test_hip_indices(self):
        assert PoseLandmark.LEFT_HIP == 23
        assert PoseLandmark.RIGHT_HIP == 24

    def test_knee_indices(self):
        assert PoseLandmark.LEFT_KNEE == 25
        assert PoseLandmark.RIGHT_KNEE == 26

    def test_ankle_indices(self):
        assert PoseLandmark.LEFT_ANKLE == 27
        assert PoseLandmark.RIGHT_ANKLE == 28


# ===========================================================================
# TrackingFrame
# ===========================================================================

class TestTrackingFrame:
    """Tests for TrackingFrame dataclass."""

    def test_defaults(self):
        tf = TrackingFrame()
        assert tf.timestamp == 0.0
        assert tf.face_blendshapes == {}
        assert tf.head_pitch == 0.0
        assert tf.head_yaw == 0.0
        assert tf.head_roll == 0.0
        assert tf.face_detected is False
        assert tf.body_angles == {}
        assert tf.body_detected is False
        assert tf.body_landmarks is None

    def test_with_face_data(self):
        tf = TrackingFrame(
            face_detected=True,
            face_blendshapes={"jawOpen": 0.5, "eyeBlinkLeft": 0.3},
            head_pitch=10.0,
            head_yaw=-5.0,
        )
        assert tf.face_detected is True
        assert tf.face_blendshapes["jawOpen"] == 0.5
        assert tf.head_pitch == 10.0

    def test_with_body_data(self):
        tf = TrackingFrame(
            body_detected=True,
            body_angles={"left_shoulder": -30.0, "right_elbow": 15.0},
        )
        assert tf.body_detected is True
        assert tf.body_angles["left_shoulder"] == -30.0


# ===========================================================================
# WebcamCapture
# ===========================================================================

class TestWebcamCapture:
    """Tests for WebcamCapture (no actual camera needed)."""

    def test_init_defaults(self):
        cap = WebcamCapture()
        assert cap.camera_index == 0
        assert cap.width == 640
        assert cap.height == 480
        assert cap.fps == 30
        assert cap.mirror is True
        assert cap.is_running is False

    def test_init_custom(self):
        cap = WebcamCapture(camera_index=1, width=1280, height=720, fps=60, mirror=False)
        assert cap.camera_index == 1
        assert cap.width == 1280
        assert cap.height == 720
        assert cap.fps == 60
        assert cap.mirror is False

    def test_get_frame_when_stopped(self):
        cap = WebcamCapture()
        assert cap.get_frame() is None

    def test_actual_fps_when_stopped(self):
        cap = WebcamCapture()
        assert cap.actual_fps == 0.0

    def test_list_cameras_returns_list(self):
        # May return empty list if no cameras
        result = WebcamCapture.list_cameras(max_check=2)
        assert isinstance(result, list)

    def test_stop_when_not_started(self):
        cap = WebcamCapture()
        cap.stop()  # Should not raise


# ===========================================================================
# MediaPipeTracker — geometry helpers
# ===========================================================================

class TestMediaPipeTrackerGeometry:
    """Tests for MediaPipeTracker geometry helper methods."""

    def test_rotation_from_identity_matrix(self):
        identity = np.eye(4)
        pitch, yaw, roll = MediaPipeTracker._rotation_from_matrix(identity)
        assert abs(pitch) < 0.1
        assert abs(yaw) < 0.1
        assert abs(roll) < 0.1

    def test_rotation_from_90deg_pitch(self):
        m = np.eye(4)
        # Rotate around X by 90 degrees
        angle = math.radians(90)
        m[1, 1] = math.cos(angle)
        m[1, 2] = -math.sin(angle)
        m[2, 1] = math.sin(angle)
        m[2, 2] = math.cos(angle)
        pitch, yaw, roll = MediaPipeTracker._rotation_from_matrix(m)
        assert abs(pitch - 90.0) < 1.0

    def test_rotation_from_invalid_input(self):
        pitch, yaw, roll = MediaPipeTracker._rotation_from_matrix("invalid")
        assert pitch == 0.0
        assert yaw == 0.0
        assert roll == 0.0

    def test_angle_between_points_straight(self):
        """180 degrees when points are collinear."""
        class Pt:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z

        a = Pt(0, 0, 0)
        b = Pt(1, 0, 0)
        c = Pt(2, 0, 0)
        angle = MediaPipeTracker._angle_between_points(a, b, c)
        assert abs(angle - 180.0) < 0.1

    def test_angle_between_points_right_angle(self):
        class Pt:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z

        a = Pt(0, 1, 0)
        b = Pt(0, 0, 0)
        c = Pt(1, 0, 0)
        angle = MediaPipeTracker._angle_between_points(a, b, c)
        assert abs(angle - 90.0) < 0.1

    def test_angle_between_points_acute(self):
        class Pt:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z

        a = Pt(1, 1, 0)
        b = Pt(0, 0, 0)
        c = Pt(1, 0, 0)
        angle = MediaPipeTracker._angle_between_points(a, b, c)
        assert 40 < angle < 50  # ~45 degrees


class TestMediaPipeTrackerBodyAngles:
    """Tests for body angle computation."""

    @staticmethod
    def _make_landmark(x, y, z, vis=1.0):
        lm = MagicMock()
        lm.x = x
        lm.y = y
        lm.z = z
        lm.visibility = vis
        return lm

    def _make_t_pose_landmarks(self):
        """Create landmarks approximating a T-pose (arms out).

        Layout uses RAW (non-mirrored) webcam coordinates where the
        person's LEFT side appears on the RIGHT of the image.
        """
        lm = [None] * 33
        # Shoulders at same height, spread apart
        # Person's LEFT on the RIGHT of raw image (high x)
        lm[PoseLandmark.LEFT_SHOULDER] = self._make_landmark(0.7, 0.3, 0)
        lm[PoseLandmark.RIGHT_SHOULDER] = self._make_landmark(0.3, 0.3, 0)
        # Elbows horizontally out from shoulders
        lm[PoseLandmark.LEFT_ELBOW] = self._make_landmark(0.9, 0.3, 0)
        lm[PoseLandmark.RIGHT_ELBOW] = self._make_landmark(0.1, 0.3, 0)
        # Wrists further out
        lm[PoseLandmark.LEFT_WRIST] = self._make_landmark(1.0, 0.3, 0)
        lm[PoseLandmark.RIGHT_WRIST] = self._make_landmark(0.0, 0.3, 0)
        # Hips below shoulders
        lm[PoseLandmark.LEFT_HIP] = self._make_landmark(0.6, 0.6, 0)
        lm[PoseLandmark.RIGHT_HIP] = self._make_landmark(0.4, 0.6, 0)
        # Knees below hips
        lm[PoseLandmark.LEFT_KNEE] = self._make_landmark(0.6, 0.8, 0)
        lm[PoseLandmark.RIGHT_KNEE] = self._make_landmark(0.4, 0.8, 0)
        # Ankles below knees
        lm[PoseLandmark.LEFT_ANKLE] = self._make_landmark(0.6, 1.0, 0)
        lm[PoseLandmark.RIGHT_ANKLE] = self._make_landmark(0.4, 1.0, 0)
        # Nose centered
        lm[PoseLandmark.NOSE] = self._make_landmark(0.5, 0.15, 0)
        return lm

    def test_signed_angle_2d_zero(self):
        """Same direction → 0 degrees."""
        angle = MediaPipeTracker._signed_angle_2d(0, 1, 0, 1)
        assert abs(angle) < 0.1

    def test_signed_angle_2d_perpendicular(self):
        """90° clockwise."""
        angle = MediaPipeTracker._signed_angle_2d(0, 1, 1, 0)
        assert abs(angle - (-90.0)) < 0.1

    def test_compute_body_angles_t_pose(self):
        tracker = MediaPipeTracker.__new__(MediaPipeTracker)
        lm = self._make_t_pose_landmarks()
        angles = tracker._compute_body_angles(lm)

        # In T-pose, shoulder angle should be near ±90 (arm horizontal)
        assert "left_shoulder" in angles
        assert "right_shoulder" in angles
        # Left arm extends left → negative angle
        assert angles["left_shoulder"] < -45
        # Right arm extends right → positive angle
        assert angles["right_shoulder"] > 45
        assert "left_elbow" in angles
        assert "right_elbow" in angles
        assert "body_lean" in angles
        assert "head_tilt" in angles
        assert "head_turn" in angles

    def test_compute_body_angles_arms_down(self):
        """Arms hanging straight down should give ~0 shoulder angle."""
        tracker = MediaPipeTracker.__new__(MediaPipeTracker)
        lm = self._make_t_pose_landmarks()
        # Move elbows below shoulders (arms down, raw frame coords)
        lm[PoseLandmark.LEFT_ELBOW] = self._make_landmark(0.68, 0.5, 0)
        lm[PoseLandmark.RIGHT_ELBOW] = self._make_landmark(0.32, 0.5, 0)
        lm[PoseLandmark.LEFT_WRIST] = self._make_landmark(0.67, 0.6, 0)
        lm[PoseLandmark.RIGHT_WRIST] = self._make_landmark(0.33, 0.6, 0)
        angles = tracker._compute_body_angles(lm)
        # Arms nearly parallel to torso → small angles
        assert abs(angles["left_shoulder"]) < 20
        assert abs(angles["right_shoulder"]) < 20

    def test_compute_body_angles_returns_upper_body_joints(self):
        tracker = MediaPipeTracker.__new__(MediaPipeTracker)
        lm = self._make_t_pose_landmarks()
        angles = tracker._compute_body_angles(lm)

        expected_keys = {
            "left_shoulder", "right_shoulder",
            "left_elbow", "right_elbow",
            "body_lean", "head_tilt", "head_turn",
        }
        assert expected_keys == set(angles.keys())

    def test_body_lean_upright_near_zero(self):
        tracker = MediaPipeTracker.__new__(MediaPipeTracker)
        lm = self._make_t_pose_landmarks()
        angles = tracker._compute_body_angles(lm)
        # Upright T-pose → body lean near 0
        assert abs(angles["body_lean"]) < 5.0

    def _make_upper_body_only_landmarks(self):
        """Create landmarks where lower body has low visibility (sitting).

        Uses raw (non-mirrored) frame coordinates.
        """
        lm = [None] * 33
        # Upper body — fully visible (raw frame: LEFT on right of image)
        lm[PoseLandmark.LEFT_SHOULDER] = self._make_landmark(0.7, 0.3, 0, vis=0.95)
        lm[PoseLandmark.RIGHT_SHOULDER] = self._make_landmark(0.3, 0.3, 0, vis=0.95)
        lm[PoseLandmark.LEFT_ELBOW] = self._make_landmark(0.85, 0.45, 0, vis=0.9)
        lm[PoseLandmark.RIGHT_ELBOW] = self._make_landmark(0.15, 0.45, 0, vis=0.9)
        lm[PoseLandmark.LEFT_WRIST] = self._make_landmark(0.9, 0.55, 0, vis=0.85)
        lm[PoseLandmark.RIGHT_WRIST] = self._make_landmark(0.1, 0.55, 0, vis=0.85)
        # Hips — partially visible (at bottom edge of frame)
        lm[PoseLandmark.LEFT_HIP] = self._make_landmark(0.6, 0.7, 0, vis=0.6)
        lm[PoseLandmark.RIGHT_HIP] = self._make_landmark(0.4, 0.7, 0, vis=0.6)
        # Lower body — off-screen / hallucinated (low visibility)
        lm[PoseLandmark.LEFT_KNEE] = self._make_landmark(0.6, 0.9, 0, vis=0.1)
        lm[PoseLandmark.RIGHT_KNEE] = self._make_landmark(0.4, 0.9, 0, vis=0.1)
        lm[PoseLandmark.LEFT_ANKLE] = self._make_landmark(0.6, 1.1, 0, vis=0.05)
        lm[PoseLandmark.RIGHT_ANKLE] = self._make_landmark(0.4, 1.1, 0, vis=0.05)
        # Nose
        lm[PoseLandmark.NOSE] = self._make_landmark(0.5, 0.15, 0, vis=0.99)
        return lm

    def test_upper_body_only_includes_visible_joints(self):
        """When sitting, upper body angles should still be computed."""
        tracker = MediaPipeTracker.__new__(MediaPipeTracker)
        lm = self._make_upper_body_only_landmarks()
        angles = tracker._compute_body_angles(lm)

        # Upper body joints should be present
        assert "left_shoulder" in angles
        assert "right_shoulder" in angles
        assert "left_elbow" in angles
        assert "right_elbow" in angles
        assert "head_tilt" in angles
        assert "head_turn" in angles
        assert "body_lean" in angles  # hips are vis=0.6, above threshold

    def test_upper_body_mode_excludes_lower_body(self):
        """Hip and knee angles are never computed in upper-body mode."""
        tracker = MediaPipeTracker.__new__(MediaPipeTracker)
        lm = self._make_t_pose_landmarks()  # full body visible
        angles = tracker._compute_body_angles(lm)

        assert "left_hip" not in angles
        assert "right_hip" not in angles
        assert "left_knee" not in angles
        assert "right_knee" not in angles

    def test_all_invisible_returns_empty(self):
        """If all landmarks are below threshold, return empty dict."""
        tracker = MediaPipeTracker.__new__(MediaPipeTracker)
        lm = [self._make_landmark(0.5, 0.5, 0, vis=0.1) for _ in range(33)]
        angles = tracker._compute_body_angles(lm)
        assert angles == {}

    def test_visibility_threshold(self):
        """Landmarks exactly at threshold should be accepted."""
        tracker = MediaPipeTracker.__new__(MediaPipeTracker)
        lm = self._make_t_pose_landmarks()
        # Set all to exactly threshold
        for i in range(33):
            if lm[i] is not None:
                lm[i].visibility = 0.5
        angles = tracker._compute_body_angles(lm)
        # Should still compute upper-body joints (0.5 >= 0.5)
        assert "left_shoulder" in angles
        assert "right_shoulder" in angles

    def test_none_visibility_treated_as_visible(self):
        """When visibility is None (Tasks API NormalizedLandmark), trust it."""
        tracker = MediaPipeTracker.__new__(MediaPipeTracker)
        lm = self._make_t_pose_landmarks()
        # Simulate NormalizedLandmark without visibility populated
        for i in range(33):
            if lm[i] is not None:
                lm[i].visibility = None
        angles = tracker._compute_body_angles(lm)
        # Upper-body joints should be present (None → trusted)
        assert "left_shoulder" in angles
        assert "right_shoulder" in angles
        assert "left_elbow" in angles
        assert "body_lean" in angles

    def test_missing_visibility_attr_treated_as_visible(self):
        """When visibility attr doesn't exist at all, trust the landmark."""
        tracker = MediaPipeTracker.__new__(MediaPipeTracker)
        # Create landmarks without visibility attribute
        class BareLandmark:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z
        lm = [None] * 33
        lm[PoseLandmark.LEFT_SHOULDER] = BareLandmark(0.3, 0.3, 0)
        lm[PoseLandmark.RIGHT_SHOULDER] = BareLandmark(0.7, 0.3, 0)
        lm[PoseLandmark.LEFT_ELBOW] = BareLandmark(0.1, 0.3, 0)
        lm[PoseLandmark.RIGHT_ELBOW] = BareLandmark(0.9, 0.3, 0)
        lm[PoseLandmark.LEFT_WRIST] = BareLandmark(0.0, 0.3, 0)
        lm[PoseLandmark.RIGHT_WRIST] = BareLandmark(1.0, 0.3, 0)
        lm[PoseLandmark.LEFT_HIP] = BareLandmark(0.4, 0.6, 0)
        lm[PoseLandmark.RIGHT_HIP] = BareLandmark(0.6, 0.6, 0)
        lm[PoseLandmark.LEFT_KNEE] = BareLandmark(0.4, 0.8, 0)
        lm[PoseLandmark.RIGHT_KNEE] = BareLandmark(0.6, 0.8, 0)
        lm[PoseLandmark.LEFT_ANKLE] = BareLandmark(0.4, 1.0, 0)
        lm[PoseLandmark.RIGHT_ANKLE] = BareLandmark(0.6, 1.0, 0)
        lm[PoseLandmark.NOSE] = BareLandmark(0.5, 0.15, 0)
        angles = tracker._compute_body_angles(lm)
        assert "left_shoulder" in angles
        assert "body_lean" in angles


# ===========================================================================
# RetargetMapper
# ===========================================================================

class TestRetargetMapper:
    """Tests for RetargetMapper face and body mapping."""

    def test_init_defaults(self):
        mapper = RetargetMapper()
        assert mapper.face_alpha == DEFAULT_FACE_ALPHA
        assert mapper.body_alpha == DEFAULT_BODY_ALPHA
        assert mapper.dead_zone == DEFAULT_DEAD_ZONE

    def test_map_face_no_detection(self):
        mapper = RetargetMapper()
        tf = TrackingFrame(face_detected=False)
        result = mapper.map_face(tf)
        assert result == {}

    def test_map_face_eye_blink(self):
        mapper = RetargetMapper(face_alpha=1.0, dead_zone=0.0)
        tf = TrackingFrame(
            face_detected=True,
            face_blendshapes={"eyeBlinkLeft": 0.8, "eyeBlinkRight": 0.2},
        )
        result = mapper.map_face(tf)
        assert abs(result["left_eye_openness"] - 0.2) < 0.01
        assert abs(result["right_eye_openness"] - 0.8) < 0.01

    def test_map_face_jaw_open(self):
        mapper = RetargetMapper(face_alpha=1.0, dead_zone=0.0)
        tf = TrackingFrame(
            face_detected=True,
            face_blendshapes={"jawOpen": 0.6},
        )
        result = mapper.map_face(tf)
        assert abs(result["jaw_open"] - 0.6) < 0.01
        assert abs(result["mouth_open"] - 0.6) < 0.01

    def test_map_face_smile_positive_curve(self):
        mapper = RetargetMapper(face_alpha=1.0, dead_zone=0.0)
        tf = TrackingFrame(
            face_detected=True,
            face_blendshapes={
                "mouthSmileLeft": 0.7,
                "mouthSmileRight": 0.7,
                "mouthFrownLeft": 0.0,
                "mouthFrownRight": 0.0,
            },
        )
        result = mapper.map_face(tf)
        assert result["mouth_curve"] > 0.5

    def test_map_face_frown_negative_curve(self):
        mapper = RetargetMapper(face_alpha=1.0, dead_zone=0.0)
        tf = TrackingFrame(
            face_detected=True,
            face_blendshapes={
                "mouthSmileLeft": 0.0,
                "mouthSmileRight": 0.0,
                "mouthFrownLeft": 0.8,
                "mouthFrownRight": 0.8,
            },
        )
        result = mapper.map_face(tf)
        assert result["mouth_curve"] < -0.5

    def test_map_face_brow_raise(self):
        mapper = RetargetMapper(face_alpha=1.0, dead_zone=0.0)
        tf = TrackingFrame(
            face_detected=True,
            face_blendshapes={
                "browOuterUpLeft": 0.9,
                "browDownLeft": 0.0,
                "browOuterUpRight": 0.1,
                "browDownRight": 0.5,
            },
        )
        result = mapper.map_face(tf)
        assert result["left_brow_raise"] > 0.5
        assert result["right_brow_raise"] < 0.0

    def test_map_face_lip_pucker(self):
        mapper = RetargetMapper(face_alpha=1.0, dead_zone=0.0)
        tf = TrackingFrame(
            face_detected=True,
            face_blendshapes={"mouthPucker": 0.75},
        )
        result = mapper.map_face(tf)
        assert abs(result["lip_pucker"] - 0.75) < 0.01

    def test_map_face_head_rotation(self):
        mapper = RetargetMapper(face_alpha=1.0, dead_zone=0.0)
        tf = TrackingFrame(
            face_detected=True,
            face_blendshapes={},
            head_yaw=20.0,
            head_roll=10.0,
        )
        result = mapper.map_face(tf)
        assert "head_tilt" in result
        assert "head_turn" in result
        assert result["head_turn"] != 0.0

    def test_map_face_sensitivity_multiplier(self):
        mapper = RetargetMapper(face_alpha=1.0, dead_zone=0.0)
        mapper.face_sensitivity["jaw_open"] = 2.0
        tf = TrackingFrame(
            face_detected=True,
            face_blendshapes={"jawOpen": 0.3},
        )
        result = mapper.map_face(tf)
        assert abs(result["jaw_open"] - 0.6) < 0.01

    def test_map_body_no_detection(self):
        mapper = RetargetMapper()
        tf = TrackingFrame(body_detected=False)
        result = mapper.map_body(tf)
        assert result == {}

    def test_map_body_passes_angles(self):
        mapper = RetargetMapper(body_alpha=1.0, dead_zone=0.0)
        tf = TrackingFrame(
            body_detected=True,
            body_angles={"left_shoulder": -45.0, "right_elbow": 30.0},
        )
        result = mapper.map_body(tf)
        assert abs(result["left_shoulder"] - (-45.0)) < 0.01
        assert abs(result["right_elbow"] - 30.0) < 0.01

    def test_map_body_sensitivity(self):
        mapper = RetargetMapper(body_alpha=1.0, dead_zone=0.0)
        mapper.body_sensitivity["left_shoulder"] = 0.5
        tf = TrackingFrame(
            body_detected=True,
            body_angles={"left_shoulder": -40.0},
        )
        result = mapper.map_body(tf)
        assert abs(result["left_shoulder"] - (-20.0)) < 0.01

    def test_smoothing_reduces_jitter(self):
        mapper = RetargetMapper(face_alpha=0.3, dead_zone=0.0)
        tf1 = TrackingFrame(
            face_detected=True,
            face_blendshapes={"jawOpen": 0.0},
        )
        tf2 = TrackingFrame(
            face_detected=True,
            face_blendshapes={"jawOpen": 1.0},
        )
        r1 = mapper.map_face(tf1)
        r2 = mapper.map_face(tf2)
        # With alpha=0.3, jump from 0→1 should be smoothed
        assert r2["jaw_open"] < 0.5  # smoothed, not instant

    def test_dead_zone_filters_small_changes(self):
        mapper = RetargetMapper(face_alpha=1.0, dead_zone=0.05)
        tf1 = TrackingFrame(
            face_detected=True,
            face_blendshapes={"jawOpen": 0.5},
        )
        tf2 = TrackingFrame(
            face_detected=True,
            face_blendshapes={"jawOpen": 0.52},
        )
        r1 = mapper.map_face(tf1)
        r2 = mapper.map_face(tf2)
        # Change of 0.02 is below dead_zone of 0.05 → should be same
        assert abs(r1["jaw_open"] - r2["jaw_open"]) < 0.001

    def test_reset_clears_state(self):
        mapper = RetargetMapper(face_alpha=0.5)
        tf = TrackingFrame(
            face_detected=True,
            face_blendshapes={"jawOpen": 0.8},
        )
        mapper.map_face(tf)
        assert len(mapper._face_smooth) > 0
        mapper.reset()
        assert len(mapper._face_smooth) == 0


# ===========================================================================
# MocapRecorder
# ===========================================================================

class TestMocapRecorder:
    """Tests for MocapRecorder record/bake/save/load."""

    def test_init(self):
        rec = MocapRecorder()
        assert rec.scene_fps == 30
        assert rec.is_recording is False
        assert rec.frame_count == 0
        assert rec.duration == 0.0

    def test_start_stop(self):
        rec = MocapRecorder()
        rec.start()
        assert rec.is_recording is True
        rec.stop()
        assert rec.is_recording is False

    def test_add_frame(self):
        rec = MocapRecorder()
        rec.start()
        tf = TrackingFrame(timestamp=1.0)
        rec.add_frame(tf)
        assert rec.frame_count == 1

    def test_add_frame_not_recording(self):
        rec = MocapRecorder()
        tf = TrackingFrame(timestamp=1.0)
        rec.add_frame(tf)
        assert rec.frame_count == 0

    def test_duration(self):
        rec = MocapRecorder()
        rec.start()
        rec.add_frame(TrackingFrame(timestamp=10.0))
        rec.add_frame(TrackingFrame(timestamp=11.0))
        rec.add_frame(TrackingFrame(timestamp=12.0))
        assert abs(rec.duration - 2.0) < 0.01

    def test_bake_to_clip_empty(self):
        rec = MocapRecorder()
        clip = rec.bake_to_clip()
        assert clip is None

    def test_bake_to_clip_with_face_data(self):
        rec = MocapRecorder(scene_fps=30)
        rec.start()
        for i in range(10):
            tf = TrackingFrame(
                timestamp=i / 30.0,
                face_detected=True,
                face_blendshapes={"jawOpen": i * 0.1},
            )
            rec.add_frame(tf)
        rec.stop()

        clip = rec.bake_to_clip(character_name="TestChar")
        assert clip is not None
        assert clip.name.startswith("Mocap_")
        assert len(clip.tracks) > 0

    def test_bake_to_clip_with_body_data(self):
        rec = MocapRecorder(scene_fps=30)
        rec.start()
        for i in range(10):
            tf = TrackingFrame(
                timestamp=i / 30.0,
                body_detected=True,
                body_angles={"left_shoulder": -30.0 + i},
            )
            rec.add_frame(tf)
        rec.stop()

        clip = rec.bake_to_clip(character_name="TestChar")
        assert clip is not None
        # Should have body tracks
        body_tracks = [
            t for t in clip.tracks.values()
            if "body." in t.property_name
        ]
        assert len(body_tracks) > 0

    def test_save_load_roundtrip(self):
        rec = MocapRecorder(scene_fps=24)
        rec.start()
        rec.add_frame(TrackingFrame(
            timestamp=1.0,
            face_detected=True,
            face_blendshapes={"jawOpen": 0.5, "eyeBlinkLeft": 0.3},
            head_pitch=5.0, head_yaw=-10.0, head_roll=2.0,
        ))
        rec.add_frame(TrackingFrame(
            timestamp=1.033,
            body_detected=True,
            body_angles={"left_shoulder": -30.0, "right_elbow": 15.0},
        ))
        rec.stop()

        with tempfile.NamedTemporaryFile(suffix=".onyx-mocap", delete=False, mode="w") as f:
            tmpfile = f.name

        try:
            rec.save(tmpfile)
            assert os.path.isfile(tmpfile)

            # Verify JSON structure
            with open(tmpfile) as f:
                data = json.load(f)
            assert data["version"] == 1
            assert data["scene_fps"] == 24
            assert data["frame_count"] == 2

            # Load into new recorder
            rec2 = MocapRecorder()
            ok = rec2.load(tmpfile)
            assert ok is True
            assert rec2.frame_count == 2
            assert rec2.scene_fps == 24
        finally:
            os.unlink(tmpfile)

    def test_load_invalid_file(self):
        rec = MocapRecorder()
        ok = rec.load("/nonexistent/path.onyx-mocap")
        assert ok is False

    def test_start_with_audio_flag(self):
        rec = MocapRecorder()
        rec.start(record_audio=True)
        assert rec._record_audio is True
        rec.stop()


# ===========================================================================
# MocapState
# ===========================================================================

class TestMocapState:
    """Tests for MocapState enum."""

    def test_values(self):
        assert MocapState.STOPPED.value == "stopped"
        assert MocapState.PREVIEWING.value == "previewing"
        assert MocapState.RECORDING.value == "recording"


# ===========================================================================
# WebcamMocap (orchestrator)
# ===========================================================================

class TestWebcamMocap:
    """Tests for WebcamMocap orchestrator (mocked dependencies)."""

    def test_init_defaults(self):
        mocap = WebcamMocap()
        assert mocap.state == MocapState.STOPPED
        assert mocap.is_active is False
        assert mocap.is_recording is False
        assert mocap.latest_frame is None

    def test_init_custom(self):
        mocap = WebcamMocap(
            camera_index=2,
            enable_face=False,
            enable_pose=True,
        )
        assert mocap.camera_index == 2
        assert mocap.enable_face is False
        assert mocap.enable_pose is True

    def test_get_stats_when_stopped(self):
        mocap = WebcamMocap()
        stats = mocap.get_stats()
        assert stats["state"] == "stopped"
        assert stats["face_detected"] is False
        assert stats["body_detected"] is False

    def test_stop_when_stopped(self):
        mocap = WebcamMocap()
        mocap.stop()  # Should not raise
        assert mocap.state == MocapState.STOPPED

    def test_start_recording_requires_preview(self):
        mocap = WebcamMocap()
        mocap.start_recording()  # Should be a no-op (not previewing)
        assert mocap.state == MocapState.STOPPED

    def test_stop_recording_when_not_recording(self):
        mocap = WebcamMocap()
        mocap.stop_recording()  # Should not raise
        assert mocap.state == MocapState.STOPPED

    def test_bake_empty_returns_none(self):
        mocap = WebcamMocap()
        clip = mocap.bake_to_clip()
        assert clip is None

    def test_set_character(self):
        mocap = WebcamMocap()
        mock_char = MagicMock()
        mocap.set_character(mock_char)
        assert mocap._character is mock_char

    def test_get_webcam_frame_when_stopped(self):
        mocap = WebcamMocap()
        assert mocap.get_webcam_frame() is None

    def test_recorder_property(self):
        mocap = WebcamMocap()
        assert isinstance(mocap.recorder, MocapRecorder)

    def test_mapper_property(self):
        mocap = WebcamMocap()
        assert isinstance(mocap.mapper, RetargetMapper)

    def test_capture_property(self):
        mocap = WebcamMocap()
        assert isinstance(mocap.capture, WebcamCapture)

    def test_state_callback(self):
        states = []
        mocap = WebcamMocap()
        mocap.on_state_change = lambda s: states.append(s)
        mocap._set_state(MocapState.PREVIEWING)
        mocap._set_state(MocapState.RECORDING)
        mocap._set_state(MocapState.STOPPED)
        assert states == [
            MocapState.PREVIEWING,
            MocapState.RECORDING,
            MocapState.STOPPED,
        ]

    def test_apply_to_character_face(self):
        """Test that face data gets applied to character's face_ctrl."""
        mocap = WebcamMocap()
        mocap._mapper = RetargetMapper(face_alpha=1.0, dead_zone=0.0)

        char = MagicMock()
        char.face_ctrl = MagicMock()
        char.face = MagicMock()
        char.body = MagicMock()
        mocap._character = char

        tf = TrackingFrame(
            face_detected=True,
            face_blendshapes={"jawOpen": 0.7},
            body_detected=False,
        )
        mocap._apply_to_character(tf)

        # face_ctrl.apply_timeline_values should have been called
        char.face_ctrl.apply_timeline_values.assert_called_once()
        char.face_ctrl.apply_to_face.assert_called_once_with(char.face)

    def test_apply_to_character_body(self):
        """Test that body data gets applied to character's body targets."""
        mocap = WebcamMocap()
        mocap._mapper = RetargetMapper(body_alpha=1.0, dead_zone=0.0)

        char = MagicMock()
        char.face_ctrl = MagicMock()
        char.face = None
        char.body = MagicMock()
        mocap._character = char

        tf = TrackingFrame(
            face_detected=False,
            body_detected=True,
            body_angles={"left_shoulder": -30.0},
        )
        mocap._apply_to_character(tf)

        char.body.set_targets.assert_called_once()

    def test_apply_to_character_none(self):
        """No error when character is None."""
        mocap = WebcamMocap()
        mocap._character = None
        tf = TrackingFrame(face_detected=True)
        mocap._apply_to_character(tf)  # Should not raise
