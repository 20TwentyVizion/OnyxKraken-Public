"""Chain Workflow Engine — orchestrates multi-step production pipelines.

Onyx can chain its capabilities together:
  Screen Recording → Music Generation → Video Editing → Export

Each workflow is a sequence of steps where outputs flow into inputs.
The engine handles narration, progress tracking, error recovery, and
persistence of intermediate artifacts.

Usage:
    from core.chain_workflow import run_workflow, list_workflows

    # Run the full production pipeline
    run_workflow("full_production", narrate_fn=speak, on_progress=update_ui)

    # List available chain workflows
    for wf in list_workflows():
        print(wf["id"], wf["title"])

CLI:
    python -m core.chain_workflow full_production
    python -m core.chain_workflow --list
"""

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

_log = logging.getLogger("core.chain_workflow")

_ROOT = Path(__file__).resolve().parent.parent
_OUTPUT_DIR = _ROOT / "output" / "chain_workflows"
_RECORDINGS_DIR = _ROOT / "data" / "recordings"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    """Result of a single workflow step."""
    success: bool
    message: str = ""
    data: dict = field(default_factory=dict)
    duration: float = 0.0
    error: str = ""


@dataclass
class WorkflowResult:
    """Result of a complete workflow run."""
    workflow_id: str
    success: bool
    steps_completed: int
    steps_total: int
    duration: float = 0.0
    outputs: dict = field(default_factory=dict)
    error: str = ""
    narration_log: list = field(default_factory=list)


# Type for step functions: takes context dict, returns StepResult
StepFn = Callable[[dict], StepResult]
NarrateFn = Callable[[str], None]
ProgressFn = Callable[[int, int, str], None]


# Condition function: takes context dict, returns bool
ConditionFn = Callable[[dict], bool]


@dataclass
class ChainStep:
    """A single step in a chain workflow."""
    id: str
    name: str
    description: str
    execute: StepFn
    narration_before: str = ""      # What Onyx says before running this step
    narration_after: str = ""       # Template with {result} placeholder
    narration_error: str = ""       # What Onyx says on failure
    estimated_seconds: int = 10
    optional: bool = False          # If True, failure doesn't stop the workflow
    skip_if: str = ""               # Context key — skip step if this key is falsy
    # v2 features
    condition: Optional[ConditionFn] = None  # Dynamic skip: run only if condition(ctx) is True
    retry_count: int = 0            # Number of retries on failure (0 = no retry)
    retry_delay: float = 5.0        # Seconds between retries (doubles each attempt)
    parallel_with: str = ""         # ID of another step to run in parallel with
    preflight_services: list[str] = field(default_factory=list)  # Required services check


@dataclass
class ChainWorkflow:
    """A named chain workflow with metadata."""
    id: str
    title: str
    description: str
    steps: list[ChainStep]
    tags: list[str] = field(default_factory=list)
    estimated_minutes: int = 5
    # Personality lines
    intro_narration: str = ""
    success_narration: str = ""
    failure_narration: str = ""


# ---------------------------------------------------------------------------
# Workflow engine
# ---------------------------------------------------------------------------

class WorkflowEngine:
    """Executes chain workflows with narration and progress tracking.

    v2 features:
      - Parallel steps (via parallel_with)
      - Conditional branching (via condition function)
      - Retry with exponential backoff
      - Pre-flight service checks
      - Telemetry integration
    """

    def __init__(
        self,
        narrate_fn: Optional[NarrateFn] = None,
        on_progress: Optional[ProgressFn] = None,
    ):
        self.narrate = narrate_fn or (lambda text: None)
        self.on_progress = on_progress or (lambda cur, total, msg: None)
        self._running = True

    def stop(self):
        self._running = False

    def _preflight_check(self, step: ChainStep) -> tuple[bool, str]:
        """Ensure required services are running before a step.

        Unlike a passive check, this actively auto-starts any missing
        service using core.service_launcher.  Only fails if a service
        cannot be started at all.
        """
        if not step.preflight_services:
            return True, ""
        try:
            from core.service_launcher import ensure_services
            all_ok, failures = ensure_services(step.preflight_services)
            if not all_ok:
                return False, "; ".join(failures)
        except ImportError:
            # Fallback: passive check via system_health
            try:
                from core.system_health import health
                for svc_name in step.preflight_services:
                    svc_lower = svc_name.lower()
                    if svc_lower == "ollama":
                        svc = health.check_ollama()
                    elif svc_lower in ("acestep", "ace-step"):
                        svc = health.check_acestep()
                    elif svc_lower == "justedit":
                        svc = health.check_justedit()
                    elif svc_lower == "ffmpeg":
                        svc = health.check_ffmpeg()
                    else:
                        continue
                    if not svc.running:
                        return False, f"{svc_name} is not running (auto-start unavailable)"
            except ImportError:
                pass
        return True, ""

    def _execute_step(self, step: ChainStep, ctx: dict) -> StepResult:
        """Execute a single step with retry logic."""
        attempts = 1 + step.retry_count
        delay = step.retry_delay
        last_result = None

        for attempt in range(attempts):
            step_start = time.time()
            try:
                result = step.execute(ctx)
                result.duration = time.time() - step_start
            except Exception as exc:
                _log.error("Step '%s' attempt %d raised: %s",
                          step.id, attempt + 1, exc, exc_info=True)
                result = StepResult(
                    success=False,
                    error=str(exc),
                    duration=time.time() - step_start,
                )

            last_result = result
            if result.success:
                return result

            # Retry?
            if attempt < attempts - 1:
                _log.info("Step '%s' failed (attempt %d/%d), retrying in %.0fs",
                          step.id, attempt + 1, attempts, delay)
                time.sleep(delay)
                delay *= 2  # exponential backoff

        return last_result

    def _execute_parallel(self, step_a: ChainStep, step_b: ChainStep,
                          ctx: dict) -> tuple[StepResult, StepResult]:
        """Execute two steps in parallel threads."""
        import concurrent.futures

        # Each thread gets a copy of context to avoid races
        ctx_a = dict(ctx)
        ctx_b = dict(ctx)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            future_a = pool.submit(self._execute_step, step_a, ctx_a)
            future_b = pool.submit(self._execute_step, step_b, ctx_b)
            result_a = future_a.result(timeout=600)
            result_b = future_b.result(timeout=600)

        # Merge both contexts back (a takes priority on conflicts)
        if result_b.data:
            ctx.update(result_b.data)
        if result_a.data:
            ctx.update(result_a.data)

        return result_a, result_b

    def _record_telemetry(self, workflow_id: str, step: ChainStep,
                          result: StepResult):
        """Record step execution in telemetry."""
        try:
            from core.telemetry import telemetry
            telemetry.record(
                action_type="chain",
                intent=f"{workflow_id}/{step.id}: {step.name}",
                result="success" if result.success else "failure",
                result_detail=result.message,
                duration=result.duration,
                error=result.error,
                workflow_id=workflow_id,
                step_id=step.id,
            )
        except Exception:
            pass

    def run(self, workflow: ChainWorkflow, context: dict | None = None) -> WorkflowResult:
        """Execute a workflow step by step, passing context between steps."""
        ctx = dict(context) if context else {}
        ctx.setdefault("output_dir", str(_OUTPUT_DIR))
        ctx.setdefault("recordings_dir", str(_RECORDINGS_DIR))
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        steps = workflow.steps
        total = len(steps)
        completed = 0
        start_time = time.time()
        narration_log = []
        outputs = {}
        # Track which steps were already run in parallel
        parallel_done: set[str] = set()

        _log.info("Chain workflow starting: %s (%d steps)", workflow.id, total)

        # Intro narration
        if workflow.intro_narration:
            self.narrate(workflow.intro_narration)
            narration_log.append(("intro", workflow.intro_narration))
            time.sleep(0.5)

        for i, step in enumerate(steps):
            if not self._running:
                return WorkflowResult(
                    workflow_id=workflow.id,
                    success=False,
                    steps_completed=completed,
                    steps_total=total,
                    duration=time.time() - start_time,
                    outputs=outputs,
                    error="Workflow cancelled",
                    narration_log=narration_log,
                )

            # Skip if already executed as part of a parallel pair
            if step.id in parallel_done:
                continue

            # Check skip condition (string key)
            if step.skip_if and not ctx.get(step.skip_if):
                _log.info("Skipping step '%s' (condition '%s' not met)",
                          step.id, step.skip_if)
                continue

            # Check dynamic condition function
            if step.condition is not None and not step.condition(ctx):
                _log.info("Skipping step '%s' (condition function returned False)",
                          step.id)
                continue

            # Pre-flight service check
            pf_ok, pf_reason = self._preflight_check(step)
            if not pf_ok:
                _log.warning("Step '%s' preflight failed: %s", step.id, pf_reason)
                if step.optional:
                    continue
                return WorkflowResult(
                    workflow_id=workflow.id,
                    success=False,
                    steps_completed=completed,
                    steps_total=total,
                    duration=time.time() - start_time,
                    outputs=outputs,
                    error=f"Preflight failed for '{step.id}': {pf_reason}",
                    narration_log=narration_log,
                )

            self.on_progress(i + 1, total, step.name)
            _log.info("Step %d/%d: %s — %s", i + 1, total, step.id, step.name)

            # Pre-step narration
            if step.narration_before:
                self.narrate(step.narration_before)
                narration_log.append((step.id + "_before", step.narration_before))
                time.sleep(0.3)

            # Check for parallel execution
            parallel_step = None
            if step.parallel_with:
                parallel_step = next(
                    (s for s in steps if s.id == step.parallel_with), None
                )

            if parallel_step and parallel_step.id not in parallel_done:
                # Execute both in parallel
                _log.info("Running '%s' and '%s' in parallel",
                          step.id, parallel_step.id)
                if parallel_step.narration_before:
                    self.narrate(parallel_step.narration_before)
                result, par_result = self._execute_parallel(step, parallel_step, ctx)
                parallel_done.add(parallel_step.id)

                # Merge parallel step outputs
                if par_result.data:
                    outputs.update(par_result.data)
                self._record_telemetry(workflow.id, parallel_step, par_result)
                if par_result.success:
                    completed += 1
            else:
                # Sequential execution with retry
                result = self._execute_step(step, ctx)

            # Merge step outputs into context for downstream steps
            if result.data:
                ctx.update(result.data)
                outputs.update(result.data)

            # Record telemetry
            self._record_telemetry(workflow.id, step, result)

            # Post-step narration
            if result.success:
                completed += 1
                if step.narration_after:
                    msg = step.narration_after.format(
                        result=result.message,
                        **{k: v for k, v in result.data.items()
                           if isinstance(v, (str, int, float))}
                    )
                    self.narrate(msg)
                    narration_log.append((step.id + "_after", msg))
                _log.info("Step '%s' complete: %s (%.1fs)",
                          step.id, result.message, result.duration)
            else:
                err_msg = step.narration_error or f"Step {step.name} hit a snag."
                self.narrate(err_msg)
                narration_log.append((step.id + "_error", err_msg))
                _log.warning("Step '%s' failed: %s", step.id, result.error)

                if not step.optional:
                    # Workflow failure narration
                    if workflow.failure_narration:
                        self.narrate(workflow.failure_narration)
                        narration_log.append(("failure", workflow.failure_narration))

                    return WorkflowResult(
                        workflow_id=workflow.id,
                        success=False,
                        steps_completed=completed,
                        steps_total=total,
                        duration=time.time() - start_time,
                        outputs=outputs,
                        error=f"Step '{step.id}' failed: {result.error}",
                        narration_log=narration_log,
                    )

        # Success narration
        duration = time.time() - start_time
        if workflow.success_narration:
            self.narrate(workflow.success_narration)
            narration_log.append(("success", workflow.success_narration))

        _log.info("Chain workflow complete: %s (%.1fs, %d/%d steps)",
                  workflow.id, duration, completed, total)

        return WorkflowResult(
            workflow_id=workflow.id,
            success=True,
            steps_completed=completed,
            steps_total=total,
            duration=duration,
            outputs=outputs,
            narration_log=narration_log,
        )


# ---------------------------------------------------------------------------
# Utility: ffprobe video duration
# ---------------------------------------------------------------------------

def probe_video_duration(path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, timeout=15, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as exc:
        _log.warning("ffprobe failed for %s: %s", path, exc)

    # Fallback: estimate from file size (rough: ~1 MB per 10 seconds at medium quality)
    try:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        return size_mb * 10  # very rough estimate
    except Exception:
        return 60.0  # default 1 minute


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------

def _step_record_demo(ctx: dict) -> StepResult:
    """Record Onyx performing a demo (Notepad + Browser tasks)."""
    from core.screen_recorder import ScreenRecorder

    rec = ScreenRecorder(fps=20, quality="high", capture_audio=True)
    demo_name = ctx.get("demo_name", "chain_demo")
    path = rec.start(demo_name)
    ctx["_recorder"] = rec

    # Perform demo tasks using pyautogui directly
    try:
        import pyautogui
        pyautogui.FAILSAFE = True

        # Task 1: Open Notepad and type a message
        _log.info("Demo task: Opening Notepad")
        try:
            subprocess.Popen(["notepad.exe"])
            time.sleep(2.0)
            pyautogui.typewrite(
                "OnyxKraken autonomous demo\n\n"
                "This video was recorded, scored, edited, and exported\n"
                "entirely by an AI agent.\n\n"
                "Full production pipeline running autonomously.",
                interval=0.03,
            )
            time.sleep(2.0)
        except Exception as exc:
            _log.warning("Notepad demo task failed: %s", exc)

        # Task 2: Open a browser to a URL
        _log.info("Demo task: Opening browser")
        try:
            import webbrowser
            webbrowser.open("https://github.com/")
            time.sleep(5.0)
        except Exception as exc:
            _log.warning("Browser demo task failed: %s", exc)

        # Pause for a few extra seconds of footage
        time.sleep(3.0)

        # Close the demo apps
        try:
            pyautogui.hotkey("alt", "F4")
            time.sleep(1.5)
            pyautogui.hotkey("alt", "F4")
            time.sleep(1.0)
        except Exception:
            pass

    except ImportError:
        _log.warning("pyautogui not available — simulating demo with delay")
        time.sleep(ctx.get("demo_duration", 30))

    info = rec.stop()
    del ctx["_recorder"]

    if info and os.path.exists(info.path):
        return StepResult(
            success=True,
            message=f"Recorded {info.duration:.0f}s video ({info.size_bytes / 1024 / 1024:.1f} MB)",
            data={
                "recording_path": info.path,
                "recording_duration": info.duration,
                "recording_size_mb": info.size_bytes / (1024 * 1024),
            },
        )
    return StepResult(success=False, error="Recording failed — no output file")


def _step_probe_duration(ctx: dict) -> StepResult:
    """Check the recorded video's actual duration with ffprobe."""
    path = ctx.get("recording_path", "")
    if not path or not os.path.exists(path):
        return StepResult(success=False, error="No recording path in context")

    duration = probe_video_duration(path)
    return StepResult(
        success=True,
        message=f"Video is {duration:.1f} seconds ({duration / 60:.1f} min)",
        data={"video_duration": duration},
    )


def _step_generate_music(ctx: dict) -> StepResult:
    """Generate music matching the video duration using DJ Mode / EVERA."""
    video_dur = ctx.get("video_duration", 60)
    genre = ctx.get("music_genre", "lo-fi")
    quality = ctx.get("music_quality", "quick_draft")

    # Determine track count: one track per ~60s of video
    max_track_len = 60.0  # EVERA max per generation
    track_count = max(1, int(video_dur / max_track_len + 0.5))

    _log.info("Generating %d track(s), genre=%s, target=%.0fs", track_count, genre, video_dur)

    try:
        from apps.dj_mode import DJSession, DJPreferences
        prefs = DJPreferences(
            genre=genre,
            quality=quality,
            num_tracks=track_count,
            duration=min(int(video_dur), 300),
        )
        session = DJSession(prefs)
        result = session.run()

        if result.tracks:
            # Use the first track (or concatenate if multiple)
            first_track = result.tracks[0]
            track_path = first_track.audio_path
            all_paths = [t.audio_path for t in result.tracks if t.audio_path]

            return StepResult(
                success=True,
                message=f"Generated {len(result.tracks)} track(s) in {genre}",
                data={
                    "music_path": track_path,
                    "music_paths": all_paths,
                    "music_genre": genre,
                    "music_tracks_count": len(result.tracks),
                    "dj_session_id": result.session_id,
                },
            )
        return StepResult(success=False, error="DJ session produced no tracks")

    except ImportError:
        _log.warning("DJ Mode not available, trying EVERA client directly")

    # Fallback: direct EVERA client
    try:
        from apps.evera_client import EveraClient
        client = EveraClient()
        resp = client.generate_track(
            genre=genre,
            mood="chill",
            instrumental=True,
            duration=min(video_dur, 60),
        )
        track_path = resp.get("local_copy", resp.get("filepath", ""))
        if track_path:
            return StepResult(
                success=True,
                message=f"Generated {genre} track via EVERA",
                data={"music_path": track_path, "music_genre": genre},
            )
    except Exception as exc:
        return StepResult(success=False, error=f"Music generation failed: {exc}")

    return StepResult(success=False, error="No music generation backend available")


def _step_assemble_justedit(ctx: dict) -> StepResult:
    """Combine video + music in JustEdit, creating a complete project."""
    from apps.modules.justedit import JustEditModule

    recording_path = ctx.get("recording_path", "")
    music_path = ctx.get("music_path", "")
    title_text = ctx.get("video_title", "OnyxKraken")

    if not recording_path or not os.path.exists(recording_path):
        return StepResult(success=False, error="No recording file found")

    je = JustEditModule()
    project_path = je.create_demo_video(
        screen_recording=recording_path,
        bgm_audio=music_path if music_path and os.path.exists(music_path) else "",
        title=title_text,
        outro_text="Built by OnyxKraken",
    )

    return StepResult(
        success=True,
        message=f"JustEdit project assembled",
        data={
            "justedit_project": project_path,
        },
    )


def _step_export_video(ctx: dict) -> StepResult:
    """Mux video + music into a final MP4 using ffmpeg.

    This creates the actual rendered output file. JustEdit's client-side
    ffmpeg is slower, so we use native ffmpeg for the final render.
    """
    recording_path = ctx.get("recording_path", "")
    music_path = ctx.get("music_path", "")
    video_dur = ctx.get("video_duration", 0)

    if not recording_path or not os.path.exists(recording_path):
        return StepResult(success=False, error="No recording to export")

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    output_path = str(_OUTPUT_DIR / f"onyx_production_{ts}.mp4")

    if music_path and os.path.exists(music_path):
        # Mux video + music
        cmd = [
            "ffmpeg", "-y",
            "-i", recording_path,
            "-stream_loop", "-1", "-i", music_path,
            "-filter_complex",
            "[1:a]volume=0.25,aformat=sample_rates=44100:channel_layouts=stereo[bgm];"
            "[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]
    else:
        # Just copy the recording
        cmd = [
            "ffmpeg", "-y",
            "-i", recording_path,
            "-c", "copy",
            "-movflags", "+faststart",
            output_path,
        ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=300, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            return StepResult(
                success=True,
                message=f"Exported {size_mb:.1f} MB video",
                data={
                    "final_video": output_path,
                    "final_size_mb": size_mb,
                },
            )
        else:
            stderr = (result.stderr or "")[-300:]
            return StepResult(success=False, error=f"ffmpeg export failed: {stderr}")
    except Exception as exc:
        return StepResult(success=False, error=f"Export error: {exc}")


def _step_open_justedit(ctx: dict) -> StepResult:
    """Launch JustEdit in the browser with the project loaded."""
    project_path = ctx.get("justedit_project", "")

    try:
        import webbrowser
        url = "http://localhost:5173"
        if project_path:
            url += f"?project={project_path}"
        webbrowser.open(url)
        return StepResult(
            success=True,
            message="JustEdit opened in browser",
            data={"justedit_url": url},
        )
    except Exception as exc:
        return StepResult(success=False, error=f"Failed to open JustEdit: {exc}")


# -- Beat Battle Recap steps --

def _step_load_battle_results(ctx: dict) -> StepResult:
    """Load the latest beat battle results for recap video."""
    try:
        from apps.battle_memory import load_battle_archives
        archives = load_battle_archives()
        if not archives:
            return StepResult(success=False, error="No beat battle archives found")

        # Get most recent battle
        latest = archives[-1]
        battle_id = latest.get("battle_id", "unknown")
        winner = latest.get("winner", "tie")
        score = latest.get("score", "0-0")
        rounds = latest.get("rounds", [])
        opponent = latest.get("opponent", "DJ Phantom")

        # Collect audio paths from rounds
        audio_paths = []
        for r in rounds:
            for path_key in ("onyx_mp3", "onyx_audio", "opponent_mp3", "opponent_audio"):
                p = r.get(path_key, "")
                if p and os.path.exists(p):
                    audio_paths.append(p)

        return StepResult(
            success=True,
            message=f"Battle {battle_id}: {winner} won ({score})",
            data={
                "battle_id": battle_id,
                "battle_winner": winner,
                "battle_score": score,
                "battle_opponent": opponent,
                "battle_rounds": len(rounds),
                "battle_audio_paths": audio_paths,
                "battle_data": latest,
            },
        )
    except Exception as exc:
        return StepResult(success=False, error=f"Failed to load battles: {exc}")


def _step_record_battle_recap(ctx: dict) -> StepResult:
    """Record a screen capture of the battle results display."""
    from core.screen_recorder import ScreenRecorder

    battle_id = ctx.get("battle_id", "unknown")
    rec = ScreenRecorder(fps=20, quality="high", capture_audio=True)
    path = rec.start(f"battle_recap_{battle_id}")

    # Show battle results on screen for ~30 seconds
    # In a real scenario, this would open the battle results webpage
    recap_duration = ctx.get("recap_duration", 30)
    try:
        import webbrowser
        webbrowser.open(f"file:///{_ROOT / 'web' / 'battle' / 'index.html'}")
    except Exception:
        pass
    time.sleep(recap_duration)

    info = rec.stop()
    if info and os.path.exists(info.path):
        return StepResult(
            success=True,
            message=f"Recap recorded ({info.duration:.0f}s)",
            data={
                "recording_path": info.path,
                "recording_duration": info.duration,
            },
        )
    return StepResult(success=False, error="Recap recording failed")


def _step_assemble_battle_video(ctx: dict) -> StepResult:
    """Assemble a beat battle recap video in JustEdit."""
    from apps.modules.justedit import JustEditModule

    recording_path = ctx.get("recording_path", "")
    audio_paths = ctx.get("battle_audio_paths", [])
    battle_winner = ctx.get("battle_winner", "")
    battle_score = ctx.get("battle_score", "")
    opponent = ctx.get("battle_opponent", "DJ Phantom")

    je = JustEditModule()
    name = f"battle_recap_{ctx.get('battle_id', int(time.time()))}"
    je.new_project(name)

    # Video track: the screen recording
    if recording_path and os.path.exists(recording_path):
        vid_res = je.add_resource(recording_path, "video")
        vid_dur = vid_res.get("duration", 60)
        je.add_video_clip(vid_res, start=0, end=vid_dur)
    else:
        vid_dur = 60

    # Audio track: battle music highlights
    cursor = 0
    for ap in audio_paths[:4]:  # max 4 audio highlights
        ares = je.add_resource(ap, "audio")
        clip_dur = min(vid_dur / max(len(audio_paths), 1), 30)
        je.add_audio_clip(ares, start=cursor, end=cursor + clip_dur,
                          volume=0.6, fade_in=0.5, fade_out=1.0)
        cursor += clip_dur

    # Title card
    title = f"DJ Onyx vs {opponent}"
    je.add_text_overlay(title, start=0, end=4, font_size=64)

    # Score overlay
    score_text = f"Result: {battle_winner.upper()} wins! ({battle_score})"
    je.add_text_overlay(score_text, start=vid_dur - 6, end=vid_dur, font_size=48)

    path = je.save_project()
    return StepResult(
        success=True,
        message=f"Battle recap project saved",
        data={"justedit_project": path},
    )


# -- Music Video steps --

def _step_generate_song(ctx: dict) -> StepResult:
    """Generate a full song (lyrics + music) for a music video."""
    genre = ctx.get("music_genre", "hip-hop")
    theme = ctx.get("song_theme", "being an AI that creates")
    duration = ctx.get("song_duration", 60)

    try:
        from apps.evera_client import EveraClient
        client = EveraClient()
        resp = client.generate_track(
            genre=genre,
            mood="energetic",
            theme=theme,
            duration=min(duration, 60),
        )
        track_path = resp.get("local_copy", resp.get("filepath", ""))
        title = resp.get("title", "Untitled")
        if track_path:
            return StepResult(
                success=True,
                message=f"Song '{title}' generated",
                data={
                    "music_path": track_path,
                    "song_title": title,
                    "video_duration": probe_video_duration(track_path) if track_path else duration,
                },
            )
    except Exception as exc:
        return StepResult(success=False, error=f"Song generation failed: {exc}")

    return StepResult(success=False, error="No song generated")


def _step_create_visuals(ctx: dict) -> StepResult:
    """Create visual content for a music video (Blender render or animation)."""
    from core.screen_recorder import ScreenRecorder

    rec = ScreenRecorder(fps=20, quality="high", capture_audio=False)
    path = rec.start("music_video_visuals")

    # Record Blender building something visual, or animation studio
    visual_duration = ctx.get("video_duration", 60)
    visual_type = ctx.get("visual_type", "animation")

    if visual_type == "blender":
        try:
            from addons.blender.house_demo import BlenderHouseDemoController
            controller = BlenderHouseDemoController()
            if controller.start_blender(timeout=60):
                # Run a few phases for visual content
                from addons.blender.house_demo import HOUSE_PHASES
                for phase in HOUSE_PHASES[:4]:  # First 4 phases for visuals
                    script = phase["script_fn"]()
                    controller.execute_phase(script, timeout=30)
                    time.sleep(1.0)
                controller.quit_blender()
        except Exception as exc:
            _log.warning("Blender visuals failed: %s", exc)
            time.sleep(visual_duration)
    else:
        # Fall back to recording the animation studio or desktop
        time.sleep(min(visual_duration, 60))

    info = rec.stop()
    if info and os.path.exists(info.path):
        return StepResult(
            success=True,
            message=f"Visual content recorded ({info.duration:.0f}s)",
            data={"recording_path": info.path, "recording_duration": info.duration},
        )
    return StepResult(success=False, error="Visual recording failed")


def _step_assemble_music_video(ctx: dict) -> StepResult:
    """Assemble a music video from song + visuals in JustEdit."""
    from apps.modules.justedit import JustEditModule

    music_path = ctx.get("music_path", "")
    recording_path = ctx.get("recording_path", "")
    song_title = ctx.get("song_title", "Onyx Track")

    je = JustEditModule()
    project_path = je.create_music_video(
        audio_path=music_path,
        video_clips=[recording_path] if recording_path else None,
        title_text=song_title,
    )

    return StepResult(
        success=True,
        message=f"Music video project assembled",
        data={"justedit_project": project_path},
    )


# -- Demo Highlight Reel steps --

def _step_collect_recordings(ctx: dict) -> StepResult:
    """Collect existing demo recordings for a highlight reel."""
    rec_dir = str(_RECORDINGS_DIR)
    if not os.path.isdir(rec_dir):
        return StepResult(success=False, error="No recordings directory")

    files = sorted(
        [os.path.join(rec_dir, f) for f in os.listdir(rec_dir) if f.endswith(".mp4")],
        key=os.path.getmtime,
        reverse=True,
    )

    limit = ctx.get("max_clips", 10)
    files = files[:limit]

    if not files:
        return StepResult(success=False, error="No recordings found")

    # Get total duration
    total_dur = sum(probe_video_duration(f) for f in files)

    return StepResult(
        success=True,
        message=f"Found {len(files)} recordings ({total_dur:.0f}s total)",
        data={
            "highlight_clips": files,
            "highlight_count": len(files),
            "video_duration": total_dur,
        },
    )


def _step_assemble_highlight_reel(ctx: dict) -> StepResult:
    """Build a highlight reel from collected recordings in JustEdit."""
    from apps.modules.justedit import JustEditModule

    clips = ctx.get("highlight_clips", [])
    music_path = ctx.get("music_path", "")

    if not clips:
        return StepResult(success=False, error="No clips to assemble")

    je = JustEditModule()
    name = f"highlight_reel_{int(time.time())}"
    je.new_project(name)

    # Add clips sequentially with crossfade transitions
    cursor = 0.0
    for i, clip_path in enumerate(clips):
        res = je.add_resource(clip_path, "video")
        dur = res.get("duration") or probe_video_duration(clip_path)
        # Use 10-15 second highlights from each clip
        highlight_dur = min(dur, 15.0)
        clip = je.add_video_clip(res, start=cursor, end=cursor + highlight_dur)
        if i > 0:
            je.set_transition(clip, "dissolve", 0.5, "in")
        cursor += highlight_dur

    # Background music
    if music_path and os.path.exists(music_path):
        bgm_res = je.add_resource(music_path, "audio")
        je.add_audio_clip(bgm_res, start=0, end=cursor,
                          volume=0.3, track_name="BGM",
                          fade_in=1.0, fade_out=2.0)

    # Title + outro
    je.add_text_overlay("OnyxKraken — Highlights", start=0, end=3, font_size=56)
    je.add_text_overlay("More at youtube.com/@OnyxKraken", start=cursor - 4,
                        end=cursor, font_size=40)

    path = je.save_project()
    return StepResult(
        success=True,
        message=f"Highlight reel: {len(clips)} clips, {cursor:.0f}s",
        data={"justedit_project": path, "reel_duration": cursor},
    )


# -- 3D Showcase steps --

def _step_blender_build_and_record(ctx: dict) -> StepResult:
    """Build something in Blender while recording the process."""
    from core.screen_recorder import ScreenRecorder

    build_type = ctx.get("build_type", "house")
    rec = ScreenRecorder(fps=20, quality="high", capture_audio=True)
    path = rec.start(f"blender_{build_type}")

    try:
        if build_type == "building":
            from addons.blender.building_demo import BlenderBuildingDemoController, BUILDING_PHASES
            controller = BlenderBuildingDemoController()
            phases = BUILDING_PHASES
        else:
            from addons.blender.house_demo import BlenderHouseDemoController, HOUSE_PHASES
            controller = BlenderHouseDemoController()
            phases = HOUSE_PHASES

        if not controller.start_blender(timeout=60):
            rec.stop()
            return StepResult(success=False, error="Failed to start Blender")

        for phase in phases:
            script = phase["script_fn"]()
            controller.execute_phase(script, timeout=30)
            time.sleep(phase.get("wait", 1.0))

        controller.quit_blender()
    except Exception as exc:
        _log.error("Blender build failed: %s", exc)
        try:
            rec.stop()
        except Exception:
            pass
        return StepResult(success=False, error=f"Blender build error: {exc}")

    info = rec.stop()
    if info and os.path.exists(info.path):
        return StepResult(
            success=True,
            message=f"3D build recorded ({info.duration:.0f}s)",
            data={
                "recording_path": info.path,
                "recording_duration": info.duration,
            },
        )
    return StepResult(success=False, error="Build recording failed")


# ---------------------------------------------------------------------------
# Workflow definitions
# ---------------------------------------------------------------------------

def _wf_full_production() -> ChainWorkflow:
    """The ultimate demo: Record → Probe → Music → Assemble → Export."""
    return ChainWorkflow(
        id="full_production",
        title="Full Production Pipeline",
        description=(
            "Onyx records itself performing tasks, checks the video length, "
            "generates matching background music, assembles everything in "
            "JustEdit, and exports the final MP4."
        ),
        estimated_minutes=10,
        tags=["production", "recording", "music", "video", "showcase"],
        intro_narration=(
            "Alright, full production mode. I'm about to record myself "
            "doing some tasks, then generate a custom soundtrack to match "
            "the video length, and assemble the whole thing in JustEdit. "
            "This is the full pipeline. Let's go."
        ),
        success_narration=(
            "And that's a wrap. Recorded, scored, edited, and exported — "
            "all autonomously. That's the OnyxKraken production pipeline."
        ),
        failure_narration=(
            "Hit a wall in the pipeline. Let me check what went wrong and "
            "we can try again."
        ),
        steps=[
            ChainStep(
                id="record",
                name="Record Demo",
                description="Screen-record Onyx performing desktop tasks",
                execute=_step_record_demo,
                narration_before=(
                    "Starting the screen recorder. I'm going to open some apps, "
                    "do a few things, and close them. Watch this."
                ),
                narration_after="Recording done. {result}",
                narration_error="Recording had issues, but let me see what I got.",
                estimated_seconds=60,
            ),
            ChainStep(
                id="probe",
                name="Check Video Duration",
                description="Analyze recording duration with ffprobe",
                execute=_step_probe_duration,
                narration_before="Let me check how long that recording is.",
                narration_after="{result}. Now I know exactly how much music to generate.",
                estimated_seconds=5,
            ),
            ChainStep(
                id="music",
                name="Generate Music",
                description="Create background music matching the video length",
                execute=_step_generate_music,
                narration_before=(
                    "Time to make some music. Generating a custom track to "
                    "fit this video perfectly."
                ),
                narration_after="Music is ready. {result}",
                narration_error="Music generation hit a snag. I'll use the video as-is.",
                estimated_seconds=120,
                optional=True,  # Video still works without music
                preflight_services=["Ollama", "ACE-Step"],
            ),
            ChainStep(
                id="assemble",
                name="Assemble in JustEdit",
                description="Combine video + music into a JustEdit project",
                execute=_step_assemble_justedit,
                narration_before=(
                    "Bringing the video and music together in JustEdit. "
                    "Adding title cards and transitions."
                ),
                narration_after="Project assembled. {result}",
                estimated_seconds=10,
                preflight_services=["JustEdit"],
            ),
            ChainStep(
                id="export",
                name="Export Final MP4",
                description="Render the final video with ffmpeg",
                execute=_step_export_video,
                narration_before="Exporting the final video now.",
                narration_after="Done! {result}",
                estimated_seconds=30,
                preflight_services=["ffmpeg"],
            ),
        ],
    )


def _wf_beat_battle_recap() -> ChainWorkflow:
    """Beat battle recap: Load results → Record recap → Assemble."""
    return ChainWorkflow(
        id="beat_battle_recap",
        title="Beat Battle Recap Video",
        description=(
            "Load the latest beat battle results, record a recap screen, "
            "and assemble a highlight video with round audio."
        ),
        estimated_minutes=5,
        tags=["music", "battle", "recap", "video"],
        intro_narration=(
            "Let me put together a recap of the latest beat battle. "
            "I'll pull the results, grab the audio highlights, and "
            "cut it all into a video."
        ),
        success_narration=(
            "Battle recap is done. DJ Onyx stays documented."
        ),
        failure_narration="Couldn't finish the recap. I'll debug this.",
        steps=[
            ChainStep(
                id="load_battle",
                name="Load Battle Results",
                description="Read the latest beat battle archive",
                execute=_step_load_battle_results,
                narration_before="Pulling up the battle results.",
                narration_after="{result}",
                estimated_seconds=5,
            ),
            ChainStep(
                id="record_recap",
                name="Record Recap Screen",
                description="Screen-capture the battle results display",
                execute=_step_record_battle_recap,
                narration_before="Recording the battle recap display.",
                narration_after="Recap footage captured.",
                estimated_seconds=35,
            ),
            ChainStep(
                id="assemble",
                name="Assemble Recap Video",
                description="Build the recap video with round highlights",
                execute=_step_assemble_battle_video,
                narration_before="Assembling the battle recap with round highlights.",
                narration_after="Battle recap project ready.",
                estimated_seconds=10,
                preflight_services=["JustEdit"],
            ),
            ChainStep(
                id="export",
                name="Export Video",
                description="Render the final recap video",
                execute=_step_export_video,
                narration_before="Rendering the final battle recap.",
                narration_after="Battle recap exported. {result}",
                estimated_seconds=30,
                preflight_services=["ffmpeg"],
            ),
        ],
    )


def _wf_music_video() -> ChainWorkflow:
    """Music video: Generate song → Create visuals → Assemble → Export."""
    return ChainWorkflow(
        id="music_video",
        title="AI Music Video Pipeline",
        description=(
            "Generate a song with EVERA, create visual content (Blender or "
            "animation), and assemble everything into a music video."
        ),
        estimated_minutes=15,
        tags=["music", "video", "creative", "3d", "showcase"],
        intro_narration=(
            "Full music video production incoming. I'm going to write and "
            "produce a track, create some visuals, and cut a music video. "
            "All from scratch. All autonomous."
        ),
        success_narration=(
            "Music video is done. Song, visuals, editing — the whole thing. "
            "That's an AI creating content from concept to export."
        ),
        failure_narration="The music video pipeline hit a problem. Let me review.",
        steps=[
            ChainStep(
                id="song",
                name="Generate Song",
                description="Create an original song with EVERA",
                execute=_step_generate_song,
                narration_before="Producing the track first. Let me cook.",
                narration_after="Track is done. {result}",
                estimated_seconds=120,
                preflight_services=["Ollama", "ACE-Step"],
            ),
            ChainStep(
                id="visuals",
                name="Create Visuals",
                description="Generate visual content for the video",
                execute=_step_create_visuals,
                narration_before="Now for the visuals. Creating content to match the music.",
                narration_after="Visuals captured. {result}",
                estimated_seconds=120,
            ),
            ChainStep(
                id="assemble",
                name="Assemble Music Video",
                description="Combine song + visuals in JustEdit",
                execute=_step_assemble_music_video,
                narration_before="Putting it all together in JustEdit.",
                narration_after="Music video project assembled.",
                estimated_seconds=15,
                preflight_services=["JustEdit"],
            ),
            ChainStep(
                id="export",
                name="Export Video",
                description="Render the final music video",
                execute=_step_export_video,
                narration_before="Final render. Almost there.",
                narration_after="Music video exported. {result}",
                estimated_seconds=30,
                preflight_services=["ffmpeg"],
            ),
        ],
    )


def _wf_highlight_reel() -> ChainWorkflow:
    """Demo highlight reel: Collect recordings → Music → Assemble."""
    return ChainWorkflow(
        id="highlight_reel",
        title="Demo Highlight Reel",
        description=(
            "Collect existing demo recordings, generate matching music, "
            "and compile a highlight reel with transitions and titles."
        ),
        estimated_minutes=8,
        tags=["demo", "highlights", "video", "music", "compilation"],
        intro_narration=(
            "Time to make a highlight reel. I'll grab my best recordings, "
            "lay down a fresh track, and cut it all together."
        ),
        success_narration=(
            "Highlight reel is ready. Every major capability, one video. "
            "That's the OnyxKraken showreel."
        ),
        failure_narration="Highlight reel had issues. Let me check what happened.",
        steps=[
            ChainStep(
                id="collect",
                name="Collect Recordings",
                description="Find and analyze existing demo recordings",
                execute=_step_collect_recordings,
                narration_before="Scanning my recordings library.",
                narration_after="{result}",
                estimated_seconds=10,
            ),
            ChainStep(
                id="music",
                name="Generate Music",
                description="Create background music for the reel",
                execute=_step_generate_music,
                narration_before="Making a soundtrack for the reel.",
                narration_after="Soundtrack ready. {result}",
                narration_error="No music this time. The footage speaks for itself.",
                estimated_seconds=120,
                optional=True,
                preflight_services=["Ollama", "ACE-Step"],
            ),
            ChainStep(
                id="assemble",
                name="Assemble Reel",
                description="Build the highlight reel in JustEdit",
                execute=_step_assemble_highlight_reel,
                narration_before="Editing the highlight reel. Transitions, titles, the works.",
                narration_after="Reel assembled. {result}",
                estimated_seconds=15,
                preflight_services=["JustEdit"],
            ),
            ChainStep(
                id="export",
                name="Export Video",
                description="Render the final highlight reel",
                execute=_step_export_video,
                narration_before="Rendering the showreel.",
                narration_after="Showreel exported. {result}",
                estimated_seconds=30,
                preflight_services=["ffmpeg"],
            ),
        ],
    )


def _wf_3d_showcase() -> ChainWorkflow:
    """3D showcase: Build in Blender → Music → Assemble → Export."""
    return ChainWorkflow(
        id="3d_showcase",
        title="3D Build Showcase",
        description=(
            "Build a 3D scene in Blender (recorded), generate a matching "
            "soundtrack, and produce a polished showcase video."
        ),
        estimated_minutes=15,
        tags=["blender", "3d", "music", "video", "showcase"],
        intro_narration=(
            "3D showcase production starting. I'll build something in Blender, "
            "record the entire process, add music, and deliver a polished video."
        ),
        success_narration=(
            "3D showcase complete. From empty viewport to finished video. "
            "Everything you just saw was built and produced by an AI."
        ),
        failure_narration="3D showcase pipeline had an issue. Let me investigate.",
        steps=[
            ChainStep(
                id="build",
                name="Build & Record in Blender",
                description="Build a 3D scene while screen recording",
                execute=_step_blender_build_and_record,
                narration_before=(
                    "Opening Blender. I'm going to build something and "
                    "record the whole process."
                ),
                narration_after="Build complete. {result}",
                estimated_seconds=300,
                preflight_services=["Blender"],
            ),
            ChainStep(
                id="probe",
                name="Check Duration",
                description="Analyze the build recording duration",
                execute=_step_probe_duration,
                narration_before="Checking the footage length.",
                narration_after="{result}",
                estimated_seconds=5,
            ),
            ChainStep(
                id="music",
                name="Generate Soundtrack",
                description="Create ambient music for the showcase",
                execute=_step_generate_music,
                narration_before="Generating a soundtrack to match the build timelapse.",
                narration_after="Soundtrack ready. {result}",
                optional=True,
                estimated_seconds=120,
                preflight_services=["Ollama", "ACE-Step"],
            ),
            ChainStep(
                id="assemble",
                name="Assemble Showcase",
                description="Combine build recording + music in JustEdit",
                execute=_step_assemble_justedit,
                narration_before="Assembling the 3D showcase video.",
                narration_after="Showcase assembled.",
                estimated_seconds=15,
                preflight_services=["JustEdit"],
            ),
            ChainStep(
                id="export",
                name="Export Video",
                description="Render the final showcase video",
                execute=_step_export_video,
                narration_before="Final render of the 3D showcase.",
                narration_after="3D showcase exported. {result}",
                estimated_seconds=30,
                preflight_services=["ffmpeg"],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

CHAIN_WORKFLOWS: dict[str, Callable[[], ChainWorkflow]] = {
    "full_production": _wf_full_production,
    "beat_battle_recap": _wf_beat_battle_recap,
    "music_video": _wf_music_video,
    "highlight_reel": _wf_highlight_reel,
    "3d_showcase": _wf_3d_showcase,
}


def list_workflows() -> list[dict]:
    """Return metadata for all registered chain workflows."""
    result = []
    for wf_id, factory in CHAIN_WORKFLOWS.items():
        wf = factory()
        result.append({
            "id": wf.id,
            "title": wf.title,
            "description": wf.description,
            "steps": len(wf.steps),
            "step_names": [s.name for s in wf.steps],
            "estimated_minutes": wf.estimated_minutes,
            "tags": wf.tags,
        })
    return result


def get_workflow(workflow_id: str) -> Optional[ChainWorkflow]:
    """Get a workflow by ID."""
    factory = CHAIN_WORKFLOWS.get(workflow_id)
    return factory() if factory else None


def run_workflow(
    workflow_id: str,
    context: dict | None = None,
    narrate_fn: Optional[NarrateFn] = None,
    on_progress: Optional[ProgressFn] = None,
) -> WorkflowResult:
    """Run a named workflow. Returns WorkflowResult."""
    wf = get_workflow(workflow_id)
    if not wf:
        return WorkflowResult(
            workflow_id=workflow_id,
            success=False,
            steps_completed=0,
            steps_total=0,
            error=f"Unknown workflow: {workflow_id}",
        )
    engine = WorkflowEngine(narrate_fn=narrate_fn, on_progress=on_progress)
    return engine.run(wf, context)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(description="OnyxKraken Chain Workflow Engine")
    parser.add_argument("workflow", nargs="?", help="Workflow ID to run")
    parser.add_argument("--list", action="store_true", help="List available workflows")
    parser.add_argument("--genre", default="lo-fi", help="Music genre (default: lo-fi)")
    parser.add_argument("--build-type", default="house", help="Blender build type")
    parser.add_argument("--dry-run", action="store_true", help="Print steps without executing")
    args = parser.parse_args()

    if args.list or not args.workflow:
        print("\n=== OnyxKraken Chain Workflows ===\n")
        for wf in list_workflows():
            steps = " → ".join(wf["step_names"])
            print(f"  {wf['id']}")
            print(f"    {wf['title']} (~{wf['estimated_minutes']} min)")
            print(f"    {wf['description'][:80]}")
            print(f"    Steps: {steps}")
            print()
    elif args.dry_run:
        wf = get_workflow(args.workflow)
        if wf:
            print(f"\n=== Dry Run: {wf.title} ===\n")
            print(f"Intro: {wf.intro_narration}\n")
            for i, step in enumerate(wf.steps):
                opt = " (optional)" if step.optional else ""
                print(f"  Step {i+1}: {step.name}{opt}")
                print(f"    {step.description}")
                if step.narration_before:
                    print(f"    Says: \"{step.narration_before[:60]}...\"")
                print()
            print(f"Success: {wf.success_narration}")
        else:
            print(f"Unknown workflow: {args.workflow}")
    else:
        def _narrate(text):
            print(f"\n🎤 Onyx: {text}\n")

        def _progress(cur, total, name):
            print(f"  [{cur}/{total}] {name}")

        ctx = {"music_genre": args.genre, "build_type": args.build_type}
        result = run_workflow(args.workflow, context=ctx,
                              narrate_fn=_narrate, on_progress=_progress)

        print(f"\n{'✅' if result.success else '❌'} {result.workflow_id}: "
              f"{result.steps_completed}/{result.steps_total} steps "
              f"({result.duration:.1f}s)")
        if result.outputs:
            for k, v in result.outputs.items():
                if isinstance(v, str) and (v.endswith(".mp4") or v.endswith(".json")):
                    print(f"  📁 {k}: {v}")
        if result.error:
            print(f"  Error: {result.error}")
