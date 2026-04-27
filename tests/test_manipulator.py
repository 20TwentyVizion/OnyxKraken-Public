"""Tests for face.stage.manipulator — gizmo system, FK/IK overlay, bone hit testing."""

import math
import pytest

from face.stage.manipulator import (
    ManipulatorGizmo, GizmoMode, GizmoColors, GizmoHit,
    FKIKOverlay, FKIKButton,
    bone_line_hit_test, KeyedStateTracker,
    draw_autokey_indicator, draw_mode_indicator,
)


# ---------------------------------------------------------------------------
# Helpers — stub canvas
# ---------------------------------------------------------------------------

class StubCanvas:
    """Minimal canvas stub for testing draw/clear calls."""

    def __init__(self):
        self.items = []
        self.deleted_tags = []

    def create_oval(self, *a, **kw):
        self.items.append(("oval", a, kw))
        return len(self.items)

    def create_line(self, *a, **kw):
        self.items.append(("line", a, kw))
        return len(self.items)

    def create_text(self, *a, **kw):
        self.items.append(("text", a, kw))
        return len(self.items)

    def create_rectangle(self, *a, **kw):
        self.items.append(("rect", a, kw))
        return len(self.items)

    def create_polygon(self, *a, **kw):
        self.items.append(("poly", a, kw))
        return len(self.items)

    def delete(self, tag):
        self.deleted_tags.append(tag)

    def winfo_width(self):
        return 1600


# ---------------------------------------------------------------------------
# GizmoMode
# ---------------------------------------------------------------------------

class TestGizmoMode:
    def test_enum_values(self):
        assert GizmoMode.MOVE is not GizmoMode.ROTATE
        assert GizmoMode.ROTATE is not GizmoMode.SCALE
        assert len(GizmoMode) == 3


# ---------------------------------------------------------------------------
# ManipulatorGizmo — init and mode
# ---------------------------------------------------------------------------

class TestManipulatorGizmoInit:
    def test_default_mode(self):
        g = ManipulatorGizmo(StubCanvas())
        assert g.mode == GizmoMode.ROTATE

    def test_set_mode(self):
        g = ManipulatorGizmo(StubCanvas())
        g.mode = GizmoMode.MOVE
        assert g.mode == GizmoMode.MOVE

    def test_cycle_forward(self):
        g = ManipulatorGizmo(StubCanvas())
        g.mode = GizmoMode.MOVE
        m = g.cycle_mode(forward=True)
        assert m == GizmoMode.ROTATE
        m = g.cycle_mode(forward=True)
        assert m == GizmoMode.SCALE
        m = g.cycle_mode(forward=True)
        assert m == GizmoMode.MOVE  # wraps

    def test_cycle_backward(self):
        g = ManipulatorGizmo(StubCanvas())
        g.mode = GizmoMode.MOVE
        m = g.cycle_mode(forward=False)
        assert m == GizmoMode.SCALE

    def test_not_visible_draw_clears(self):
        cv = StubCanvas()
        g = ManipulatorGizmo(cv)
        g.visible = False
        g.draw(100, 100, angle=45)
        # Should only clear, not draw
        assert ManipulatorGizmo.GIZMO_TAG in cv.deleted_tags
        assert len(cv.items) == 0


# ---------------------------------------------------------------------------
# ManipulatorGizmo — drawing
# ---------------------------------------------------------------------------

class TestManipulatorGizmoDraw:
    def test_draw_rotate(self):
        cv = StubCanvas()
        g = ManipulatorGizmo(cv)
        g.mode = GizmoMode.ROTATE
        g.draw(200, 200, angle=30, joint_name="left_shoulder")
        assert len(cv.items) > 0
        # Should have ring (oval), line, handle (oval), center (oval), text
        types = [item[0] for item in cv.items]
        assert "oval" in types
        assert "line" in types
        assert "text" in types

    def test_draw_move(self):
        cv = StubCanvas()
        g = ManipulatorGizmo(cv)
        g.mode = GizmoMode.MOVE
        g.draw(200, 200, joint_name="head")
        types = [item[0] for item in cv.items]
        assert "line" in types  # arrows
        assert "oval" in types  # center dot

    def test_draw_scale(self):
        cv = StubCanvas()
        g = ManipulatorGizmo(cv)
        g.mode = GizmoMode.SCALE
        g.draw(200, 200, scale=1.5, joint_name="body")
        types = [item[0] for item in cv.items]
        assert "line" in types  # scale lines
        assert "rect" in types  # box handles
        assert "poly" in types  # diamond

    def test_clear(self):
        cv = StubCanvas()
        g = ManipulatorGizmo(cv)
        g.draw(100, 100)
        g.clear()
        assert ManipulatorGizmo.GIZMO_TAG in cv.deleted_tags


# ---------------------------------------------------------------------------
# ManipulatorGizmo — hit testing
# ---------------------------------------------------------------------------

class TestManipulatorGizmoHitTest:
    def test_rotate_ring_hit(self):
        g = ManipulatorGizmo(StubCanvas())
        g.draw(200, 200, angle=0)
        hit = g.hit_test(200 + 40, 200)  # on the ring
        assert hit.hit
        assert hit.component in ("ring", "handle")

    def test_rotate_miss(self):
        g = ManipulatorGizmo(StubCanvas())
        g.draw(200, 200, angle=0)
        hit = g.hit_test(400, 400)  # far away
        assert not hit.hit

    def test_move_x_axis_hit(self):
        g = ManipulatorGizmo(StubCanvas())
        g.mode = GizmoMode.MOVE
        g.draw(200, 200)
        hit = g.hit_test(225, 200)  # on X arrow
        assert hit.hit
        assert hit.component == "x_axis"

    def test_move_y_axis_hit(self):
        g = ManipulatorGizmo(StubCanvas())
        g.mode = GizmoMode.MOVE
        g.draw(200, 200)
        hit = g.hit_test(200, 175)  # on Y arrow (up)
        assert hit.hit
        assert hit.component == "y_axis"

    def test_scale_x_handle_hit(self):
        g = ManipulatorGizmo(StubCanvas())
        g.mode = GizmoMode.SCALE
        g.draw(200, 200, scale=1.0)
        hit = g.hit_test(200 + g.scale_length, 200)  # X box handle
        assert hit.hit
        assert hit.component == "scale_x"

    def test_scale_uniform_hit(self):
        g = ManipulatorGizmo(StubCanvas())
        g.mode = GizmoMode.SCALE
        g.draw(200, 200, scale=1.0)
        hit = g.hit_test(200, 200)  # center diamond
        assert hit.hit
        assert hit.component == "scale_uniform"

    def test_not_visible_no_hit(self):
        g = ManipulatorGizmo(StubCanvas())
        g.visible = False
        hit = g.hit_test(200, 200)
        assert not hit.hit


# ---------------------------------------------------------------------------
# ManipulatorGizmo — drag
# ---------------------------------------------------------------------------

class TestManipulatorGizmoDrag:
    def test_rotate_drag(self):
        g = ManipulatorGizmo(StubCanvas())
        g.mode = GizmoMode.ROTATE
        g.draw(200, 200, angle=0)
        g.start_drag(200 + 40, 200, "ring", current_value=0.0)
        assert g.dragging
        result = g.compute_drag(200, 200 + 40)
        assert "angle" in result
        assert "delta" in result

    def test_move_drag_x_constrained(self):
        g = ManipulatorGizmo(StubCanvas())
        g.mode = GizmoMode.MOVE
        g.draw(200, 200)
        g.start_drag(200, 200, "x_axis", current_values=(100.0, 50.0))
        result = g.compute_drag(220, 210)
        assert result["dy"] == 0  # Y constrained
        assert result["y"] == 50.0  # Y unchanged

    def test_move_drag_y_constrained(self):
        g = ManipulatorGizmo(StubCanvas())
        g.mode = GizmoMode.MOVE
        g.draw(200, 200)
        g.start_drag(200, 200, "y_axis", current_values=(100.0, 50.0))
        result = g.compute_drag(210, 180)
        assert result["dx"] == 0  # X constrained
        assert result["x"] == 100.0  # X unchanged

    def test_move_drag_free(self):
        g = ManipulatorGizmo(StubCanvas())
        g.mode = GizmoMode.MOVE
        g.draw(200, 200)
        g.start_drag(200, 200, "free", current_values=(100.0, 50.0))
        result = g.compute_drag(220, 210)
        assert result["dx"] == 20
        assert result["dy"] == 10

    def test_scale_drag(self):
        g = ManipulatorGizmo(StubCanvas())
        g.mode = GizmoMode.SCALE
        g.draw(200, 200, scale=1.0)
        g.start_drag(240, 200, "scale_x", current_value=1.0)
        result = g.compute_drag(290, 200)  # drag 50px right
        assert "scale" in result
        assert result["scale"] > 1.0

    def test_end_drag(self):
        g = ManipulatorGizmo(StubCanvas())
        g.start_drag(100, 100, "ring", current_value=0)
        assert g.dragging
        g.end_drag()
        assert not g.dragging
        assert g.drag_component == ""

    def test_no_result_when_not_dragging(self):
        g = ManipulatorGizmo(StubCanvas())
        result = g.compute_drag(100, 100)
        assert result == {}


# ---------------------------------------------------------------------------
# ManipulatorGizmo — effective radius
# ---------------------------------------------------------------------------

class TestEffectiveRadius:
    def test_default_zoom(self):
        g = ManipulatorGizmo(StubCanvas())
        g._zoom = 1.0
        r = g.effective_radius
        assert g.min_gizmo_size <= r <= g.max_gizmo_size

    def test_zoomed_in(self):
        g = ManipulatorGizmo(StubCanvas())
        g._zoom = 3.0
        r = g.effective_radius
        assert r >= g.min_gizmo_size

    def test_zoomed_out(self):
        g = ManipulatorGizmo(StubCanvas())
        g._zoom = 0.3
        r = g.effective_radius
        assert r <= g.max_gizmo_size


# ---------------------------------------------------------------------------
# FKIKOverlay
# ---------------------------------------------------------------------------

class TestFKIKOverlay:
    def test_init(self):
        overlay = FKIKOverlay(StubCanvas())
        assert overlay.visible
        assert len(overlay.buttons) == 0

    def test_draw_buttons(self):
        cv = StubCanvas()
        overlay = FKIKOverlay(cv)
        joints = {
            "left_elbow": (100, 200, 45),
            "right_elbow": (300, 200, -30),
            "left_knee": (150, 400, 10),
            "right_knee": (250, 400, -5),
        }
        ik_states = {
            "left_arm": False,
            "right_arm": True,
            "left_leg": False,
            "right_leg": False,
        }
        overlay.draw(joints, ik_states)
        assert len(overlay.buttons) == 4
        assert overlay.buttons["right_arm"].is_ik is True
        assert overlay.buttons["left_arm"].is_ik is False

    def test_hit_test(self):
        cv = StubCanvas()
        overlay = FKIKOverlay(cv)
        joints = {"left_elbow": (100, 200, 0)}
        ik_states = {"left_arm": False}
        overlay.draw(joints, ik_states)
        btn = overlay.buttons["left_arm"]
        # Hit inside button
        result = overlay.hit_test(btn.screen_x + 10, btn.screen_y + 5)
        assert result == "left_arm"

    def test_hit_miss(self):
        cv = StubCanvas()
        overlay = FKIKOverlay(cv)
        joints = {"left_elbow": (100, 200, 0)}
        ik_states = {"left_arm": False}
        overlay.draw(joints, ik_states)
        result = overlay.hit_test(900, 900)
        assert result is None

    def test_clear(self):
        cv = StubCanvas()
        overlay = FKIKOverlay(cv)
        overlay.clear()
        assert FKIKOverlay.OVERLAY_TAG in cv.deleted_tags

    def test_not_visible(self):
        cv = StubCanvas()
        overlay = FKIKOverlay(cv)
        overlay.visible = False
        joints = {"left_elbow": (100, 200, 0)}
        ik_states = {"left_arm": False}
        overlay.draw(joints, ik_states)
        assert len(overlay.buttons) == 0


# ---------------------------------------------------------------------------
# bone_line_hit_test
# ---------------------------------------------------------------------------

class TestBoneLineHitTest:
    def test_hit_on_bone(self):
        joints = {
            "left_shoulder": (100, 100, 0),
            "left_elbow": (100, 200, 0),
        }
        bones = [("left_shoulder", "left_elbow")]
        result = bone_line_hit_test(102, 150, joints, bones, tolerance=8)
        assert result == "left_shoulder"

    def test_miss_far_away(self):
        joints = {
            "left_shoulder": (100, 100, 0),
            "left_elbow": (100, 200, 0),
        }
        bones = [("left_shoulder", "left_elbow")]
        result = bone_line_hit_test(500, 500, joints, bones)
        assert result is None

    def test_closest_bone_wins(self):
        joints = {
            "left_shoulder": (100, 100, 0),
            "left_elbow": (100, 200, 0),
            "right_shoulder": (300, 100, 0),
            "right_elbow": (300, 200, 0),
        }
        bones = [
            ("left_shoulder", "left_elbow"),
            ("right_shoulder", "right_elbow"),
        ]
        # Click near left bone
        result = bone_line_hit_test(103, 150, joints, bones)
        assert result == "left_shoulder"
        # Click near right bone
        result = bone_line_hit_test(298, 150, joints, bones)
        assert result == "right_shoulder"

    def test_missing_joints(self):
        joints = {"left_shoulder": (100, 100, 0)}
        bones = [("left_shoulder", "missing_joint")]
        result = bone_line_hit_test(100, 100, joints, bones)
        assert result is None

    def test_empty_inputs(self):
        result = bone_line_hit_test(100, 100, {}, [])
        assert result is None


# ---------------------------------------------------------------------------
# KeyedStateTracker
# ---------------------------------------------------------------------------

class _FakeKeyframe:
    def __init__(self, frame):
        self.frame = frame

class _FakeTrack:
    def __init__(self, char_name, prop, keyed_frames):
        self.char_name = char_name
        self.prop = prop
        self.keyframes = [_FakeKeyframe(f) for f in keyed_frames]


class TestKeyedStateTracker:
    def test_empty(self):
        t = KeyedStateTracker()
        assert not t.is_keyed("onyx", "body.left_shoulder")

    def test_update_and_query(self):
        tracks = [
            _FakeTrack("onyx", "body.left_shoulder", [0, 10, 20]),
            _FakeTrack("onyx", "body.right_shoulder", [5, 15]),
        ]
        t = KeyedStateTracker()
        t.update(tracks, 10)
        assert t.is_keyed("onyx", "body.left_shoulder")
        assert not t.is_keyed("onyx", "body.right_shoulder")

    def test_any_keyed(self):
        tracks = [_FakeTrack("onyx", "body.head_tilt", [30])]
        t = KeyedStateTracker()
        t.update(tracks, 30)
        assert t.any_keyed("onyx")
        assert not t.any_keyed("xyno")

    def test_joint_color_keyed(self):
        tracks = [_FakeTrack("onyx", "body.left_shoulder", [5])]
        t = KeyedStateTracker()
        t.update(tracks, 5)
        assert t.get_joint_color("onyx", "left_shoulder") == GizmoColors.KEYED

    def test_joint_color_not_keyed(self):
        tracks = [_FakeTrack("onyx", "body.left_shoulder", [5])]
        t = KeyedStateTracker()
        t.update(tracks, 10)  # frame 10 not keyed
        color = t.get_joint_color("onyx", "left_shoulder", default="#aabbcc")
        assert color == "#aabbcc"

    def test_unknown_joint(self):
        t = KeyedStateTracker()
        t.update([], 0)
        color = t.get_joint_color("onyx", "nonexistent", default="#123456")
        assert color == "#123456"


# ---------------------------------------------------------------------------
# HUD helpers (just test they don't crash — they draw to canvas)
# ---------------------------------------------------------------------------

class TestHUDHelpers:
    def test_autokey_indicator_on(self):
        cv = StubCanvas()
        draw_autokey_indicator(cv, True, 10, 10)
        assert len(cv.items) > 0

    def test_autokey_indicator_off(self):
        cv = StubCanvas()
        draw_autokey_indicator(cv, False, 10, 10)
        assert len(cv.items) == 0  # nothing drawn when off

    def test_mode_indicator(self):
        cv = StubCanvas()
        draw_mode_indicator(cv, GizmoMode.ROTATE, 10, 10)
        assert len(cv.items) > 0
        # Check text contains ROTATE
        text_items = [i for i in cv.items if i[0] == "text"]
        assert len(text_items) == 1


# ---------------------------------------------------------------------------
# GizmoColors — sanity check constants exist
# ---------------------------------------------------------------------------

class TestGizmoColors:
    def test_axis_colors(self):
        assert GizmoColors.X_AXIS.startswith("#")
        assert GizmoColors.Y_AXIS.startswith("#")

    def test_keyed_colors(self):
        assert GizmoColors.KEYED != GizmoColors.NOT_KEYED

    def test_fk_ik_colors(self):
        assert GizmoColors.FK_COLOR != GizmoColors.IK_COLOR
