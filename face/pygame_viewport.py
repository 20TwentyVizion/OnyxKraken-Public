"""Pygame Viewport — embeds a Pygame rendering surface inside Tkinter.

Strategy: Pygame renders to an off-screen surface, which is converted to
a PIL Image each frame and displayed on a Tkinter Label via PhotoImage.
This avoids the fragile SDL_WINDOWID hack and works reliably cross-platform.

For the face at 400x360 @ 30fps, the PIL blit overhead is ~2ms/frame,
well within budget. For larger viewports (1920x1080), the mss screen-grab
approach in VideoExporter is faster for recording, but for live display
this PIL bridge is the right tradeoff.

Usage:
    root = tk.Tk()
    viewport = PygameViewport(root, width=400, height=360)
    viewport.pack(fill="both", expand=True)

    # In your render loop:
    renderer = viewport.renderer  # PygameRenderer instance
    renderer.begin_frame()
    renderer.draw_oval(...)
    renderer.end_frame()
    viewport.present()  # blits pygame surface to Tkinter label
"""

from __future__ import annotations

import logging
import tkinter as tk
from typing import Optional

_log = logging.getLogger("face.pygame_viewport")


class PygameViewport(tk.Frame):
    """A Tkinter widget that hosts a PygameRenderer surface.

    Renders via Pygame → PIL Image → Tkinter PhotoImage pipeline.
    Supports dynamic resizing — surface is recreated on resize.
    """

    def __init__(self, parent, width: int = 400, height: int = 360,
                 bg_color: str = "#050810", **kwargs):
        super().__init__(parent, bg=bg_color, **kwargs)

        self._width = width
        self._height = height
        self._bg_color = bg_color
        self._photo = None  # Tkinter PhotoImage reference (prevent GC)
        self._pg = None
        self._renderer = None
        self._label = tk.Label(self, bg=bg_color, borderwidth=0,
                               highlightthickness=0)
        self._label.pack(fill="both", expand=True)

        # Initialize pygame (display not needed — we use off-screen surfaces)
        self._init_pygame()

        # Handle resizing
        self.bind("<Configure>", self._on_resize)

    def _init_pygame(self):
        """Initialize pygame subsystems needed for off-screen rendering."""
        try:
            import pygame
            # Only init the subsystems we need — no display window
            if not pygame.get_init():
                pygame.init()
            if not pygame.font.get_init():
                pygame.font.init()
            self._pg = pygame

            from face.render_backend import PygameRenderer
            surface = pygame.Surface((self._width, self._height), pygame.SRCALPHA)
            self._renderer = PygameRenderer(surface=surface,
                                            width=self._width,
                                            height=self._height)
            _log.info(f"PygameViewport initialized ({self._width}x{self._height})")
        except ImportError as e:
            _log.warning(f"pygame-ce not available, falling back to Tk: {e}")
            self._pg = None
            self._renderer = None

    @property
    def renderer(self) -> Optional["PygameRenderer"]:
        """The PygameRenderer for this viewport, or None if unavailable."""
        return self._renderer

    @property
    def available(self) -> bool:
        """True if pygame rendering is available."""
        return self._renderer is not None

    def present(self):
        """Convert the pygame surface to a Tkinter PhotoImage and display it.

        Call this after renderer.end_frame() to push the frame to screen.
        """
        if not self._renderer or not self._pg:
            return

        try:
            from PIL import Image, ImageTk

            surface = self._renderer.surface
            # pygame surface → raw bytes → PIL Image → PhotoImage
            raw = self._pg.image.tobytes(surface, "RGBA")
            w, h = surface.get_size()
            img = Image.frombytes("RGBA", (w, h), raw)

            self._photo = ImageTk.PhotoImage(img)
            self._label.configure(image=self._photo)
        except Exception as e:
            _log.debug(f"PygameViewport.present() error: {e}")

    def _on_resize(self, event):
        """Recreate the pygame surface when the widget is resized."""
        new_w = max(2, event.width)
        new_h = max(2, event.height)
        if new_w == self._width and new_h == self._height:
            return
        self._width = new_w
        self._height = new_h
        if self._renderer and self._pg:
            new_surface = self._pg.Surface((new_w, new_h), self._pg.SRCALPHA)
            self._renderer.surface = new_surface
            _log.debug(f"PygameViewport resized to {new_w}x{new_h}")

    def get_surface_size(self) -> tuple[int, int]:
        """Return current surface dimensions."""
        return self._width, self._height
