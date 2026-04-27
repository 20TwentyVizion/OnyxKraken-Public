"""Vision Bridge — wires the standalone vision/ package into OnyxKraken.

vision/ is now standalone (analyzer.py uses injectable config + chat_fn).
This bridge injects the real model_router and config values, then exposes
vision as a service.

Events emitted:
  vision:screenshot_taken  — after capture           {path}
  vision:analyzed          — after analyze_screenshot {prompt, response_len}
  vision:stability_check   — after is_screen_stable   {stable}

Events consumed:
  app_ready               — inject config + router
  app_shutting_down       — cleanup
"""

import logging
from typing import Any, Dict

from core.plugins.protocol import OnyxPlugin, PluginMeta

_log = logging.getLogger("core.plugins.bridge_vision")

VISION_SCREENSHOT_TAKEN = "vision:screenshot_taken"
VISION_ANALYZED = "vision:analyzed"
VISION_STABILITY_CHECK = "vision:stability_check"


class VisionBridge(OnyxPlugin):
    """Bridge between standalone vision/ and OnyxKraken infrastructure."""

    def __init__(self):
        super().__init__()
        self._bus = None
        self._event_handlers = {}
        self._configured = False

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="vision",
            display_name="Vision Analyzer",
            version="1.0.0",
            description="Screenshot capture, grid overlay, SSIM stability, and vision model queries.",
            standalone=True,
            category="core",
            services=["vision"],
            events_emitted=[
                VISION_SCREENSHOT_TAKEN, VISION_ANALYZED,
                VISION_STABILITY_CHECK,
            ],
            events_consumed=["app_ready", "app_shutting_down"],
            dependencies=[],
            tags=["vision", "screenshot", "opencv", "automation"],
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def register(self, registry, event_bus) -> None:
        self._bus = event_bus
        registry.register("vision", self, replace=True)

        self._subscribe(event_bus, "app_ready", self._on_app_ready)
        self._subscribe(event_bus, "app_shutting_down", self._on_shutdown)

        # Inject config + router immediately
        self._inject_config()

        _log.info("Vision bridge registered.")

    def unregister(self, registry, event_bus) -> None:
        for event_name, handler in self._event_handlers.items():
            try:
                event_bus.off(event_name, handler)
            except Exception:
                pass
        self._event_handlers.clear()
        _log.info("Vision bridge unregistered.")

    def health(self) -> Dict[str, Any]:
        base = super().health()
        base["configured"] = self._configured
        try:
            import cv2
            base["opencv_available"] = True
        except ImportError:
            base["opencv_available"] = False
        return base

    # ------------------------------------------------------------------
    # Configuration injection
    # ------------------------------------------------------------------

    def _inject_config(self):
        """Inject OnyxKraken's config values and model router into vision.analyzer."""
        try:
            import config as onyx_config
            from agent.model_router import router
            from vision.analyzer import configure

            cfg = {
                "save_screenshots": getattr(onyx_config, "SAVE_SCREENSHOTS", True),
                "screenshot_dir": getattr(onyx_config, "SCREENSHOT_DIR", "screenshots"),
                "max_screenshots": getattr(onyx_config, "MAX_SCREENSHOTS", 50),
                "ssim_stability_delay": getattr(onyx_config, "SSIM_STABILITY_DELAY", 0.5),
                "ssim_threshold": getattr(onyx_config, "SSIM_THRESHOLD", 0.98),
            }

            configure(cfg=cfg, chat_fn=router.chat)
            self._configured = True
            _log.info("Vision analyzer configured with OnyxKraken config + router.")

        except ImportError as e:
            _log.warning("Could not inject config into vision: %s", e)
            self._configured = False

    # ------------------------------------------------------------------
    # Onyx-facing API
    # ------------------------------------------------------------------

    def capture(self, region=None) -> Dict:
        """Capture screenshot with event emission."""
        from vision.analyzer import capture_screenshot, save_screenshot
        img = capture_screenshot(region=region)
        path = save_screenshot(img)
        if self._bus:
            self._bus.emit(VISION_SCREENSHOT_TAKEN, {"path": path})
        return {"ok": True, "path": path}

    def analyze(self, img, prompt: str, use_grid: bool = False) -> Dict:
        """Analyze screenshot with event emission."""
        from vision.analyzer import analyze_screenshot
        response = analyze_screenshot(img, prompt, use_grid=use_grid)
        if self._bus:
            self._bus.emit(VISION_ANALYZED, {
                "prompt": prompt,
                "response_len": len(response),
            })
        return {"ok": True, "response": response}

    def check_stability(self, delay=None, threshold=None) -> Dict:
        """Check screen stability with event emission."""
        from vision.analyzer import is_screen_stable
        stable = is_screen_stable(delay=delay, threshold=threshold)
        if self._bus:
            self._bus.emit(VISION_STABILITY_CHECK, {"stable": stable})
        return {"ok": True, "stable": stable}

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_app_ready(self, data: Dict) -> None:
        if not self._configured:
            self._inject_config()

    def _on_shutdown(self, data: Dict) -> None:
        _log.info("Vision: shutdown acknowledged.")

    def _subscribe(self, bus, event_name: str, handler):
        bus.on(event_name, handler)
        self._event_handlers[event_name] = handler


plugin = VisionBridge()
