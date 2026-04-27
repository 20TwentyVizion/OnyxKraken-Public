"""Render Backend Abstraction — decouples drawing from Tkinter Canvas.

Provides a uniform drawing API that can be implemented by:
  - TkCanvasRenderer (wraps existing tk.Canvas calls)
  - PygameRenderer   (hardware-accelerated, anti-aliased)

All coordinates are in *screen space* (already scaled). The face_gui
scaling helpers (_sx/_sy/_ss) remain in FaceCanvas and feed screen-space
coords to whichever renderer is active.

Usage:
    renderer = PygameRenderer(width=400, height=360)
    renderer.begin_frame()
    renderer.draw_oval(10, 10, 100, 80, fill="#00d4ff")
    renderer.draw_line([(0,0), (100,100)], color="#ffffff", width=2)
    renderer.end_frame()
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import List, Optional, Sequence, Tuple, Union

Coord = Union[float, int]
Color = str  # hex color string e.g. "#00d4ff"
PointList = Sequence[Tuple[Coord, Coord]]


class RenderBackend(ABC):
    """Abstract rendering interface matching the subset of tk.Canvas
    primitives used by the face, stage, and animation systems."""

    @abstractmethod
    def begin_frame(self, bg_color: Color = "#050810"):
        """Clear the frame buffer and prepare for drawing."""

    @abstractmethod
    def end_frame(self):
        """Finalize the frame (flip buffers, present, etc.)."""

    @abstractmethod
    def get_size(self) -> Tuple[int, int]:
        """Return current (width, height) of the render surface."""

    # ----- Primitives -----

    @abstractmethod
    def draw_oval(self, x0: Coord, y0: Coord, x1: Coord, y1: Coord,
                  fill: Color = "", outline: Color = "", width: float = 1,
                  stipple: str = ""):
        """Draw an axis-aligned ellipse bounded by (x0,y0)-(x1,y1)."""

    @abstractmethod
    def draw_rectangle(self, x0: Coord, y0: Coord, x1: Coord, y1: Coord,
                       fill: Color = "", outline: Color = "", width: float = 1):
        """Draw a filled/outlined rectangle."""

    @abstractmethod
    def draw_line(self, points: PointList, color: Color = "#ffffff",
                  width: float = 1, smooth: bool = False):
        """Draw a polyline through the given points."""

    @abstractmethod
    def draw_polygon(self, points: PointList, fill: Color = "",
                     outline: Color = "", width: float = 1):
        """Draw a filled/outlined polygon."""

    @abstractmethod
    def draw_text(self, x: Coord, y: Coord, text: str, color: Color = "#ffffff",
                  font_family: str = "Consolas", font_size: int = 12,
                  anchor: str = "center"):
        """Draw text at the given position."""

    @abstractmethod
    def draw_image(self, x: Coord, y: Coord, image, anchor: str = "center"):
        """Draw an image (PIL Image or backend-specific handle)."""


# -----------------------------------------------------------------------
# Tkinter Canvas Renderer (wraps existing canvas — drop-in compatible)
# -----------------------------------------------------------------------

class TkCanvasRenderer(RenderBackend):
    """Wraps a tk.Canvas so existing code works unchanged via the new API."""

    def __init__(self, canvas):
        self._canvas = canvas

    def begin_frame(self, bg_color: Color = "#050810"):
        self._canvas.delete("all")

    def end_frame(self):
        pass  # Tkinter updates automatically via mainloop

    def get_size(self) -> Tuple[int, int]:
        return self._canvas.winfo_width(), self._canvas.winfo_height()

    def draw_oval(self, x0, y0, x1, y1, fill="", outline="", width=1, stipple=""):
        kw = {}
        if fill:
            kw["fill"] = fill
        if outline:
            kw["outline"] = outline
        else:
            kw["outline"] = ""
        if width:
            kw["width"] = width
        if stipple:
            kw["stipple"] = stipple
        self._canvas.create_oval(x0, y0, x1, y1, **kw)

    def draw_rectangle(self, x0, y0, x1, y1, fill="", outline="", width=1):
        kw = {}
        if fill:
            kw["fill"] = fill
        if outline:
            kw["outline"] = outline
        else:
            kw["outline"] = ""
        if width:
            kw["width"] = width
        self._canvas.create_rectangle(x0, y0, x1, y1, **kw)

    def draw_line(self, points, color="#ffffff", width=1, smooth=False):
        flat = []
        for p in points:
            flat.extend(p)
        kw = {"fill": color, "width": width}
        if smooth:
            kw["smooth"] = True
        self._canvas.create_line(flat, **kw)

    def draw_polygon(self, points, fill="", outline="", width=1):
        flat = []
        for p in points:
            flat.extend(p)
        kw = {}
        if fill:
            kw["fill"] = fill
        if outline:
            kw["outline"] = outline
        else:
            kw["outline"] = ""
        if width:
            kw["width"] = width
        self._canvas.create_polygon(flat, **kw)

    def draw_text(self, x, y, text, color="#ffffff",
                  font_family="Consolas", font_size=12, anchor="center"):
        self._canvas.create_text(x, y, text=text, fill=color,
                                 font=(font_family, font_size), anchor=anchor)

    def draw_image(self, x, y, image, anchor="center"):
        self._canvas.create_image(x, y, image=image, anchor=anchor)


# -----------------------------------------------------------------------
# Pygame Renderer (hardware-accelerated, anti-aliased)
# -----------------------------------------------------------------------

def _hex_to_rgba(h: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    """Convert '#rrggbb' to (r, g, b, a)."""
    h = h.lstrip("#")
    if len(h) == 6:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)
    return (0, 0, 0, alpha)


def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 6:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    return (0, 0, 0)


class PygameRenderer(RenderBackend):
    """Hardware-accelerated 2D renderer using pygame-ce.

    Features over TkCanvas:
      - Anti-aliased circles and lines via pygame.gfxdraw
      - Alpha blending for glow effects
      - Smooth 60fps with hardware surfaces
      - Font caching for fast text rendering
    """

    def __init__(self, surface=None, width: int = 400, height: int = 360):
        import pygame
        self._pg = pygame
        # Ensure required subsystems are initialized
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()
        if surface is not None:
            self._surface = surface
        else:
            self._surface = pygame.Surface((width, height), pygame.SRCALPHA)
        self._font_cache: dict = {}
        self._gfx = None
        try:
            import pygame.gfxdraw
            self._gfx = pygame.gfxdraw
        except ImportError:
            pass

    @property
    def surface(self):
        return self._surface

    @surface.setter
    def surface(self, s):
        self._surface = s

    def begin_frame(self, bg_color: Color = "#050810"):
        self._surface.fill(_hex_to_rgb(bg_color))

    def end_frame(self):
        pass  # Caller handles display.flip() or blit

    def get_size(self) -> Tuple[int, int]:
        return self._surface.get_size()

    def _get_font(self, family: str, size: int):
        key = (family, size)
        if key not in self._font_cache:
            pg = self._pg
            try:
                self._font_cache[key] = pg.font.SysFont(family, max(1, size))
            except Exception:
                self._font_cache[key] = pg.font.Font(None, max(1, size))
        return self._font_cache[key]

    # ----- Primitives -----

    def draw_oval(self, x0, y0, x1, y1, fill="", outline="", width=1, stipple=""):
        pg = self._pg
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        rx = abs(x1 - x0) / 2
        ry = abs(y1 - y0) / 2

        if rx < 1 or ry < 1:
            return

        if fill and fill != "":
            rgb = _hex_to_rgb(fill)
            if self._gfx and abs(rx - ry) < 1:
                # Perfect circle — use gfxdraw for AA
                r = int(rx)
                self._gfx.aacircle(self._surface, int(cx), int(cy), r, rgb)
                self._gfx.filled_circle(self._surface, int(cx), int(cy), r, rgb)
            else:
                rect = pg.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
                pg.draw.ellipse(self._surface, rgb, rect)

        if outline and outline != "":
            rgb = _hex_to_rgb(outline)
            w = max(1, int(width))
            rect = pg.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
            pg.draw.ellipse(self._surface, rgb, rect, w)

    def draw_rectangle(self, x0, y0, x1, y1, fill="", outline="", width=1):
        pg = self._pg
        rect = pg.Rect(int(min(x0, x1)), int(min(y0, y1)),
                        int(abs(x1 - x0)), int(abs(y1 - y0)))
        if fill and fill != "":
            pg.draw.rect(self._surface, _hex_to_rgb(fill), rect)
        if outline and outline != "":
            pg.draw.rect(self._surface, _hex_to_rgb(outline), rect, max(1, int(width)))

    def draw_line(self, points, color="#ffffff", width=1, smooth=False):
        pg = self._pg
        if len(points) < 2:
            return
        rgb = _hex_to_rgb(color)
        w = max(1, int(width))
        int_pts = [(int(p[0]), int(p[1])) for p in points]

        if smooth and len(int_pts) >= 3:
            # Catmull-Rom interpolation for smooth curves
            smooth_pts = _catmull_rom(int_pts, segments_per_span=6)
            if len(smooth_pts) >= 2:
                pg.draw.aalines(self._surface, rgb, False, smooth_pts)
                if w > 1:
                    pg.draw.lines(self._surface, rgb, False, smooth_pts, w)
                return

        if len(int_pts) == 2:
            pg.draw.aaline(self._surface, rgb, int_pts[0], int_pts[1])
            if w > 1:
                pg.draw.line(self._surface, rgb, int_pts[0], int_pts[1], w)
        else:
            pg.draw.aalines(self._surface, rgb, False, int_pts)
            if w > 1:
                pg.draw.lines(self._surface, rgb, False, int_pts, w)

    def draw_polygon(self, points, fill="", outline="", width=1):
        pg = self._pg
        if len(points) < 3:
            return
        int_pts = [(int(p[0]), int(p[1])) for p in points]

        if fill and fill != "":
            if self._gfx:
                xs = [p[0] for p in int_pts]
                ys = [p[1] for p in int_pts]
                self._gfx.aapolygon(self._surface, int_pts, _hex_to_rgb(fill))
                self._gfx.filled_polygon(self._surface, int_pts, _hex_to_rgb(fill))
            else:
                pg.draw.polygon(self._surface, _hex_to_rgb(fill), int_pts)

        if outline and outline != "":
            rgb = _hex_to_rgb(outline)
            w = max(1, int(width))
            pg.draw.polygon(self._surface, rgb, int_pts, w)
            # AA outline
            if self._gfx:
                self._gfx.aapolygon(self._surface, int_pts, rgb)

    def draw_text(self, x, y, text, color="#ffffff",
                  font_family="Consolas", font_size=12, anchor="center"):
        font = self._get_font(font_family, font_size)
        surf = font.render(text, True, _hex_to_rgb(color))
        rect = surf.get_rect()
        if anchor == "center":
            rect.center = (int(x), int(y))
        elif anchor == "nw":
            rect.topleft = (int(x), int(y))
        elif anchor == "n":
            rect.midtop = (int(x), int(y))
        elif anchor == "ne":
            rect.topright = (int(x), int(y))
        elif anchor == "w":
            rect.midleft = (int(x), int(y))
        elif anchor == "e":
            rect.midright = (int(x), int(y))
        elif anchor == "sw":
            rect.bottomleft = (int(x), int(y))
        elif anchor == "s":
            rect.midbottom = (int(x), int(y))
        elif anchor == "se":
            rect.bottomright = (int(x), int(y))
        self._surface.blit(surf, rect)

    def draw_image(self, x, y, image, anchor="center"):
        """Blit a pygame.Surface or PIL Image at (x, y)."""
        pg = self._pg
        if hasattr(image, "mode"):
            # PIL Image — convert to pygame surface
            import io
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            buf.seek(0)
            surf = pg.image.load(buf, "png")
        elif isinstance(image, pg.Surface):
            surf = image
        else:
            return
        rect = surf.get_rect()
        if anchor == "center":
            rect.center = (int(x), int(y))
        else:
            rect.topleft = (int(x), int(y))
        self._surface.blit(surf, rect)


# -----------------------------------------------------------------------
# CanvasAdapter — drop-in tk.Canvas replacement backed by RenderBackend
# -----------------------------------------------------------------------

class CanvasAdapter:
    """Wraps a RenderBackend to provide tk.Canvas-compatible draw methods.

    This allows existing code that calls ``canvas.create_oval(...)``,
    ``canvas.create_line(...)``, etc. to work unmodified with a
    PygameRenderer by passing a CanvasAdapter instead of a real Canvas.

    Retained-mode operations (``coords``, ``itemconfig``, ``tag_lower``,
    ``delete``) become no-ops since PygameRenderer uses immediate-mode
    rendering (full redraw each frame).

    Usage::

        renderer = PygameRenderer(width=800, height=600)
        adapter = CanvasAdapter(renderer)
        # Pass adapter anywhere a tk.Canvas is expected:
        scene.render(adapter)
    """

    def __init__(self, renderer: RenderBackend):
        self._r = renderer
        self._counter = 0  # fake item ID generator

    def _next_id(self) -> int:
        self._counter += 1
        return self._counter

    # -- Size queries --

    def winfo_width(self) -> int:
        return self._r.get_size()[0]

    def winfo_height(self) -> int:
        return self._r.get_size()[1]

    # -- Retained-mode no-ops --

    def delete(self, *args):
        pass

    def tag_lower(self, *args):
        pass

    def tag_raise(self, *args):
        pass

    def coords(self, *args):
        pass

    def itemconfig(self, *args, **kwargs):
        pass

    def itemconfigure(self, *args, **kwargs):
        pass

    def type(self, item_id):
        return "rectangle"

    def lift(self, *args):
        pass

    # -- Draw primitives --

    def create_oval(self, x0, y0, x1, y1, **kw):
        self._r.draw_oval(x0, y0, x1, y1,
                          fill=kw.get('fill', ''),
                          outline=kw.get('outline', ''),
                          width=kw.get('width', 1),
                          stipple=kw.get('stipple', ''))
        return self._next_id()

    def create_rectangle(self, x0, y0, x1, y1, **kw):
        self._r.draw_rectangle(x0, y0, x1, y1,
                                fill=kw.get('fill', ''),
                                outline=kw.get('outline', ''),
                                width=kw.get('width', 1))
        return self._next_id()

    def create_line(self, *args, **kw):
        flat = []
        for a in args:
            if isinstance(a, (list, tuple)):
                flat.extend(a)
            else:
                flat.append(float(a))
        pts = [(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)]
        self._r.draw_line(pts,
                          color=kw.get('fill', '#ffffff'),
                          width=kw.get('width', 1),
                          smooth=kw.get('smooth', False))
        return self._next_id()

    def create_polygon(self, *args, **kw):
        flat = []
        for a in args:
            if isinstance(a, (list, tuple)):
                flat.extend(a)
            else:
                flat.append(float(a))
        pts = [(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)]
        self._r.draw_polygon(pts,
                              fill=kw.get('fill', ''),
                              outline=kw.get('outline', ''),
                              width=kw.get('width', 1))
        return self._next_id()

    def create_text(self, x, y, **kw):
        font_spec = kw.get('font', ('Consolas', 12))
        if isinstance(font_spec, tuple):
            family = font_spec[0]
            size = font_spec[1] if len(font_spec) > 1 else 12
        else:
            family = str(font_spec)
            size = 12
        self._r.draw_text(x, y,
                          text=kw.get('text', ''),
                          color=kw.get('fill', '#ffffff'),
                          font_family=family,
                          font_size=size,
                          anchor=kw.get('anchor', 'center'))
        return self._next_id()

    def create_image(self, x, y, **kw):
        image = kw.get('image')
        if image is not None:
            self._r.draw_image(x, y, image,
                               anchor=kw.get('anchor', 'center'))
        return self._next_id()


# -----------------------------------------------------------------------
# Catmull-Rom spline for smooth curves (replaces Tk's smooth=True)
# -----------------------------------------------------------------------

def _catmull_rom(points: list, segments_per_span: int = 6) -> list:
    """Generate a smooth Catmull-Rom spline through the given points."""
    if len(points) < 3:
        return points
    result = []
    # Extend with phantom endpoints for full coverage
    pts = [points[0]] + points + [points[-1]]
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for t_idx in range(segments_per_span):
            t = t_idx / segments_per_span
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * ((2 * p1[0]) +
                        (-p0[0] + p2[0]) * t +
                        (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                        (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) +
                        (-p0[1] + p2[1]) * t +
                        (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                        (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            result.append((int(x), int(y)))
    result.append(pts[-2])  # add last real point
    return result
