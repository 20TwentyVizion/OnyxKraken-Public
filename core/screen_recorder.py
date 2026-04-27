"""Built-in screen recorder — captures the desktop to MP4 via mss + ffmpeg.

Supports optional TTS audio embedding: when audio is enabled, the recorder
activates a TTS audio collector that saves each speech clip with its
timestamp. On stop, ffmpeg composes all clips into the video at the
correct offsets — producing perfectly synced narration.

Usage:
    from core.screen_recorder import ScreenRecorder

    rec = ScreenRecorder(capture_audio=True)
    rec.start("my_demo")          # begins recording → data/recordings/my_demo_<ts>.mp4
    ...
    info = rec.stop()             # stops, embeds TTS audio, returns RecordingInfo
"""

import logging
import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import mss as _mss
except ImportError:
    _mss = None

_log = logging.getLogger("core.screen_recorder")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_FPS = 20
DEFAULT_OUTPUT_DIR = os.path.join("data", "recordings")
DEFAULT_QUALITY = "medium"  # low / medium / high / lossless
AUDIO_SAMPLE_RATE = 44100
AUDIO_CHANNELS = 2

# ffmpeg CRF presets (lower = better quality, bigger files)
_CRF_MAP = {
    "low": "32",
    "medium": "23",
    "high": "18",
    "lossless": "0",
}


# ---------------------------------------------------------------------------
# ScreenRecorder
# ---------------------------------------------------------------------------

@dataclass
class AudioSegment:
    """A span of audio playback that occurred during recording."""
    path: str
    start_offset: float       # seconds into recording when playback started
    end_offset: float = -1.0  # seconds into recording when stopped (-1 = still playing)
    volume: float = 0.3
    loop: bool = True          # True = source loops, False = plays once


@dataclass
class RecordingInfo:
    """Metadata for a completed recording."""
    path: str
    duration: float
    width: int
    height: int
    fps: int
    size_bytes: int = 0


class ScreenRecorder:
    """Capture the screen to MP4 using mss + ffmpeg.

    Thread-safe start/stop. Only one recording at a time.
    """

    def __init__(
        self,
        fps: int = DEFAULT_FPS,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        quality: str = DEFAULT_QUALITY,
        region: Optional[dict] = None,
        monitor: int = 1,
        capture_audio: bool = False,
    ):
        """
        Args:
            fps:           Target frames per second (10-60).
            output_dir:    Directory to save recordings.
            quality:       Encoding quality preset (low/medium/high/lossless).
            region:        Optional dict {left, top, width, height} to record a sub-region.
            monitor:       Monitor index for mss (1 = primary).
            capture_audio: If True, capture system audio via WASAPI loopback.
        """
        self.fps = max(5, min(60, fps))
        self.output_dir = output_dir
        self.quality = quality if quality in _CRF_MAP else "medium"
        self.region = region
        self.monitor = monitor
        self.capture_audio = capture_audio

        self._recording = False
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._ffmpeg_proc: Optional[subprocess.Popen] = None
        self._output_path: str = ""
        self._start_time: float = 0.0
        self._frame_count: int = 0
        self._width: int = 0
        self._height: int = 0
        self._stop_event = threading.Event()

        # Audio: TTS clip collector (activated during recording)
        self._tts_clips: list = []
        # Audio segments: tracks all music / beat playback events
        self._audio_segments: list[AudioSegment] = []
        self._current_segment: Optional[AudioSegment] = None
        self._audio_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self, name: str = "recording") -> str:
        """Start recording the screen.

        Args:
            name: Base name for the output file (timestamp is appended).

        Returns:
            The output file path that will be written to.

        Raises:
            RuntimeError: If already recording or ffmpeg is not found.
        """
        with self._lock:
            if self._recording:
                raise RuntimeError("Already recording. Call stop() first.")

            # Verify ffmpeg is available
            if not self._ffmpeg_available():
                raise RuntimeError(
                    "ffmpeg not found on PATH. Install it from https://ffmpeg.org"
                )

            os.makedirs(self.output_dir, exist_ok=True)

            ts = time.strftime("%Y%m%d_%H%M%S")
            safe_name = name.replace(" ", "_").replace("/", "_")
            self._output_path = os.path.join(
                self.output_dir, f"{safe_name}_{ts}.mp4"
            )

            # Determine capture region dimensions
            if _mss is None:
                raise RuntimeError("Screen recording requires 'mss'. Install with: pip install onyxkraken[desktop]")
            with _mss.mss() as sct:
                if self.region:
                    self._width = self.region["width"]
                    self._height = self.region["height"]
                else:
                    mon = sct.monitors[self.monitor]
                    self._width = mon["width"]
                    self._height = mon["height"]

            # Ensure even dimensions (required by H.264)
            self._width = self._width - (self._width % 2)
            self._height = self._height - (self._height % 2)

            self._frame_count = 0
            self._stop_event.clear()
            self._recording = True
            self._start_time = time.time()

            # Start ffmpeg process
            self._start_ffmpeg()

            # Start capture thread
            self._thread = threading.Thread(
                target=self._capture_loop, daemon=True, name="screen-recorder"
            )
            self._thread.start()

            # Start TTS audio collector if audio capture requested
            if self.capture_audio:
                self._start_tts_collector()

            _log.info(
                "Recording started: %s (%dx%d @ %dfps, quality=%s, audio=%s)",
                self._output_path, self._width, self._height,
                self.fps, self.quality, self.capture_audio,
            )
            return self._output_path

    def stop(self) -> Optional[RecordingInfo]:
        """Stop recording and finalize the MP4.

        If audio was captured, muxes video + audio into the final file.

        Returns:
            RecordingInfo with metadata, or None if not recording.
        """
        with self._lock:
            if not self._recording:
                _log.warning("stop() called but not recording.")
                return None

            self._recording = False
            self._stop_event.set()

        # Wait for video capture thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        # Close ffmpeg stdin to finalize the video file
        video_ok = False
        if self._ffmpeg_proc and self._ffmpeg_proc.stdin:
            try:
                self._ffmpeg_proc.stdin.close()
            except Exception:
                pass
            try:
                rc = self._ffmpeg_proc.wait(timeout=15.0)
                video_ok = (rc == 0)
                if rc != 0:
                    _log.warning("ffmpeg video exited with code %d", rc)
            except subprocess.TimeoutExpired:
                self._ffmpeg_proc.kill()
                _log.warning("ffmpeg video killed after timeout")

        # Brief delay to ensure file is flushed to disk
        time.sleep(0.5)

        # Verify video file exists and has content
        if video_ok and os.path.exists(self._output_path):
            fsize = os.path.getsize(self._output_path)
            if fsize < 1024:
                _log.warning("Video file too small (%d bytes), skipping mux", fsize)
                video_ok = False

        # Finalize any open audio segment
        self._end_current_segment()
        audio_segments = list(self._audio_segments)
        self._audio_segments.clear()

        # Compose TTS audio clips + music/beat segments into the video
        tts_clips = self._stop_tts_collector()
        has_audio = bool(tts_clips) or bool(audio_segments)
        if video_ok and has_audio and os.path.exists(self._output_path):
            self._compose_audio(self._output_path, tts_clips, audio_segments)

        duration = time.time() - self._start_time
        size = 0
        if os.path.exists(self._output_path):
            size = os.path.getsize(self._output_path)

        info = RecordingInfo(
            path=self._output_path,
            duration=duration,
            width=self._width,
            height=self._height,
            fps=self.fps,
            size_bytes=size,
        )

        _log.info(
            "Recording stopped: %s (%.1fs, %d frames, %.1f MB%s)",
            info.path, info.duration, self._frame_count,
            info.size_bytes / (1024 * 1024),
            f", with {len(tts_clips)} TTS clips" if tts_clips else "",
        )
        return info

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _ffmpeg_available() -> bool:
        """Check if ffmpeg is on PATH."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _start_ffmpeg(self):
        """Launch ffmpeg subprocess that reads raw BGRA frames from stdin."""
        crf = _CRF_MAP[self.quality]
        cmd = [
            "ffmpeg",
            "-y",                           # overwrite output
            "-f", "rawvideo",               # input format
            "-pixel_format", "bgra",        # mss gives BGRA
            "-video_size", f"{self._width}x{self._height}",
            "-framerate", str(self.fps),
            "-i", "pipe:0",                 # read from stdin
            "-c:v", "libx264",             # H.264 codec
            "-preset", "ultrafast",         # fast encoding for real-time
            "-crf", crf,
            "-pix_fmt", "yuv420p",          # compatibility
            "-movflags", "+faststart",      # web-friendly MP4
            self._output_path,
        ]
        _log.debug("ffmpeg command: %s", " ".join(cmd))
        self._ffmpeg_proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def _capture_loop(self):
        """Background thread: capture frames and pipe to ffmpeg."""
        frame_interval = 1.0 / self.fps
        _log.debug("Capture loop started (interval=%.3fs)", frame_interval)

        try:
            with _mss.mss() as sct:
                if self.region:
                    mon = self.region
                else:
                    mon = sct.monitors[self.monitor]
                    # Adjust to even dimensions
                    mon = {
                        "left": mon["left"],
                        "top": mon["top"],
                        "width": self._width,
                        "height": self._height,
                    }

                while not self._stop_event.is_set():
                    t0 = time.perf_counter()

                    # Capture frame
                    raw = sct.grab(mon)
                    frame_bytes = bytes(raw.raw)  # BGRA pixels

                    # Pipe to ffmpeg
                    if self._ffmpeg_proc and self._ffmpeg_proc.stdin:
                        try:
                            self._ffmpeg_proc.stdin.write(frame_bytes)
                            self._frame_count += 1
                        except (BrokenPipeError, OSError):
                            _log.error("ffmpeg pipe broken, stopping capture.")
                            break

                    # Maintain target FPS
                    elapsed = time.perf_counter() - t0
                    sleep_time = frame_interval - elapsed
                    if sleep_time > 0:
                        self._stop_event.wait(sleep_time)

        except Exception as exc:
            _log.error("Capture loop error: %s", exc, exc_info=True)

        _log.debug("Capture loop ended (%d frames)", self._frame_count)

    # ------------------------------------------------------------------
    # TTS Audio Composition (replaces broken loopback capture)
    # ------------------------------------------------------------------

    def _start_tts_collector(self):
        """Activate the TTS audio collector to save speech clips."""
        try:
            from core.voice import get_tts_collector
            collector = get_tts_collector()
            collector.start(self._start_time)
            _log.info("TTS audio collector activated for recording")
        except Exception as exc:
            _log.warning("Failed to start TTS collector: %s", exc)

    def _stop_tts_collector(self) -> list:
        """Stop TTS collector and return clips."""
        try:
            from core.voice import get_tts_collector
            collector = get_tts_collector()
            return collector.stop()
        except Exception as exc:
            _log.warning("Failed to stop TTS collector: %s", exc)
            return []

    def set_music_track(self, path: str, volume: float = 0.20):
        """Register the background music file to include in composition.

        Called by the stage/show system when music starts playing so the
        recorder can add the music to the final video alongside TTS clips.
        """
        if not path or not os.path.exists(path):
            return
        with self._audio_lock:
            self._end_current_segment()
            seg = AudioSegment(
                path=path,
                start_offset=max(0.0, time.time() - self._start_time),
                volume=max(0.05, min(1.0, volume)),
                loop=True,
            )
            self._current_segment = seg
            self._audio_segments.append(seg)
            _log.info("Audio segment started: %s (offset=%.1fs, vol=%.2f)",
                      os.path.basename(path), seg.start_offset, volume)

    def clear_music_track(self):
        """End the current audio segment (e.g. when music stops)."""
        with self._audio_lock:
            self._end_current_segment()

    def add_audio_segment(self, path: str, volume: float = 0.5, loop: bool = False):
        """Register an audio file playing right now (e.g. a generated beat).

        Unlike set_music_track, this does NOT end the previous segment first
        (both can overlap). Use end_audio_segment() to mark it as stopped.
        """
        if not path or not os.path.exists(path):
            return
        with self._audio_lock:
            seg = AudioSegment(
                path=path,
                start_offset=max(0.0, time.time() - self._start_time),
                volume=max(0.05, min(1.0, volume)),
                loop=loop,
            )
            self._current_segment = seg
            self._audio_segments.append(seg)
            _log.info("Audio segment started (beat): %s (offset=%.1fs, vol=%.2f)",
                      os.path.basename(path), seg.start_offset, volume)

    def end_audio_segment(self):
        """End the most recent audio segment."""
        with self._audio_lock:
            self._end_current_segment()

    def _end_current_segment(self):
        """Mark the current segment as ended (caller holds _audio_lock)."""
        if self._current_segment and self._current_segment.end_offset < 0:
            self._current_segment.end_offset = max(
                0.0, time.time() - self._start_time)
            _log.debug("Audio segment ended at %.1fs",
                       self._current_segment.end_offset)
        self._current_segment = None

    def _compose_audio(self, video_path: str, tts_clips: list,
                        audio_segments: list[AudioSegment]):
        """Compose TTS clips + music/beat audio segments onto the video.

        Each AudioSegment is trimmed to its actual duration, delayed to its
        start offset, and volume-adjusted.  TTS clips are handled the same
        way as before.  All streams are mixed together and muxed with the
        video track.
        """
        if not tts_clips and not audio_segments:
            return

        recording_dur = time.time() - self._start_time
        _log.info("Composing audio: %d TTS clips + %d audio segments (%.0fs video)",
                  len(tts_clips), len(audio_segments), recording_dur)

        inputs = ["-i", video_path]
        filter_parts = []
        delayed_labels = []
        input_idx = 1  # 0 = video

        # --- TTS clips ---
        valid_clips = []
        for clip in tts_clips:
            if not os.path.exists(clip.path):
                continue
            if os.path.getsize(clip.path) < 100:
                continue
            inputs.extend(["-i", clip.path])
            delay_ms = max(0, int(clip.start_time * 1000))
            label = f"tts{input_idx}"
            filter_parts.append(
                f"[{input_idx}:a]adelay={delay_ms}|{delay_ms},"
                f"aformat=sample_rates=44100:channel_layouts=stereo[{label}]"
            )
            delayed_labels.append(f"[{label}]")
            valid_clips.append(clip)
            input_idx += 1

        # --- Audio segments (background music, generated beats, etc.) ---
        for seg_i, seg in enumerate(audio_segments):
            if not os.path.exists(seg.path):
                _log.warning("Audio segment missing: %s", seg.path)
                continue

            # Calculate how long this segment played
            end = seg.end_offset if seg.end_offset >= 0 else recording_dur
            seg_duration = max(0.1, end - seg.start_offset)

            # For looped sources, use -stream_loop so ffmpeg extends the audio
            if seg.loop:
                inputs.extend(["-stream_loop", "-1", "-i", seg.path])
            else:
                inputs.extend(["-i", seg.path])

            delay_ms = max(0, int(seg.start_offset * 1000))
            vol_str = f"{seg.volume:.2f}"
            label = f"seg{seg_i}"

            # atrim trims the output to the segment's duration,
            # adelay positions it at the right time, volume adjusts level
            filter_parts.append(
                f"[{input_idx}:a]"
                f"atrim=0:{seg_duration:.2f},asetpts=PTS-STARTPTS,"
                f"adelay={delay_ms}|{delay_ms},"
                f"volume={vol_str},"
                f"aformat=sample_rates=44100:channel_layouts=stereo[{label}]"
            )
            delayed_labels.append(f"[{label}]")
            input_idx += 1

        if not delayed_labels:
            _log.warning("No valid audio streams to compose")
            self._cleanup_tts_clips(tts_clips)
            return

        # Mix all streams
        mix_inputs = "".join(delayed_labels)
        filter_parts.append(
            f"{mix_inputs}amix=inputs={len(delayed_labels)}:"
            f"duration=longest:dropout_transition=0:normalize=0[amixed]"
        )
        # Boost final volume — TTS clips tend to be quiet
        filter_parts.append("[amixed]volume=2.0[aout]")

        filter_graph = "; ".join(filter_parts)

        muxed_path = video_path.replace(".mp4", "_muxed.mp4")
        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_graph,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            muxed_path,
        ]

        try:
            _log.debug("Audio compose cmd: %s", " ".join(cmd))
            result = subprocess.run(
                cmd, capture_output=True, timeout=300,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0 and os.path.exists(muxed_path):
                fsize = os.path.getsize(muxed_path)
                if fsize > 1024:
                    os.replace(muxed_path, video_path)
                    _log.info("Audio composed into %s (%d TTS + %d segments)",
                              video_path, len(valid_clips), len(audio_segments))
                else:
                    _log.warning("Composed file too small (%d bytes)", fsize)
                    os.remove(muxed_path)
            else:
                stderr = result.stderr.decode(errors="replace")[-500:] if result.stderr else ""
                _log.warning("ffmpeg audio compose failed (code %d): %s",
                             result.returncode, stderr)
                if os.path.exists(muxed_path):
                    os.remove(muxed_path)
        except subprocess.TimeoutExpired:
            _log.error("ffmpeg audio compose timed out")
            if os.path.exists(muxed_path):
                try:
                    os.remove(muxed_path)
                except Exception:
                    pass
        except Exception as exc:
            _log.error("Audio compose error: %s", exc)
            if os.path.exists(muxed_path):
                try:
                    os.remove(muxed_path)
                except Exception:
                    pass
        finally:
            self._cleanup_tts_clips(tts_clips)

    @staticmethod
    def _cleanup_tts_clips(clips: list):
        """Remove temp TTS clip files."""
        try:
            from core.voice import get_tts_collector
            get_tts_collector().cleanup()
        except Exception:
            pass
        for clip in clips:
            try:
                if os.path.exists(clip.path):
                    os.remove(clip.path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_default_recorder: Optional[ScreenRecorder] = None


def get_recorder(**kwargs) -> ScreenRecorder:
    """Get or create the default ScreenRecorder singleton."""
    global _default_recorder
    if _default_recorder is None:
        _default_recorder = ScreenRecorder(**kwargs)
    return _default_recorder


def start_recording(name: str = "recording", **kwargs) -> str:
    """Start recording with the default recorder. Returns output path."""
    rec = get_recorder(**kwargs)
    return rec.start(name)


def stop_recording() -> Optional[RecordingInfo]:
    """Stop the default recorder and return info."""
    global _default_recorder
    if _default_recorder is None:
        return None
    info = _default_recorder.stop()
    _default_recorder = None
    return info


def is_recording() -> bool:
    """Check if the default recorder is active."""
    return _default_recorder is not None and _default_recorder.is_recording
