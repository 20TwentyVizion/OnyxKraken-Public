"""Screen Recorder Bridge — wires the standalone recorder into OnyxKraken.

core/screen_recorder.py has zero Onyx imports (uses mss + ffmpeg).
This bridge exposes ScreenRecorder as a service and emits events.

Events emitted:
  recorder:started     — recording began           {path, fps, quality}
  recorder:stopped     — recording finished         {path, duration, size_bytes}

Events consumed:
  app_shutting_down    — stop active recording
"""

import logging
from typing import Any, Dict, Optional

from core.plugins.protocol import OnyxPlugin, PluginMeta

_log = logging.getLogger("core.plugins.bridge_screen_recorder")

RECORDER_STARTED = "recorder:started"
RECORDER_STOPPED = "recorder:stopped"


class ScreenRecorderBridge(OnyxPlugin):
    """Bridge between standalone core/screen_recorder.py and OnyxKraken."""

    def __init__(self):
        super().__init__()
        self._recorder = None
        self._bus = None
        self._event_handlers = {}

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="screen_recorder",
            display_name="Screen Recorder",
            version="1.0.0",
            description="Capture the desktop to MP4 with optional TTS audio narration.",
            standalone=True,
            category="media",
            services=["screen_recorder"],
            events_emitted=[RECORDER_STARTED, RECORDER_STOPPED],
            events_consumed=["app_shutting_down"],
            dependencies=[],
            tags=["recording", "screen", "video", "media"],
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def register(self, registry, event_bus) -> None:
        self._bus = event_bus
        registry.register_factory("screen_recorder", self._get_recorder, replace=True)

        self._subscribe(event_bus, "app_shutting_down", self._on_shutdown)
        _log.info("Screen Recorder bridge registered.")

    def unregister(self, registry, event_bus) -> None:
        for event_name, handler in self._event_handlers.items():
            try:
                event_bus.off(event_name, handler)
            except Exception:
                pass
        self._event_handlers.clear()
        if self._recorder and self._recorder.is_recording:
            self._recorder.stop()
        _log.info("Screen Recorder bridge unregistered.")

    def health(self) -> Dict[str, Any]:
        base = super().health()
        base["is_recording"] = bool(self._recorder and self._recorder.is_recording)
        # Check ffmpeg availability
        import shutil
        base["ffmpeg_available"] = shutil.which("ffmpeg") is not None
        return base

    # ------------------------------------------------------------------
    # Service factory
    # ------------------------------------------------------------------

    def _get_recorder(self):
        if self._recorder is None:
            from core.screen_recorder import ScreenRecorder
            self._recorder = ScreenRecorder()
            _log.info("ScreenRecorder instance created.")
        return self._recorder

    # ------------------------------------------------------------------
    # Onyx-facing API
    # ------------------------------------------------------------------

    def start_recording(self, name: str = "recording", **kwargs) -> Dict:
        """Start recording with event emission."""
        rec = self._get_recorder()
        try:
            path = rec.start(name)
            if self._bus:
                self._bus.emit(RECORDER_STARTED, {
                    "path": path,
                    "fps": rec.fps,
                    "quality": rec.quality,
                })
            return {"ok": True, "path": path}
        except RuntimeError as e:
            return {"ok": False, "error": str(e)}

    def stop_recording(self) -> Dict:
        """Stop recording with event emission."""
        if not self._recorder or not self._recorder.is_recording:
            return {"ok": False, "error": "Not recording"}
        info = self._recorder.stop()
        if info and self._bus:
            self._bus.emit(RECORDER_STOPPED, {
                "path": info.path,
                "duration": info.duration,
                "size_bytes": info.size_bytes,
            })
        return {
            "ok": info is not None,
            "path": info.path if info else "",
            "duration": info.duration if info else 0,
        }

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_shutdown(self, data: Dict) -> None:
        if self._recorder and self._recorder.is_recording:
            _log.info("Screen Recorder: stopping recording on shutdown.")
            self._recorder.stop()

    def _subscribe(self, bus, event_name: str, handler):
        bus.on(event_name, handler)
        self._event_handlers[event_name] = handler


plugin = ScreenRecorderBridge()
