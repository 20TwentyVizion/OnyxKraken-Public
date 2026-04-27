"""Voice I/O — speech-to-text and text-to-speech for OnyxKraken.

STT options (in priority order):
  1. whisper.cpp via subprocess (local, fast, GPU-accelerated)
  2. OpenAI Whisper Python package (local, slower)
  3. Windows SAPI via pyttsx3 (fallback)

TTS options (in quality order):
  1. Fish Audio S2 — open-source emotional TTS with inline tags (local or API)
  2. ElevenLabs — premium cloud TTS (needs API key)
  3. Edge TTS via edge-tts package (higher quality, needs network)
  4. pyttsx3 (Windows SAPI — always available)

Usage:
    from core.voice import listen, speak

    text = listen()            # records mic → returns transcription
    speak("Hello world")       # synthesizes and plays speech

Fish Audio S2 mood-aware speech:
    from core.voice import speak_with_mood
    speak_with_mood("I found the solution", mood="confident")
    # → Inserts [strong][emphasis] tags automatically
"""

import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from dataclasses import dataclass, field
from typing import Optional

_log = logging.getLogger("core.voice")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Path to whisper.cpp main executable (set via env var or auto-detect)
WHISPER_CPP_PATH = os.environ.get("WHISPER_CPP_PATH", "")
WHISPER_MODEL_PATH = os.environ.get(
    "WHISPER_MODEL_PATH",
    os.path.join(os.path.expanduser("~"), "models", "ggml-base.en.bin"),
)

# Recording settings
RECORD_RATE = 16000
RECORD_CHANNELS = 1
RECORD_SECONDS_DEFAULT = 5
RECORD_SECONDS_MAX = 30

# Fish Audio S2 configuration
FISH_AUDIO_API_URL = os.environ.get(
    "FISH_AUDIO_API_URL", "https://api.fish.audio/v1/tts")
FISH_AUDIO_API_KEY = os.environ.get("FISH_AUDIO_API_KEY", "")
FISH_AUDIO_LOCAL_URL = os.environ.get(
    "FISH_AUDIO_LOCAL_URL", "http://localhost:8721/v1/tts")
FISH_AUDIO_VOICE_ID = os.environ.get(
    "FISH_AUDIO_VOICE_ID", "")  # reference voice ID for cloned voice


# ---------------------------------------------------------------------------
# Fish Audio S2 — Mood-to-Inline-Tag Mapping
# ---------------------------------------------------------------------------
# Maps OnyxKraken mind moods to Fish Audio S2 inline emotional tags.
# Tags are inserted at sentence boundaries to modulate vocal expression.
# See: https://docs.fish.audio/text-to-speech#inline-tags

FISH_AUDIO_MOOD_TAGS: dict[str, dict] = {
    "confident": {
        "prefix": "[strong]",
        "mid_tags": ["[emphasis]"],
        "suffix": "",
        "description": "Bold, assured delivery",
    },
    "ready": {
        "prefix": "",
        "mid_tags": [],
        "suffix": "",
        "description": "Neutral, baseline delivery",
    },
    "curious": {
        "prefix": "[wondering]",
        "mid_tags": ["[soft]"],
        "suffix": "",
        "description": "Inquisitive, exploratory tone",
    },
    "focused": {
        "prefix": "[steady]",
        "mid_tags": ["[emphasis]"],
        "suffix": "",
        "description": "Deliberate, precise delivery",
    },
    "improving": {
        "prefix": "[bright]",
        "mid_tags": ["[emphasis]"],
        "suffix": "",
        "description": "Optimistic, progressing tone",
    },
    "struggling": {
        "prefix": "[soft]",
        "mid_tags": ["[sighs]", "[slow]"],
        "suffix": "",
        "description": "Subdued, effortful delivery",
    },
    # Extended moods for DigitalEntity / future use
    "excited": {
        "prefix": "[emphasis][fast]",
        "mid_tags": ["[bright]"],
        "suffix": "",
        "description": "High energy, enthusiastic",
    },
    "frustrated": {
        "prefix": "[angry]",
        "mid_tags": ["[emphasis]", "[sighs]"],
        "suffix": "",
        "description": "Tense, irritated delivery",
    },
    "sad": {
        "prefix": "[soft][slow]",
        "mid_tags": ["[sighs]"],
        "suffix": "",
        "description": "Low energy, melancholic",
    },
    "reflective": {
        "prefix": "[soft]",
        "mid_tags": ["[slow]", "[whispers]"],
        "suffix": "",
        "description": "Contemplative, introspective",
    },
    "anxious": {
        "prefix": "[nervous][fast]",
        "mid_tags": ["[gasps]"],
        "suffix": "",
        "description": "Uneasy, rapid delivery",
    },
}


def inject_mood_tags(text: str, mood: str = "ready") -> str:
    """Inject Fish Audio S2 inline emotional tags into text based on mood.

    Splits text into sentences and applies prefix tags to the first sentence,
    mid-sentence tags distributed across the rest, preserving natural reading.

    Args:
        text: Plain text to augment with inline tags.
        mood: Current mood from OnyxKraken mind system.

    Returns:
        Text with inline tags inserted (no-op if mood is 'ready' or unknown).
    """
    if not text or not text.strip():
        return text

    mood_lower = mood.lower().strip()
    tags = FISH_AUDIO_MOOD_TAGS.get(mood_lower)
    if not tags or mood_lower == "ready":
        return text  # neutral mood → no tags

    # Split on sentence boundaries
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if not sentences:
        return text

    prefix = tags.get("prefix", "")
    mid_tags = tags.get("mid_tags", [])
    suffix = tags.get("suffix", "")

    # Apply prefix to first sentence
    if prefix:
        sentences[0] = f"{prefix} {sentences[0]}"

    # Distribute mid-tags across middle sentences
    if mid_tags and len(sentences) > 1:
        mid_indices = range(1, len(sentences))
        for i, idx in enumerate(mid_indices):
            tag = mid_tags[i % len(mid_tags)]
            sentences[idx] = f"{tag} {sentences[idx]}"

    # Apply suffix to last sentence
    if suffix:
        sentences[-1] = f"{sentences[-1]} {suffix}"

    return " ".join(sentences)


def _load_voice_settings() -> dict:
    """Load voice-related settings from settings.json."""
    try:
        from face.settings import load_settings
        return load_settings()
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# STT: Speech-to-Text
# ---------------------------------------------------------------------------

def _find_whisper_cpp() -> Optional[str]:
    """Auto-detect whisper.cpp executable."""
    if WHISPER_CPP_PATH and os.path.exists(WHISPER_CPP_PATH):
        return WHISPER_CPP_PATH
    candidates = [
        os.path.join(os.path.expanduser("~"), "whisper.cpp", "main.exe"),
        os.path.join(os.path.expanduser("~"), "whisper.cpp", "build", "bin", "Release", "main.exe"),
        r"C:\tools\whisper.cpp\main.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _record_audio(duration: float = RECORD_SECONDS_DEFAULT) -> Optional[str]:
    """Record audio from microphone and save as WAV file.

    Returns path to temporary WAV file, or None on failure.
    """
    try:
        import sounddevice as sd
        import numpy as np

        print(f"[Voice] Recording {duration}s of audio...")
        audio = sd.rec(
            int(duration * RECORD_RATE),
            samplerate=RECORD_RATE,
            channels=RECORD_CHANNELS,
            dtype="int16",
        )
        sd.wait()

        # Check for silence (all zeros or very low amplitude)
        if np.max(np.abs(audio)) < 100:
            print("[Voice] Recording appears to be silence.")
            return None

        # Save to temp WAV
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(RECORD_CHANNELS)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(RECORD_RATE)
            wf.writeframes(audio.tobytes())

        print(f"[Voice] Recorded to: {tmp.name}")
        return tmp.name

    except ImportError:
        print("[Voice] sounddevice not installed. Run: pip install sounddevice")
        return None
    except Exception as e:
        print(f"[Voice] Recording failed: {e}")
        return None


def transcribe_whisper_cpp(audio_path: str) -> Optional[str]:
    """Transcribe audio using whisper.cpp subprocess."""
    exe = _find_whisper_cpp()
    if not exe:
        return None
    if not os.path.exists(WHISPER_MODEL_PATH):
        print(f"[Voice] Whisper model not found: {WHISPER_MODEL_PATH}")
        return None

    try:
        result = subprocess.run(
            [exe, "-m", WHISPER_MODEL_PATH, "-f", audio_path, "--no-timestamps", "-nt"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            text = result.stdout.strip()
            # whisper.cpp sometimes outputs blank lines and metadata — grab last non-empty line
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            return lines[-1] if lines else None
        print(f"[Voice] whisper.cpp error: {result.stderr[:200]}")
    except Exception as e:
        print(f"[Voice] whisper.cpp failed: {e}")
    return None


def transcribe_whisper_python(audio_path: str) -> Optional[str]:
    """Transcribe audio using OpenAI Whisper Python package."""
    try:
        import whisper
        model = whisper.load_model("base.en")
        result = model.transcribe(audio_path)
        return result.get("text", "").strip() or None
    except ImportError:
        return None
    except Exception as e:
        print(f"[Voice] Whisper Python failed: {e}")
        return None


def listen(duration: float = RECORD_SECONDS_DEFAULT) -> Optional[str]:
    """Record from microphone and transcribe to text.

    Tries whisper.cpp first, then Whisper Python, returns None on failure.
    """
    audio_path = _record_audio(duration)
    if audio_path is None:
        return None

    try:
        # Try whisper.cpp first (fastest)
        text = transcribe_whisper_cpp(audio_path)
        if text:
            print(f"[Voice] Transcribed (whisper.cpp): {text[:80]}")
            return text

        # Fallback to Whisper Python
        text = transcribe_whisper_python(audio_path)
        if text:
            print(f"[Voice] Transcribed (whisper-python): {text[:80]}")
            return text

        print("[Voice] No STT backend available.")
        return None

    finally:
        try:
            os.remove(audio_path)
        except Exception:
            pass  # temp audio file cleanup is best-effort


# ---------------------------------------------------------------------------
# TTS: Text-to-Speech
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Fish Audio S2 TTS
# ---------------------------------------------------------------------------

def _get_fish_audio_config() -> dict:
    """Resolve Fish Audio S2 configuration from settings + env vars."""
    s = _load_voice_settings()
    return {
        "api_key": s.get("fish_audio_api_key", "") or FISH_AUDIO_API_KEY,
        "api_url": s.get("fish_audio_api_url", "") or FISH_AUDIO_API_URL,
        "local_url": s.get("fish_audio_local_url", "") or FISH_AUDIO_LOCAL_URL,
        "voice_id": s.get("fish_audio_voice_id", "") or FISH_AUDIO_VOICE_ID,
        "use_local": s.get("fish_audio_use_local", False),
    }


def speak_fish_audio(text: str, on_start=None, mood: str = "ready") -> bool:
    """Speak text using Fish Audio S2 API (cloud or local).

    Automatically injects mood-based inline tags if mood != 'ready'.
    Supports both the Fish Audio cloud API and local inference server.

    Args:
        text: Text to speak.
        on_start: Callback invoked right before playback.
        mood: Current mood for inline tag injection.

    Returns:
        True if speech was successfully synthesized and played.
    """
    cfg = _get_fish_audio_config()

    # Inject mood tags for emotional delivery
    tagged_text = inject_mood_tags(text, mood)
    _log.debug("[Fish S2] mood=%s, tagged: %s", mood, tagged_text[:120])

    # Choose local vs API
    if cfg["use_local"]:
        return _speak_fish_local(tagged_text, cfg, on_start, len(text))
    else:
        return _speak_fish_api(tagged_text, cfg, on_start, len(text))


def _speak_fish_api(text: str, cfg: dict, on_start=None,
                    orig_len: int = 0) -> bool:
    """Speak via Fish Audio cloud API."""
    api_key = cfg["api_key"]
    if not api_key:
        _log.debug("[Fish S2] No API key configured")
        return False

    try:
        import requests as _requests

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "format": "mp3",
            "latency": "normal",
        }
        # Add voice reference if configured
        voice_id = cfg.get("voice_id", "")
        if voice_id:
            payload["reference_id"] = voice_id

        resp = _requests.post(
            cfg["api_url"], json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            _log.warning("[Fish S2] API error: %d — %s",
                         resp.status_code, resp.text[:200])
            return False

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(resp.content)
        tmp.close()

        duration = _get_audio_duration(tmp.name)
        _play_audio_file(tmp.name, on_start=on_start, duration=duration,
                         text_len=orig_len or len(text))
        try:
            os.remove(tmp.name)
        except Exception:
            pass
        return True

    except ImportError:
        _log.debug("[Fish S2] requests not installed")
        return False
    except Exception as e:
        _log.warning("[Fish S2] API failed: %s", e)
        return False


def _speak_fish_local(text: str, cfg: dict, on_start=None,
                      orig_len: int = 0) -> bool:
    """Speak via local Fish Audio S2 inference server.

    Expects a local server at FISH_AUDIO_LOCAL_URL (default: localhost:8721)
    running the fish-speech inference server with the S2 model loaded.
    """
    try:
        import requests as _requests

        payload = {
            "text": text,
            "format": "wav",
        }
        voice_id = cfg.get("voice_id", "")
        if voice_id:
            payload["reference_id"] = voice_id

        resp = _requests.post(
            cfg["local_url"], json=payload,
            headers={"Content-Type": "application/json"}, timeout=60)
        if resp.status_code != 200:
            _log.warning("[Fish S2 local] error: %d", resp.status_code)
            return False

        suffix = ".wav" if "wav" in resp.headers.get("content-type", "") else ".mp3"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(resp.content)
        tmp.close()

        duration = _get_audio_duration(tmp.name)
        _play_audio_file(tmp.name, on_start=on_start, duration=duration,
                         text_len=orig_len or len(text))
        try:
            os.remove(tmp.name)
        except Exception:
            pass
        return True

    except ImportError:
        _log.debug("[Fish S2 local] requests not installed")
        return False
    except Exception as e:
        _log.warning("[Fish S2 local] failed: %s", e)
        return False


def _synth_fish_audio(text: str, mood: str = "ready") -> Optional[str]:
    """Synthesize to file via Fish Audio S2 (no playback).

    Used by synthesize_to_file() for pre-caching.
    """
    cfg = _get_fish_audio_config()
    tagged_text = inject_mood_tags(text, mood)

    try:
        import requests as _requests

        if cfg["use_local"]:
            url = cfg["local_url"]
            headers = {"Content-Type": "application/json"}
        else:
            if not cfg["api_key"]:
                return None
            url = cfg["api_url"]
            headers = {
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
            }

        payload = {"text": tagged_text, "format": "mp3"}
        if cfg.get("voice_id"):
            payload["reference_id"] = cfg["voice_id"]

        resp = _requests.post(url, json=payload, headers=headers, timeout=60)
        if resp.status_code != 200:
            return None

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(resp.content)
        tmp.close()
        return tmp.name
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Legacy TTS backends
# ---------------------------------------------------------------------------

def speak_pyttsx3(text: str, on_start=None) -> bool:
    """Speak text using pyttsx3 (Windows SAPI)."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 180)
        engine.setProperty("volume", 0.9)
        if on_start:
            on_start()
        start_t = time.time()
        engine.say(text)
        engine.runAndWait()
        # Save audio clip for recording if collector is active
        _tts_collector.register_pyttsx3_audio(text, start_t)
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"[Voice] pyttsx3 failed: {e}")
        return False


_TTS_CHANNEL_ID = 7  # dedicated pygame mixer channel for TTS playback


def _ensure_mixer_init():
    """Initialize pygame mixer once with consistent settings.

    Uses 44100 Hz stereo — standard for ElevenLabs and Edge TTS output.
    Allocates 8 channels so TTS and SFX don't collide.
    """
    import pygame
    if not pygame.mixer.get_init():
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
        pygame.mixer.set_num_channels(8)


def _play_audio_file(path: str, on_start=None, duration: float = 0.0,
                     text_len: int = 0):
    """Play an audio file on a **dedicated TTS channel** and block until done.

    Uses pygame.mixer.Sound on channel 7 so TTS audio is completely
    independent of pygame.mixer.music (used by MusicPlayer for background
    music).  Volume is always 1.0 regardless of music ducking.

    Falls back to os.startfile() if pygame is unavailable.
    on_start is called right before audio playback begins (for sync).
    duration/text_len are used to calculate mouth animation speed.
    """
    # Store duration-based chars_per_sec for mouth sync
    if duration > 0 and text_len > 0:
        cps = text_len / duration
        _last_tts_info["duration"] = duration
        _last_tts_info["text_len"] = text_len
        _last_tts_info["chars_per_sec"] = max(5.0, min(cps, 25.0))

    try:
        import pygame
        _ensure_mixer_init()

        sound = pygame.mixer.Sound(path)
        channel = pygame.mixer.Channel(_TTS_CHANNEL_ID)
        channel.set_volume(1.0)  # full volume, independent of music

        if on_start:
            on_start()
        start_t = time.time()
        channel.play(sound)
        # Register with TTS collector for recording
        _tts_collector.register_clip(path, start_t, duration,
                                     text="" if not text_len else "[tts]")
        while channel.get_busy():
            time.sleep(0.05)
        return
    except ImportError:
        pass  # pygame not installed
    except Exception as e:
        _log.debug("pygame TTS playback failed: %s", e)

    # Fallback: os.startfile (opens default media player)
    if on_start:
        on_start()
    start_t = time.time()
    _tts_collector.register_clip(path, start_t, duration,
                                 text="" if not text_len else "[tts]")
    os.startfile(path)
    time.sleep(max(1.0, os.path.getsize(path) / 16000))


def speak_edge_tts(text: str, on_start=None) -> bool:
    """Speak text using Edge TTS (higher quality, needs network)."""
    try:
        import asyncio
        import edge_tts

        # Read voice from settings, default to GuyNeural
        s = _load_voice_settings()
        voice = s.get("edge_tts_voice", "") or "en-US-GuyNeural"

        async def _speak():
            communicate = edge_tts.Communicate(text, voice)
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            await communicate.save(tmp.name)
            # Calculate audio duration for mouth sync
            duration = _get_audio_duration(tmp.name)
            _play_audio_file(tmp.name, on_start=on_start, duration=duration,
                             text_len=len(text))
            try:
                os.remove(tmp.name)
            except Exception:
                pass  # temp TTS file cleanup is best-effort

        asyncio.run(_speak())
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"[Voice] Edge TTS failed: {e}")
        return False


def speak_elevenlabs(text: str, on_start=None) -> bool:
    """Speak text using ElevenLabs API (premium quality, needs API key + network)."""
    # Read from settings.json first, then fall back to env vars
    s = _load_voice_settings()
    api_key = s.get("elevenlabs_api_key", "") or os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        return False
    voice_id = (s.get("elevenlabs_voice_id", "") or
                os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB"))
    model_id = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_monolingual_v1")

    try:
        import requests as _requests

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key,
        }
        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }
        resp = _requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"[Voice] ElevenLabs API error: {resp.status_code}")
            return False

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(resp.content)
        tmp.close()

        duration = _get_audio_duration(tmp.name)
        _play_audio_file(tmp.name, on_start=on_start, duration=duration,
                         text_len=len(text))
        try:
            os.remove(tmp.name)
        except Exception:
            pass
        return True

    except ImportError:
        print("[Voice] requests not installed for ElevenLabs.")
        return False
    except Exception as e:
        print(f"[Voice] ElevenLabs failed: {e}")
        return False


def _get_audio_duration(path: str) -> float:
    """Get audio duration in seconds. Returns 0 on failure."""
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        sound = pygame.mixer.Sound(path)
        dur = sound.get_length()
        del sound
        return dur
    except Exception:
        pass
    # Rough estimate from file size (mp3 ~16KB/s for speech)
    try:
        return max(1.0, os.path.getsize(path) / 16000)
    except Exception:
        return 0.0


# Global: last known TTS duration info for mouth sync
_last_tts_info = {"duration": 0.0, "text_len": 0, "chars_per_sec": 13.0}


# ---------------------------------------------------------------------------
# TTS Audio Collector — saves clips + timestamps for video embedding
# ---------------------------------------------------------------------------

@dataclass
class TTSClip:
    """A recorded TTS audio clip with its playback timestamp."""
    path: str           # path to the audio file (WAV or MP3)
    start_time: float   # time.time() when playback started
    duration: float     # estimated duration in seconds
    text: str = ""      # the spoken text


class TTSAudioCollector:
    """Collects TTS audio clips with timestamps for embedding into recordings.

    When active, each TTS call saves a copy of its audio file and records
    when playback started (relative to recording start). The ScreenRecorder
    uses these clips to compose audio into the final video.
    """

    def __init__(self):
        self._active = False
        self._lock = threading.Lock()
        self._clips: list[TTSClip] = []
        self._recording_start: float = 0.0
        self._clip_dir = os.path.join(tempfile.gettempdir(), "onyx_tts_clips")

    def start(self, recording_start_time: float):
        """Start collecting TTS clips. Called when recording begins."""
        with self._lock:
            self._active = True
            self._recording_start = recording_start_time
            self._clips = []
            os.makedirs(self._clip_dir, exist_ok=True)
            _log.info("TTS audio collector started")

    def stop(self) -> list[TTSClip]:
        """Stop collecting and return all clips. Caller owns cleanup."""
        with self._lock:
            self._active = False
            clips = list(self._clips)
            self._clips = []
            _log.info("TTS audio collector stopped: %d clips", len(clips))
            return clips

    @property
    def is_active(self) -> bool:
        return self._active

    def register_clip(self, source_path: str, start_time: float,
                      duration: float, text: str = ""):
        """Register a TTS audio clip that just started playing.

        Args:
            source_path: Path to the audio file (will be copied).
            start_time: time.time() when playback began.
            duration: Estimated duration in seconds.
            text: The spoken text.
        """
        if not self._active:
            return

        with self._lock:
            idx = len(self._clips)
            ext = os.path.splitext(source_path)[1] or ".wav"
            dest = os.path.join(self._clip_dir, f"tts_clip_{idx:04d}{ext}")
            try:
                shutil.copy2(source_path, dest)
                clip = TTSClip(
                    path=dest,
                    start_time=start_time - self._recording_start,
                    duration=duration,
                    text=text[:80],
                )
                self._clips.append(clip)
                _log.debug("TTS clip %d: %.1fs offset, %.1fs dur, '%s'",
                           idx, clip.start_time, duration, clip.text)
            except Exception as exc:
                _log.warning("Failed to save TTS clip: %s", exc)

    def register_pyttsx3_audio(self, text: str, start_time: float):
        """Save pyttsx3 speech to file and register it.

        pyttsx3 doesn't expose the audio file during playback, so we
        re-synthesize to a temp file after the fact.
        """
        if not self._active:
            return

        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 180)
            engine.setProperty("volume", 0.9)

            idx = len(self._clips)
            dest = os.path.join(self._clip_dir, f"tts_clip_{idx:04d}.wav")
            engine.save_to_file(text, dest)
            engine.runAndWait()

            if os.path.exists(dest) and os.path.getsize(dest) > 100:
                duration = _get_audio_duration(dest)
                with self._lock:
                    clip = TTSClip(
                        path=dest,
                        start_time=start_time - self._recording_start,
                        duration=duration,
                        text=text[:80],
                    )
                    self._clips.append(clip)
                    _log.debug("TTS pyttsx3 clip %d: %.1fs offset, %.1fs dur",
                               idx, clip.start_time, duration)
        except Exception as exc:
            _log.warning("Failed to save pyttsx3 clip: %s", exc)

    def cleanup(self):
        """Remove all saved clip files."""
        try:
            if os.path.isdir(self._clip_dir):
                shutil.rmtree(self._clip_dir, ignore_errors=True)
        except Exception:
            pass


# Module-level singleton
_tts_collector = TTSAudioCollector()


def get_tts_collector() -> TTSAudioCollector:
    """Get the global TTS audio collector."""
    return _tts_collector


def get_last_tts_chars_per_sec() -> float:
    """Return the calculated chars_per_sec from the most recent TTS playback."""
    return _last_tts_info.get("chars_per_sec", 13.0)


def speak(text: str, on_start=None, mood: str = "ready"):
    """Synthesize and play speech.

    Priority depends on tts_engine setting:
      'auto'       → Fish S2 → ElevenLabs → Edge TTS → pyttsx3
      'fish'       → Fish Audio S2 only (fallback to Edge)
      'elevenlabs' → ElevenLabs only (fallback to Edge)
      'edge'       → Edge TTS only (fallback to pyttsx3)
      'system'     → pyttsx3 only
    on_start is called right before audio playback begins (after synthesis).
    mood is passed to Fish Audio S2 for inline emotional tag injection.
    """
    if not text:
        return

    s = _load_voice_settings()
    engine = s.get("tts_engine", "auto")

    # Resolve mood from mind system if not explicitly provided
    if mood == "ready":
        try:
            from core.mind import mind
            mood = mind.get_mood()
        except Exception:
            pass

    if engine == "fish":
        if speak_fish_audio(text, on_start=on_start, mood=mood):
            return
        if speak_edge_tts(text, on_start=on_start):
            return
    elif engine == "elevenlabs":
        if speak_elevenlabs(text, on_start=on_start):
            return
        if speak_edge_tts(text, on_start=on_start):
            return
    elif engine == "edge":
        if speak_edge_tts(text, on_start=on_start):
            return
        if speak_pyttsx3(text, on_start=on_start):
            return
    elif engine == "system":
        if speak_pyttsx3(text, on_start=on_start):
            return
    else:  # 'auto' — try all in quality order
        if speak_fish_audio(text, on_start=on_start, mood=mood):
            return
        if speak_elevenlabs(text, on_start=on_start):
            return
        if speak_edge_tts(text, on_start=on_start):
            return
        if speak_pyttsx3(text, on_start=on_start):
            return

    print(f"[Voice] No TTS backend available. Text: {text[:100]}")


def speak_with_mood(text: str, mood: str = "ready", on_start=None):
    """Convenience wrapper: speak with explicit mood for emotional delivery.

    This is the recommended entry point when you want mood-aware speech.
    If Fish Audio S2 is not available, falls back to the normal speak() chain
    (mood tags are silently stripped for non-S2 backends).

    Args:
        text: Text to speak.
        mood: Mood name (confident, curious, struggling, etc.)
        on_start: Callback right before playback.
    """
    speak(text, on_start=on_start, mood=mood)


def speak_as(character: str, text: str, on_start=None):
    """Speak as a named character using their ElevenLabs voice ID.

    Characters:
      'xyno'  — Uses xyno_voice_id from settings
      'onyx'  — Uses elevenlabs_voice_id from settings (same as speak())

    Falls back to Edge TTS with a different voice if ElevenLabs unavailable.
    """
    if not text:
        return

    s = _load_voice_settings()
    api_key = s.get("elevenlabs_api_key", "") or os.environ.get("ELEVENLABS_API_KEY", "")

    if character.lower() == "xyno":
        voice_id = s.get("xyno_voice_id", "") or "iBo5PWT1qLiEyqhM7TrG"
        fallback_edge_voice = "en-US-AriaNeural"  # feminine contrast voice
    else:
        # Default to Onyx's own voice
        voice_id = (s.get("elevenlabs_voice_id", "") or
                    os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB"))
        fallback_edge_voice = s.get("edge_tts_voice", "") or "en-US-GuyNeural"

    # Try ElevenLabs with the character's voice
    if api_key and voice_id:
        if _speak_elevenlabs_with_voice(text, api_key, voice_id, on_start=on_start):
            return

    # Fallback: Edge TTS with a different voice
    if _speak_edge_tts_with_voice(text, fallback_edge_voice, on_start=on_start):
        return

    # Last resort: default speak()
    speak(text, on_start=on_start)


def _speak_elevenlabs_with_voice(text: str, api_key: str, voice_id: str,
                                  on_start=None) -> bool:
    """Speak via ElevenLabs with an explicit voice_id (no settings lookup)."""
    model_id = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_monolingual_v1")
    try:
        import requests as _requests
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key,
        }
        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        resp = _requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"[Voice] ElevenLabs API error ({voice_id[:8]}...): {resp.status_code}")
            return False

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(resp.content)
        tmp.close()

        duration = _get_audio_duration(tmp.name)
        _play_audio_file(tmp.name, on_start=on_start, duration=duration,
                         text_len=len(text))
        try:
            os.remove(tmp.name)
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"[Voice] ElevenLabs speak_as failed: {e}")
        return False


def _speak_edge_tts_with_voice(text: str, voice: str, on_start=None) -> bool:
    """Speak via Edge TTS with an explicit voice name."""
    try:
        import asyncio
        import edge_tts

        async def _speak():
            communicate = edge_tts.Communicate(text, voice)
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            await communicate.save(tmp.name)
            duration = _get_audio_duration(tmp.name)
            _play_audio_file(tmp.name, on_start=on_start, duration=duration,
                             text_len=len(text))
            try:
                os.remove(tmp.name)
            except Exception:
                pass

        asyncio.run(_speak())
        return True
    except Exception as e:
        print(f"[Voice] Edge TTS speak_as failed: {e}")
        return False


# ---------------------------------------------------------------------------
# ElevenLabs Sound Effects Generation (budget-aware)
# ---------------------------------------------------------------------------

_sfx_usage_this_session = 0


def elevenlabs_generate_sfx(prompt: str, duration_secs: float = 3.0,
                             save_path: str = "") -> Optional[str]:
    """Generate a sound effect using ElevenLabs Sound Generation API.

    Budget-aware: checks elevenlabs_sfx_budget setting. Returns path to
    the generated audio file, or None on failure/budget exceeded.

    Args:
        prompt: Text description of the sound effect (e.g. "dramatic whoosh")
        duration_secs: Desired duration in seconds (0.5 - 22)
        save_path: Optional explicit save path. If empty, uses temp file.
    """
    global _sfx_usage_this_session

    s = _load_voice_settings()
    api_key = s.get("elevenlabs_api_key", "") or os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        _log.warning("[SFX] No ElevenLabs API key for sound generation")
        return None

    budget = int(s.get("elevenlabs_sfx_budget", 10))
    if _sfx_usage_this_session >= budget:
        _log.info("[SFX] Budget exhausted (%d/%d) — skipping: %s",
                  _sfx_usage_this_session, budget, prompt)
        return None

    try:
        import requests as _requests
        url = "https://api.elevenlabs.io/v1/sound-generation"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key,
        }
        payload = {
            "text": prompt,
            "duration_seconds": max(0.5, min(22.0, duration_secs)),
        }
        resp = _requests.post(url, json=payload, headers=headers, timeout=60)
        if resp.status_code != 200:
            _log.warning("[SFX] ElevenLabs sound gen error: %d", resp.status_code)
            return None

        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(resp.content)
            out = save_path
        else:
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.write(resp.content)
            tmp.close()
            out = tmp.name

        _sfx_usage_this_session += 1
        _log.info("[SFX] Generated (%d/%d): %s -> %s",
                  _sfx_usage_this_session, budget, prompt, out)
        return out

    except Exception as e:
        _log.warning("[SFX] Sound generation failed: %s", e)
        return None


# Per-character Edge TTS voice map — each character gets a distinct voice
# so multi-character scenes sound like real ensembles.
CHARACTER_EDGE_VOICES = {
    "onyx":  "en-US-GuyNeural",           # male, balanced/neutral
    "xyno":  "en-US-AriaNeural",          # female, energetic/expressive
    "volt":  "en-US-ChristopherNeural",   # male, precise/analytical
    "nova":  "en-US-JennyNeural",         # female, warm/creative
    "sage":  "en-GB-RyanNeural",          # male, British/wise
    "blaze": "en-US-EricNeural",          # male, intense/commanding
    "frost": "en-AU-WilliamNeural",       # male, Australian/cool
    "ember": "en-US-MichelleNeural",      # female, friendly/warm
}


def synthesize_to_file(text: str, character: str = "onyx",
                       local_only: bool = False,
                       mood: str = "ready") -> Optional[str]:
    """Synthesize speech to a temp file WITHOUT playing it.

    Returns the file path on success, or None on failure.
    Used for pre-caching TTS audio so playback is instant.

    Args:
        text: Text to synthesize.
        character: Character name — selects the Edge TTS voice from
                   CHARACTER_EDGE_VOICES.
        local_only: If True, skip ElevenLabs and only use local
                    voices (Edge TTS / pyttsx3).  Useful for
                    multi-character scenes where each character
                    needs a distinct, instantly-available voice.
        mood: Current mood for Fish Audio S2 inline tag injection.
    """
    if not text:
        return None

    s = _load_voice_settings()

    # Try Fish Audio S2 first (supports mood-aware emotional tags)
    engine = s.get("tts_engine", "auto")
    if engine in ("fish", "auto"):
        path = _synth_fish_audio(text, mood=mood)
        if path:
            return path

    # Resolve Edge TTS voice for this character
    char_lower = character.lower()
    edge_voice = CHARACTER_EDGE_VOICES.get(
        char_lower,
        s.get("edge_tts_voice", "") or "en-US-GuyNeural",
    )

    # Try ElevenLabs (unless caller wants local-only)
    if not local_only:
        api_key = s.get("elevenlabs_api_key", "") or os.environ.get("ELEVENLABS_API_KEY", "")
        if api_key:
            if char_lower == "xyno":
                voice_id = s.get("xyno_voice_id", "") or "iBo5PWT1qLiEyqhM7TrG"
            else:
                voice_id = (s.get("elevenlabs_voice_id", "") or
                            os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB"))
            if voice_id:
                path = _synth_elevenlabs(text, api_key, voice_id)
                if path:
                    return path

    # Try Edge TTS (character-specific voice)
    path = _synth_edge(text, edge_voice)
    if path:
        return path

    # Try pyttsx3
    path = _synth_pyttsx3(text)
    if path:
        return path

    return None


def _synth_elevenlabs(text: str, api_key: str, voice_id: str) -> Optional[str]:
    """Synthesize to file via ElevenLabs (no playback)."""
    model_id = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_monolingual_v1")
    try:
        import requests as _requests
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key,
        }
        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        resp = _requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            return None
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(resp.content)
        tmp.close()
        return tmp.name
    except Exception:
        return None


def _synth_edge(text: str, voice: str) -> Optional[str]:
    """Synthesize to file via Edge TTS (no playback)."""
    try:
        import asyncio
        import edge_tts

        async def _do():
            communicate = edge_tts.Communicate(text, voice)
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            await communicate.save(tmp.name)
            return tmp.name

        return asyncio.run(_do())
    except Exception:
        return None


def _synth_pyttsx3(text: str) -> Optional[str]:
    """Synthesize to file via pyttsx3 (no playback)."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 180)
        engine.setProperty("volume", 0.9)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        engine.save_to_file(text, tmp.name)
        engine.runAndWait()
        if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 100:
            return tmp.name
        return None
    except Exception:
        return None


def play_tts_file(path: str):
    """Play a pre-synthesized TTS audio file (blocking).

    Used after synthesize_to_file() for instant playback with zero
    synthesis latency.
    """
    if not path or not os.path.exists(path):
        return
    duration = _get_audio_duration(path)
    _play_audio_file(path, duration=duration)


def reset_sfx_budget():
    """Reset the per-session SFX usage counter (call at episode start)."""
    global _sfx_usage_this_session
    _sfx_usage_this_session = 0


def get_sfx_usage() -> tuple:
    """Return (used, budget) for the current session."""
    s = _load_voice_settings()
    budget = int(s.get("elevenlabs_sfx_budget", 10))
    return (_sfx_usage_this_session, budget)


# ---------------------------------------------------------------------------
# Background Music Player (pygame mixer)
# ---------------------------------------------------------------------------

class MusicPlayer:
    """Manages background music playback with fade in/out.

    Uses pygame.mixer.music for background audio alongside TTS playback.
    TTS uses pygame.mixer.Sound (via _play_audio_file), and background
    music uses the separate pygame.mixer.music channel, so they can play
    simultaneously.
    """

    def __init__(self):
        self._playing = False
        self._current_path = ""
        self._volume = 0.3  # default low volume for background
        self._target_volume = 0.3
        self._fade_thread: Optional[threading.Thread] = None

    def play(self, path: str, volume: float = 0.3, fade_in: float = 2.0):
        """Start playing background music.

        Args:
            path: Path to audio file (mp3, wav, ogg).
            volume: Target volume (0.0 - 1.0). Keep low for background.
            fade_in: Fade-in duration in seconds.
        """
        try:
            import pygame
            _ensure_mixer_init()

            self._current_path = path
            self._target_volume = volume

            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.0)
            pygame.mixer.music.play(-1)  # loop indefinitely
            self._playing = True

            # Fade in on a thread
            if fade_in > 0:
                self._fade_to(volume, fade_in)
            else:
                pygame.mixer.music.set_volume(volume)
                self._volume = volume

            _log.info("[Music] Playing: %s (vol=%.2f, fade=%.1fs)",
                      os.path.basename(path), volume, fade_in)
        except Exception as e:
            _log.warning("[Music] Play failed: %s", e)

    def stop(self, fade_out: float = 2.0):
        """Stop background music with optional fade-out."""
        if not self._playing:
            return
        try:
            import pygame
            if fade_out > 0:
                self._fade_to(0.0, fade_out, stop_after=True)
            else:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
                self._playing = False
        except Exception as e:
            _log.warning("[Music] Stop failed: %s", e)

    def set_volume(self, volume: float, fade_time: float = 1.0):
        """Adjust volume (e.g. duck during speech, raise during breaks)."""
        self._target_volume = volume
        if fade_time > 0:
            self._fade_to(volume, fade_time)
        else:
            try:
                import pygame
                pygame.mixer.music.set_volume(volume)
                self._volume = volume
            except Exception:
                pass

    def _fade_to(self, target: float, duration: float, stop_after: bool = False):
        """Smoothly fade volume to target over duration seconds."""
        def _do_fade():
            try:
                import pygame
                steps = int(duration / 0.05)
                if steps < 1:
                    steps = 1
                current = self._volume
                step_size = (target - current) / steps
                for _ in range(steps):
                    current += step_size
                    current = max(0.0, min(1.0, current))
                    try:
                        pygame.mixer.music.set_volume(current)
                    except Exception:
                        break
                    time.sleep(0.05)
                self._volume = target
                if stop_after:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                    self._playing = False
            except Exception as e:
                _log.debug("[Music] Fade failed: %s", e)

        t = threading.Thread(target=_do_fade, daemon=True, name="MusicFade")
        t.start()
        self._fade_thread = t

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def volume(self) -> float:
        return self._volume


# Module-level music player singleton
_music_player = MusicPlayer()


def get_music_player() -> MusicPlayer:
    """Get the global background music player."""
    return _music_player
