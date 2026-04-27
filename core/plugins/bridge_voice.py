"""Voice Bridge — wires the standalone voice I/O into OnyxKraken.

core/voice.py has zero Onyx imports (STT via whisper, TTS via pyttsx3/edge-tts).
This bridge exposes listen() and speak() as services and emits events.

Events emitted:
  voice:speech_started   — TTS began              {text}
  voice:speech_finished  — TTS completed           {text, duration}
  voice:transcribed      — STT returned text       {text, duration}

Events consumed:
  voice_settings_changed — update rate/pitch/engine
  app_shutting_down      — stop any active speech
"""

import logging
import time
from typing import Any, Dict, Optional

from core.plugins.protocol import OnyxPlugin, PluginMeta

_log = logging.getLogger("core.plugins.bridge_voice")

VOICE_SPEECH_STARTED = "voice:speech_started"
VOICE_SPEECH_FINISHED = "voice:speech_finished"
VOICE_TRANSCRIBED = "voice:transcribed"


class VoiceBridge(OnyxPlugin):
    """Bridge between standalone core/voice.py and OnyxKraken infrastructure."""

    def __init__(self):
        super().__init__()
        self._bus = None
        self._event_handlers = {}

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="voice",
            display_name="Voice I/O",
            version="1.0.0",
            description="Speech-to-text and text-to-speech — whisper.cpp, pyttsx3, edge-tts.",
            standalone=True,
            category="core",
            services=["voice"],
            events_emitted=[
                VOICE_SPEECH_STARTED, VOICE_SPEECH_FINISHED,
                VOICE_TRANSCRIBED,
            ],
            events_consumed=["voice_settings_changed", "app_shutting_down"],
            dependencies=[],
            tags=["voice", "tts", "stt", "audio"],
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def register(self, registry, event_bus) -> None:
        self._bus = event_bus
        registry.register("voice", self, replace=True)

        self._subscribe(event_bus, "voice_settings_changed", self._on_settings_changed)
        self._subscribe(event_bus, "app_shutting_down", self._on_shutdown)
        _log.info("Voice bridge registered.")

    def unregister(self, registry, event_bus) -> None:
        for event_name, handler in self._event_handlers.items():
            try:
                event_bus.off(event_name, handler)
            except Exception:
                pass
        self._event_handlers.clear()
        _log.info("Voice bridge unregistered.")

    def health(self) -> Dict[str, Any]:
        base = super().health()
        try:
            from core.voice import _find_whisper_cpp
            base["whisper_cpp_available"] = _find_whisper_cpp() is not None
        except Exception:
            base["whisper_cpp_available"] = False
        try:
            import pyttsx3
            base["pyttsx3_available"] = True
        except ImportError:
            base["pyttsx3_available"] = False
        return base

    # ------------------------------------------------------------------
    # Onyx-facing API
    # ------------------------------------------------------------------

    def speak(self, text: str) -> Dict:
        """Speak text with event emission."""
        from core.voice import speak as _speak

        if self._bus:
            self._bus.emit(VOICE_SPEECH_STARTED, {"text": text})

        t0 = time.time()
        success = _speak(text)
        duration = time.time() - t0

        if self._bus:
            self._bus.emit(VOICE_SPEECH_FINISHED, {
                "text": text,
                "duration": round(duration, 2),
            })

        return {"ok": success, "text": text, "duration": round(duration, 2)}

    def listen(self, duration: float = 5.0) -> Dict:
        """Listen for speech with event emission."""
        from core.voice import listen as _listen

        t0 = time.time()
        text = _listen(duration=duration)
        elapsed = time.time() - t0

        if text and self._bus:
            self._bus.emit(VOICE_TRANSCRIBED, {
                "text": text,
                "duration": round(elapsed, 2),
            })

        return {
            "ok": text is not None,
            "text": text or "",
            "duration": round(elapsed, 2),
        }

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_settings_changed(self, data: Dict) -> None:
        _log.info("Voice settings updated: %s", data)

    def _on_shutdown(self, data: Dict) -> None:
        _log.info("Voice: shutdown acknowledged.")

    def _subscribe(self, bus, event_name: str, handler):
        bus.on(event_name, handler)
        self._event_handlers[event_name] = handler


plugin = VoiceBridge()
