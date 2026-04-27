"""Tests for the render backend abstraction and Pygame renderer.

Covers:
  - PygameRenderer primitive drawing (oval, rect, line, polygon, text)
  - Catmull-Rom spline smoothing
  - Surface management (begin/end frame, resize)
  - FaceCanvas adapter dispatch (Tk fallback vs Pygame routing)
  - PygameViewport initialization and present cycle
"""

import math
import os
import sys
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# PygameRenderer tests (no Tk required)
# ---------------------------------------------------------------------------

class TestPygameRenderer(unittest.TestCase):
    """Test PygameRenderer primitive operations."""

    @classmethod
    def setUpClass(cls):
        import pygame
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()

    def _make(self, w=200, h=150):
        from face.render_backend import PygameRenderer
        return PygameRenderer(width=w, height=h)

    def test_get_size(self):
        r = self._make(400, 360)
        self.assertEqual(r.get_size(), (400, 360))

    def test_begin_frame_clears_surface(self):
        r = self._make(100, 100)
        # Draw something, then begin_frame should clear
        r.draw_rectangle(0, 0, 100, 100, fill="#ff0000")
        r.begin_frame("#000000")
        # Sample a pixel — should be black after clear
        import pygame
        color = r.surface.get_at((50, 50))
        self.assertEqual((color.r, color.g, color.b), (0, 0, 0))

    def test_draw_oval_fill(self):
        r = self._make(100, 100)
        r.begin_frame("#000000")
        r.draw_oval(10, 10, 90, 90, fill="#ff0000")
        import pygame
        # Center pixel should be red
        color = r.surface.get_at((50, 50))
        self.assertGreater(color.r, 200)

    def test_draw_oval_outline_only(self):
        r = self._make(100, 100)
        r.begin_frame("#000000")
        r.draw_oval(10, 10, 90, 90, outline="#00ff00", width=2)
        # Center should still be black (no fill)
        import pygame
        color = r.surface.get_at((50, 50))
        self.assertEqual(color.r, 0)

    def test_draw_oval_empty_strings_no_crash(self):
        r = self._make(100, 100)
        r.begin_frame("#000000")
        # Empty fill and outline should not crash
        r.draw_oval(10, 10, 90, 90, fill="", outline="")

    def test_draw_oval_tiny_no_crash(self):
        r = self._make(100, 100)
        r.begin_frame("#000000")
        # Very small oval (radius < 1)
        r.draw_oval(50, 50, 50.5, 50.5, fill="#ffffff")

    def test_draw_rectangle_fill(self):
        r = self._make(100, 100)
        r.begin_frame("#000000")
        r.draw_rectangle(20, 20, 80, 80, fill="#0000ff")
        import pygame
        color = r.surface.get_at((50, 50))
        self.assertGreater(color.b, 200)

    def test_draw_rectangle_outline(self):
        r = self._make(100, 100)
        r.begin_frame("#000000")
        r.draw_rectangle(20, 20, 80, 80, outline="#00ff00", width=2)
        # Inside should still be black
        import pygame
        color = r.surface.get_at((50, 50))
        self.assertEqual(color.r, 0)

    def test_draw_line_two_points(self):
        r = self._make(100, 100)
        r.begin_frame("#000000")
        r.draw_line([(0, 50), (100, 50)], color="#ffffff", width=3)
        import pygame
        color = r.surface.get_at((50, 50))
        self.assertGreater(color.r, 200)

    def test_draw_line_multiple_points(self):
        r = self._make(100, 100)
        r.begin_frame("#000000")
        pts = [(10, 10), (50, 90), (90, 10)]
        r.draw_line(pts, color="#ff00ff", width=2)
        # Should not crash, line passes through middle area

    def test_draw_line_smooth(self):
        r = self._make(200, 200)
        r.begin_frame("#000000")
        pts = [(10, 100), (60, 20), (120, 180), (190, 50)]
        r.draw_line(pts, color="#00ffff", width=2, smooth=True)
        # Smooth curve should render without error

    def test_draw_line_single_point_no_crash(self):
        r = self._make(100, 100)
        r.begin_frame("#000000")
        r.draw_line([(50, 50)], color="#ffffff", width=1)

    def test_draw_polygon_filled(self):
        r = self._make(100, 100)
        r.begin_frame("#000000")
        pts = [(50, 10), (90, 90), (10, 90)]
        r.draw_polygon(pts, fill="#ffff00")
        import pygame
        # Center of triangle should be yellow
        color = r.surface.get_at((50, 60))
        self.assertGreater(color.r, 150)
        self.assertGreater(color.g, 150)

    def test_draw_polygon_outline_only(self):
        r = self._make(100, 100)
        r.begin_frame("#000000")
        pts = [(50, 10), (90, 90), (10, 90)]
        r.draw_polygon(pts, outline="#00ff00", width=2)

    def test_draw_polygon_too_few_points(self):
        r = self._make(100, 100)
        r.begin_frame("#000000")
        # Less than 3 points — should not crash
        r.draw_polygon([(10, 10), (50, 50)], fill="#ff0000")

    def test_draw_text(self):
        r = self._make(200, 100)
        r.begin_frame("#000000")
        r.draw_text(100, 50, "Hello", color="#ffffff",
                     font_family="Consolas", font_size=16)
        # Text should be rendered — check center area has non-black pixels
        import pygame
        found_white = False
        for x in range(80, 120):
            color = r.surface.get_at((x, 50))
            if color.r > 100:
                found_white = True
                break
        self.assertTrue(found_white, "Text should render non-black pixels")

    def test_draw_text_anchors(self):
        r = self._make(200, 100)
        r.begin_frame("#000000")
        for anchor in ("center", "nw", "n", "ne", "w", "e", "sw", "s", "se"):
            r.draw_text(100, 50, "X", color="#ffffff",
                         font_family="Arial", font_size=12, anchor=anchor)

    def test_draw_image_pygame_surface(self):
        import pygame
        r = self._make(200, 200)
        r.begin_frame("#000000")
        img = pygame.Surface((50, 50))
        img.fill((255, 0, 0))
        r.draw_image(100, 100, img, anchor="center")
        color = r.surface.get_at((100, 100))
        self.assertGreater(color.r, 200)

    def test_surface_property(self):
        import pygame
        r = self._make(100, 100)
        self.assertIsInstance(r.surface, pygame.Surface)
        # Replace surface
        new_surf = pygame.Surface((200, 200), pygame.SRCALPHA)
        r.surface = new_surf
        self.assertEqual(r.get_size(), (200, 200))

    def test_end_frame_no_crash(self):
        r = self._make(100, 100)
        r.begin_frame("#000000")
        r.end_frame()


# ---------------------------------------------------------------------------
# Catmull-Rom spline tests
# ---------------------------------------------------------------------------

class TestCatmullRom(unittest.TestCase):
    def test_basic_spline(self):
        from face.render_backend import _catmull_rom
        pts = [(0, 0), (50, 100), (100, 0), (150, 100)]
        result = _catmull_rom(pts, segments_per_span=4)
        self.assertGreater(len(result), len(pts))
        # First point should be near (0,0) or (50,100) depending on phantom
        # Last point should be the last real point
        self.assertEqual(result[-1], pts[-1])

    def test_two_points_returns_input(self):
        from face.render_backend import _catmull_rom
        pts = [(0, 0), (100, 100)]
        result = _catmull_rom(pts)
        self.assertEqual(result, pts)

    def test_single_point_returns_input(self):
        from face.render_backend import _catmull_rom
        pts = [(50, 50)]
        result = _catmull_rom(pts)
        self.assertEqual(result, pts)


# ---------------------------------------------------------------------------
# Color conversion tests
# ---------------------------------------------------------------------------

class TestColorConversion(unittest.TestCase):
    def test_hex_to_rgb(self):
        from face.render_backend import _hex_to_rgb
        self.assertEqual(_hex_to_rgb("#ff0000"), (255, 0, 0))
        self.assertEqual(_hex_to_rgb("#00ff00"), (0, 255, 0))
        self.assertEqual(_hex_to_rgb("#0000ff"), (0, 0, 255))
        self.assertEqual(_hex_to_rgb("000000"), (0, 0, 0))

    def test_hex_to_rgba(self):
        from face.render_backend import _hex_to_rgba
        self.assertEqual(_hex_to_rgba("#ff8040"), (255, 128, 64, 255))
        self.assertEqual(_hex_to_rgba("#ff8040", 128), (255, 128, 64, 128))


# ---------------------------------------------------------------------------
# FaceCanvas adapter dispatch tests (mock-based, no real Tk window)
# ---------------------------------------------------------------------------

class TestFaceCanvasDispatch(unittest.TestCase):
    """Test that FaceCanvas draw adapters correctly dispatch to renderer."""

    def _make_mock_face(self):
        """Create a FaceCanvas-like object with dispatch methods for testing."""
        from face.render_backend import PygameRenderer
        import tkinter as tk

        # We can't create a real FaceCanvas without a Tk root, so test
        # the dispatch logic by importing and calling the adapter methods
        # on a mock object that has the same attributes.
        renderer = PygameRenderer(width=400, height=360)

        class MockFace:
            _use_pygame = True
            _r = renderer
            _viewport = MagicMock()

        # Import the actual adapter methods from FaceCanvas and bind them
        from face.face_gui import FaceCanvas
        face = MockFace()
        face._d_oval = FaceCanvas._d_oval.__get__(face, MockFace)
        face._d_rect = FaceCanvas._d_rect.__get__(face, MockFace)
        face._d_line = FaceCanvas._d_line.__get__(face, MockFace)
        face._d_polygon = FaceCanvas._d_polygon.__get__(face, MockFace)
        face._d_text = FaceCanvas._d_text.__get__(face, MockFace)
        face._begin_draw = FaceCanvas._begin_draw.__get__(face, MockFace)
        face._end_draw = FaceCanvas._end_draw.__get__(face, MockFace)
        return face, renderer

    def test_d_oval_routes_to_pygame(self):
        face, r = self._make_mock_face()
        r.begin_frame("#000000")
        face._d_oval(10, 10, 90, 90, fill="#ff0000", outline="#ffffff", width=2)
        import pygame
        color = r.surface.get_at((50, 50))
        self.assertGreater(color.r, 200)

    def test_d_rect_routes_to_pygame(self):
        face, r = self._make_mock_face()
        r.begin_frame("#000000")
        face._d_rect(20, 20, 80, 80, fill="#0000ff")
        import pygame
        color = r.surface.get_at((50, 50))
        self.assertGreater(color.b, 200)

    def test_d_line_flat_coords(self):
        face, r = self._make_mock_face()
        r.begin_frame("#000000")
        # Flat positional args (as Tk create_line uses)
        face._d_line(0, 50, 200, 50, fill="#ffffff", width=3)
        import pygame
        color = r.surface.get_at((100, 50))
        self.assertGreater(color.r, 200)

    def test_d_line_list_coords(self):
        face, r = self._make_mock_face()
        r.begin_frame("#000000")
        # Single flat list arg (as Tk create_line with pts list)
        pts = [10, 10, 100, 100, 190, 10]
        face._d_line(pts, fill="#00ff00", width=2)

    def test_d_line_smooth(self):
        face, r = self._make_mock_face()
        r.begin_frame("#000000")
        pts = [10, 50, 60, 10, 120, 90, 190, 30]
        face._d_line(pts, fill="#ff00ff", width=2, smooth=True)

    def test_d_polygon_flat_coords(self):
        face, r = self._make_mock_face()
        r.begin_frame("#000000")
        # Inline positional coords (as used for nose triangle)
        face._d_polygon(50, 10, 90, 90, 10, 90, fill="#ffff00")
        import pygame
        color = r.surface.get_at((50, 60))
        self.assertGreater(color.r, 150)

    def test_d_polygon_list_coords(self):
        face, r = self._make_mock_face()
        r.begin_frame("#000000")
        pts = [50, 10, 90, 90, 10, 90]
        face._d_polygon(pts, fill="#00ffff", outline="#ffffff", width=1)

    def test_d_text(self):
        face, r = self._make_mock_face()
        r.begin_frame("#000000")
        face._d_text(200, 180, text="Test", fill="#ffffff",
                     font=("Consolas", 14))

    def test_begin_draw_clears_surface(self):
        face, r = self._make_mock_face()
        r.draw_rectangle(0, 0, 400, 360, fill="#ff0000")
        face._begin_draw()
        import pygame
        color = r.surface.get_at((200, 180))
        # Should be cleared to BG_COLOR (#050810)
        self.assertLess(color.r, 20)

    def test_end_draw_calls_present(self):
        face, r = self._make_mock_face()
        face._end_draw()
        face._viewport.present.assert_called_once()

    def test_d_line_stipple_kwarg_ignored(self):
        """Stipple is a Tk-only param — should not crash in Pygame mode."""
        face, r = self._make_mock_face()
        r.begin_frame("#000000")
        face._d_line(10, 50, 190, 50, fill="#000000", stipple="gray12")


# ---------------------------------------------------------------------------
# TkCanvasRenderer tests (mock canvas)
# ---------------------------------------------------------------------------

class TestTkCanvasRenderer(unittest.TestCase):
    def _make(self):
        from face.render_backend import TkCanvasRenderer
        canvas = MagicMock()
        canvas.winfo_width.return_value = 400
        canvas.winfo_height.return_value = 360
        return TkCanvasRenderer(canvas), canvas

    def test_begin_frame_deletes_all(self):
        r, canvas = self._make()
        r.begin_frame()
        canvas.delete.assert_called_with("all")

    def test_get_size(self):
        r, canvas = self._make()
        self.assertEqual(r.get_size(), (400, 360))

    def test_draw_oval_delegates(self):
        r, canvas = self._make()
        r.draw_oval(10, 10, 90, 90, fill="#ff0000", outline="#ffffff", width=2)
        canvas.create_oval.assert_called_once()

    def test_draw_rectangle_delegates(self):
        r, canvas = self._make()
        r.draw_rectangle(10, 10, 90, 90, fill="#0000ff")
        canvas.create_rectangle.assert_called_once()

    def test_draw_line_delegates(self):
        r, canvas = self._make()
        r.draw_line([(0, 0), (100, 100)], color="#ffffff", width=2)
        canvas.create_line.assert_called_once()

    def test_draw_polygon_delegates(self):
        r, canvas = self._make()
        r.draw_polygon([(10, 10), (50, 10), (30, 50)], fill="#00ff00")
        canvas.create_polygon.assert_called_once()

    def test_draw_text_delegates(self):
        r, canvas = self._make()
        r.draw_text(100, 50, "Hello", color="#ffffff")
        canvas.create_text.assert_called_once()

    def test_draw_image_delegates(self):
        r, canvas = self._make()
        r.draw_image(100, 100, "dummy_image")
        canvas.create_image.assert_called_once()


# ---------------------------------------------------------------------------
# Integration: full face draw cycle through PygameRenderer
# ---------------------------------------------------------------------------

class TestFaceDrawCycleIntegration(unittest.TestCase):
    """Verify that a simulated face draw cycle completes without error."""

    def test_full_draw_primitives_cycle(self):
        """Simulate the face_gui._draw() flow using PygameRenderer directly."""
        from face.render_backend import PygameRenderer
        r = PygameRenderer(width=400, height=360)

        r.begin_frame("#050810")

        # Face plate (rounded rect — polygon)
        pts = []
        for i in range(36):
            angle = math.radians(i * 10)
            pts.append((200 + 180 * math.cos(angle), 180 + 160 * math.sin(angle)))
        r.draw_polygon(pts, fill="#0a1220", outline="#0a3050", width=2)

        # Eyes (ovals)
        for side in (-1, 1):
            ex = 200 + side * 65
            r.draw_oval(ex - 35, 120, ex + 35, 180,
                        fill="#0a1828", outline="#0a3050", width=1)
            # Pupil
            r.draw_oval(ex - 10, 143, ex + 10, 157,
                        fill="#00d4ff", outline="")
            # Highlight
            r.draw_oval(ex - 5, 145, ex, 150,
                        fill="#ffffff", outline="")

        # Brows (smooth lines)
        for side in (-1, 1):
            brow_pts = []
            ex = 200 + side * 65
            for i in range(15):
                t = i / 14
                x = ex - 30 + t * 60
                y = 115 - math.sin(t * math.pi) * 5
                brow_pts.append((x, y))
            r.draw_line(brow_pts, color="#0a3050", width=3, smooth=True)

        # Mouth (smooth line)
        mouth_pts = []
        for i in range(25):
            t = i / 24
            x = 160 + t * 80
            y = 240 - math.sin(t * math.pi) * 8
            mouth_pts.append((x, y))
        r.draw_line(mouth_pts, color="#0a3050", width=2, smooth=True)

        # Details
        r.draw_rectangle(80, 22, 320, 25, fill="#0a3050")
        r.draw_line([(175, 275), (225, 275)], color="#061020", width=1)
        r.draw_polygon([(196, 195), (204, 195), (200, 203)],
                       fill="#061020")
        r.draw_text(200, 340, "thinking...", color="#0a5070",
                    font_family="Consolas", font_size=10)

        # Scan lines
        for y in range(25, 340, 4):
            r.draw_line([(20, y), (380, y)], color="#000000", width=1)

        r.end_frame()

        # Verify surface has content
        import pygame
        w, h = r.get_size()
        self.assertEqual((w, h), (400, 360))
        # Center should not be pure bg color (face was drawn there)
        color = r.surface.get_at((200, 150))
        # Should be the face fill color area
        self.assertTrue(color.r > 0 or color.g > 0 or color.b > 0)


# ---------------------------------------------------------------------------
# CanvasAdapter tests (drop-in tk.Canvas replacement)
# ---------------------------------------------------------------------------

class TestCanvasAdapter(unittest.TestCase):
    """Test CanvasAdapter provides tk.Canvas-compatible interface."""

    def _make(self, w=400, h=300):
        from face.render_backend import PygameRenderer, CanvasAdapter
        r = PygameRenderer(width=w, height=h)
        return CanvasAdapter(r), r

    def test_size_queries(self):
        adapter, r = self._make(800, 600)
        self.assertEqual(adapter.winfo_width(), 800)
        self.assertEqual(adapter.winfo_height(), 600)

    def test_create_oval_returns_id(self):
        adapter, r = self._make()
        r.begin_frame("#000000")
        item_id = adapter.create_oval(10, 10, 90, 90, fill="#ff0000")
        self.assertIsInstance(item_id, int)
        self.assertGreater(item_id, 0)

    def test_create_oval_draws(self):
        adapter, r = self._make()
        r.begin_frame("#000000")
        adapter.create_oval(10, 10, 90, 90, fill="#ff0000", outline="#ffffff", width=2)
        import pygame
        color = r.surface.get_at((50, 50))
        self.assertGreater(color.r, 200)

    def test_create_rectangle_draws(self):
        adapter, r = self._make()
        r.begin_frame("#000000")
        adapter.create_rectangle(20, 20, 80, 80, fill="#0000ff")
        import pygame
        color = r.surface.get_at((50, 50))
        self.assertGreater(color.b, 200)

    def test_create_line_flat_args(self):
        adapter, r = self._make()
        r.begin_frame("#000000")
        adapter.create_line(0, 150, 400, 150, fill="#ffffff", width=3)
        import pygame
        color = r.surface.get_at((200, 150))
        self.assertGreater(color.r, 200)

    def test_create_line_list_arg(self):
        adapter, r = self._make()
        r.begin_frame("#000000")
        adapter.create_line([10, 10, 100, 100, 200, 50], fill="#00ff00", width=2)

    def test_create_polygon_flat_args(self):
        adapter, r = self._make()
        r.begin_frame("#000000")
        adapter.create_polygon(200, 10, 390, 290, 10, 290, fill="#ffff00")
        import pygame
        color = r.surface.get_at((200, 200))
        self.assertGreater(color.r, 150)

    def test_create_polygon_list_arg(self):
        adapter, r = self._make()
        r.begin_frame("#000000")
        adapter.create_polygon([200, 10, 390, 290, 10, 290],
                               fill="#00ffff", outline="#ffffff")

    def test_create_text(self):
        adapter, r = self._make()
        r.begin_frame("#000000")
        adapter.create_text(200, 150, text="Hello", fill="#ffffff",
                            font=("Consolas", 14), anchor="center")

    def test_create_text_string_font(self):
        adapter, r = self._make()
        r.begin_frame("#000000")
        adapter.create_text(200, 150, text="Test", fill="#ffffff",
                            font="Arial")

    def test_create_image(self):
        import pygame
        adapter, r = self._make()
        r.begin_frame("#000000")
        img = pygame.Surface((50, 50))
        img.fill((255, 0, 0))
        adapter.create_image(200, 150, image=img, anchor="center")
        color = r.surface.get_at((200, 150))
        self.assertGreater(color.r, 200)

    def test_retained_mode_nops(self):
        """Retained-mode operations should be silent no-ops."""
        adapter, r = self._make()
        adapter.delete("all")
        adapter.delete("scene")
        adapter.tag_lower("bg")
        adapter.tag_raise("fg")
        adapter.coords(1, 10, 10, 50, 50)
        adapter.itemconfig(1, fill="#ff0000")
        adapter.itemconfigure(1, fill="#ff0000")
        self.assertEqual(adapter.type(1), "rectangle")
        adapter.lift()

    def test_unique_ids(self):
        adapter, r = self._make()
        r.begin_frame("#000000")
        id1 = adapter.create_oval(10, 10, 90, 90, fill="#ff0000")
        id2 = adapter.create_rectangle(10, 10, 90, 90, fill="#0000ff")
        id3 = adapter.create_line(0, 0, 100, 100, fill="#ffffff")
        self.assertNotEqual(id1, id2)
        self.assertNotEqual(id2, id3)

    def test_tags_kwarg_ignored(self):
        """Tags are Tk-specific and should be silently ignored."""
        adapter, r = self._make()
        r.begin_frame("#000000")
        adapter.create_oval(10, 10, 90, 90, fill="#ff0000", tags="scene")
        adapter.create_rectangle(10, 10, 90, 90, fill="#0000ff", tags="bg")
        adapter.create_line(0, 0, 100, 100, fill="#ffffff", tags="scene")
        adapter.create_polygon([10, 10, 50, 10, 30, 50], fill="#00ff00", tags="shape_1")
        adapter.create_text(50, 50, text="Hi", fill="#ffffff", tags="label")

    def test_dash_kwarg_ignored(self):
        """Dash patterns are Tk-specific and should be silently ignored."""
        adapter, r = self._make()
        r.begin_frame("#000000")
        adapter.create_rectangle(10, 10, 90, 90, outline="#ffffff",
                                 width=2, dash=(5, 3))
        adapter.create_line(0, 0, 100, 100, fill="#ffffff",
                            width=1, dash=(4, 2))


# ---------------------------------------------------------------------------
# StageBackground Pygame renderer tests
# ---------------------------------------------------------------------------

class TestStageBackgroundPygame(unittest.TestCase):
    """Test StageBackground drawing through PygameRenderer."""

    def _make(self, w=800, h=600):
        from face.render_backend import PygameRenderer
        from face.stage.background import StageBackground
        r = PygameRenderer(width=w, height=h)
        bg = StageBackground(renderer=r)
        return bg, r

    def test_solid_background(self):
        bg, r = self._make()
        bg.set_solid("#ff0000")
        r.begin_frame("#000000")
        bg.draw()
        import pygame
        color = r.surface.get_at((400, 300))
        self.assertGreater(color.r, 200)

    def test_vertical_gradient(self):
        bg, r = self._make()
        bg.set_gradient(["#000000", "#ffffff"], "vertical")
        r.begin_frame("#000000")
        bg.draw()
        import pygame
        # Top should be dark, bottom should be light
        top = r.surface.get_at((400, 10))
        bot = r.surface.get_at((400, 590))
        self.assertLess(top.r, 100)
        self.assertGreater(bot.r, 150)

    def test_horizontal_gradient(self):
        bg, r = self._make()
        bg.set_gradient(["#000000", "#ffffff"], "horizontal")
        r.begin_frame("#000000")
        bg.draw()
        import pygame
        left = r.surface.get_at((10, 300))
        right = r.surface.get_at((790, 300))
        self.assertLess(left.r, 100)
        self.assertGreater(right.r, 150)

    def test_radial_gradient(self):
        bg, r = self._make()
        bg.set_gradient(["#ffffff", "#000000"], "radial")
        r.begin_frame("#000000")
        bg.draw()
        import pygame
        center = r.surface.get_at((400, 300))
        # Center should be bright (first color)
        self.assertGreater(center.r, 100)

    def test_preset_deep_space(self):
        bg, r = self._make()
        bg.set_preset("deep_space")
        bg.update(0.016)
        r.begin_frame("#000000")
        bg.draw()
        # Should complete without error

    def test_preset_with_particles(self):
        bg, r = self._make()
        bg.set_preset("onyx_atmosphere")
        for _ in range(5):
            bg.update(0.016)
        r.begin_frame("#000000")
        bg.draw()
        # Particles should be spawned and drawn

    def test_particles_immediate_mode(self):
        from face.render_backend import PygameRenderer
        from face.stage.background import ParticleField
        r = PygameRenderer(width=400, height=300)
        pf = ParticleField(object(), 20, "#00ff00", "float")
        pf.spawn(400, 300)
        for _ in range(3):
            pf.update(0.016, 400, 300)
        r.begin_frame("#000000")
        pf.draw_immediate(r)
        # Should draw without error

    def test_clear_particles(self):
        bg, r = self._make()
        bg.set_particles("float", 30, "#ff0000")
        bg.clear_particles()
        r.begin_frame("#000000")
        bg.draw()
        # Should not crash after clearing

    def test_update_without_draw(self):
        bg, r = self._make()
        bg.set_preset("electric_blue")
        # Multiple updates should not crash
        for _ in range(10):
            bg.update(0.016)


if __name__ == "__main__":
    unittest.main()
