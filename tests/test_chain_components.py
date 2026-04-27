"""Component-level tests for chain workflow steps.

Run with:  python -m pytest tests/test_chain_components.py -v --tb=short
Or individually:  python tests/test_chain_components.py

Tests are organized in three tiers:
  1. UNIT — Each component in isolation (imports, constructors, basic logic)
  2. INTEGRATION — Pairwise step combinations (Record→Probe, Probe→Music, etc.)
  3. E2E — Full chain workflows end-to-end

Each test prints a clear PASS/FAIL so you can see status without pytest.
"""

import os
import sys
import time
import tempfile
import subprocess
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_results: list[tuple[str, bool, str]] = []


def _record(name: str, passed: bool, detail: str = ""):
    status = "\033[92mPASS\033[0m" if passed else "\033[91mFAIL\033[0m"
    _results.append((name, passed, detail))
    print(f"  [{status}] {name}" + (f"  — {detail}" if detail else ""))


def _section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ===================================================================
# TIER 1: UNIT TESTS — individual components
# ===================================================================

def test_imports():
    """Verify all chain workflow modules can be imported."""
    _section("TIER 1: Import checks")

    modules = [
        ("core.chain_workflow", "Chain workflow engine"),
        ("core.screen_recorder", "Screen recorder"),
        ("core.system_health", "System health"),
        ("core.service_launcher", "Service launcher"),
        ("core.nodes.registry", "Node registry"),
        ("core.nodes.base_node", "Base node"),
        ("core.nodes.types", "Node types"),
        ("face.node_canvas", "Node canvas UI"),
        ("face.workflow_hud", "Workflow HUD"),
        ("face.extensions_controller", "Extensions controller"),
        ("face.backend", "Backend bridge"),
    ]

    for mod_path, label in modules:
        try:
            __import__(mod_path)
            _record(f"Import {label}", True)
        except Exception as e:
            _record(f"Import {label}", False, str(e)[:80])


def test_chain_workflow_registry():
    """Verify all chain workflows are registered and buildable."""
    _section("TIER 1: Chain workflow definitions")

    try:
        from core.chain_workflow import CHAIN_WORKFLOWS, list_workflows
        workflows = list_workflows()
        _record("list_workflows()", True, f"{len(workflows)} workflows")

        for wf_info in workflows:
            wf_id = wf_info["id"]
            builder = CHAIN_WORKFLOWS.get(wf_id)
            if builder:
                try:
                    wf = builder()
                    step_count = len(wf.steps)
                    _record(f"Build '{wf_id}'", True, f"{step_count} steps")
                except Exception as e:
                    _record(f"Build '{wf_id}'", False, str(e)[:80])
            else:
                _record(f"Build '{wf_id}'", False, "Not in CHAIN_WORKFLOWS")
    except Exception as e:
        _record("Chain workflow registry", False, str(e)[:80])


def test_node_registry():
    """Verify node registry discovers all nodes including chain nodes."""
    _section("TIER 1: Node registry")

    try:
        from core.nodes.registry import get_registry
        reg = get_registry()
        count = reg.discover()
        _record("Node discovery", True, f"{count} nodes discovered")

        # Check chain nodes specifically
        chain_ids = [nid for nid in reg.node_ids if nid.startswith("chain.")]
        _record("Chain nodes registered", len(chain_ids) > 0,
                f"{len(chain_ids)} chain nodes: {chain_ids[:5]}")

        # Check we can get schema for each
        for nid in chain_ids:
            cls = reg.get(nid)
            if cls:
                schema = cls.schema_dict()
                inputs = len(schema.get("inputs", []))
                outputs = len(schema.get("outputs", []))
                _record(f"  Schema '{nid}'", True,
                        f"{inputs} inputs, {outputs} outputs")
            else:
                _record(f"  Schema '{nid}'", False, "Not found")
    except Exception as e:
        _record("Node registry", False, str(e)[:80])


def test_preset_workflows():
    """Verify preset workflow JSONs are valid and loadable."""
    _section("TIER 1: Preset workflow files")

    import json
    presets_dir = ROOT / "core" / "nodes" / "presets"
    if not presets_dir.is_dir():
        _record("Presets directory", False, f"Not found: {presets_dir}")
        return

    for p in sorted(presets_dir.glob("*.json")):
        try:
            with open(p) as f:
                data = json.load(f)
            meta = data.get("meta", {})
            nodes = data.get("nodes", {})
            name = meta.get("name", p.stem)

            # Check all class_types reference valid node IDs
            from core.nodes.registry import get_registry
            reg = get_registry()
            if reg.count == 0:
                reg.discover()

            missing = []
            for nid, ndef in nodes.items():
                ct = ndef.get("class_type", "")
                if not reg.get(ct):
                    missing.append(ct)

            if missing:
                _record(f"Preset '{name}'", False, f"Unknown nodes: {missing}")
            else:
                _record(f"Preset '{name}'", True,
                        f"{len(nodes)} nodes, category={meta.get('category','?')}")
        except Exception as e:
            _record(f"Preset '{p.name}'", False, str(e)[:80])


def test_ffmpeg_available():
    """Check if ffmpeg and ffprobe are on PATH."""
    _section("TIER 1: External tools")

    for tool in ["ffmpeg", "ffprobe"]:
        try:
            r = subprocess.run(
                [tool, "-version"], capture_output=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            version_line = r.stdout.decode().split("\n")[0][:60] if r.stdout else "?"
            _record(f"{tool} available", r.returncode == 0, version_line)
        except FileNotFoundError:
            _record(f"{tool} available", False, "Not found on PATH")
        except Exception as e:
            _record(f"{tool} available", False, str(e)[:60])


def test_screen_recorder_init():
    """Verify ScreenRecorder can be constructed."""
    _section("TIER 1: Screen recorder")

    try:
        from core.screen_recorder import ScreenRecorder
        rec = ScreenRecorder(fps=10, quality="low")
        _record("ScreenRecorder()", True, f"fps={rec.fps}, quality={rec.quality}")
    except Exception as e:
        _record("ScreenRecorder()", False, str(e)[:80])


def test_dj_preferences():
    """Verify DJPreferences can be constructed with valid args."""
    _section("TIER 1: DJ Mode")

    try:
        from apps.dj_mode import DJPreferences
        prefs = DJPreferences(
            genre="lo-fi",
            quality="standard",
            num_tracks=1,
            duration=60,
        )
        _record("DJPreferences()", True,
                f"genre={prefs.genre}, quality={prefs.quality}, "
                f"tracks={prefs.num_tracks}, dur={prefs.duration}s, bpm={prefs.bpm}")
    except Exception as e:
        _record("DJPreferences()", False, str(e)[:80])


def test_probe_duration_function():
    """Test probe_video_duration with a non-existent file (fallback path)."""
    _section("TIER 1: Probe duration")

    try:
        from core.chain_workflow import probe_video_duration
        # Non-existent file should return fallback 60.0
        dur = probe_video_duration("/nonexistent/video.mp4")
        _record("probe_video_duration(missing)", True, f"fallback={dur}s")
    except Exception as e:
        _record("probe_video_duration(missing)", False, str(e)[:80])


def test_step_result_dataclass():
    """Verify StepResult and WorkflowResult dataclasses."""
    _section("TIER 1: Data classes")

    try:
        from core.chain_workflow import StepResult, WorkflowResult
        sr = StepResult(success=True, message="test", data={"key": "val"})
        _record("StepResult", True, f"success={sr.success}, data={sr.data}")

        wr = WorkflowResult(
            workflow_id="test", success=True,
            steps_completed=5, steps_total=5, duration=10.0, outputs={},
        )
        _record("WorkflowResult", True,
                f"id={wr.workflow_id}, {wr.steps_completed}/{wr.steps_total}")
    except Exception as e:
        _record("Data classes", False, str(e)[:80])


def test_justedit_module_import():
    """Check JustEditModule can be imported."""
    _section("TIER 1: JustEdit module")

    try:
        from apps.modules.justedit import JustEditModule
        je = JustEditModule()
        _record("JustEditModule()", True)
    except Exception as e:
        _record("JustEditModule()", False, str(e)[:80])


# ===================================================================
# TIER 2: INTEGRATION — pairwise step combinations
# ===================================================================

def test_probe_with_real_file():
    """Test probe_video_duration against a real file if any exist."""
    _section("TIER 2: Probe with real recording")

    rec_dir = ROOT / "data" / "recordings"
    if not rec_dir.is_dir():
        _record("Find recording", False, f"No recordings dir: {rec_dir}")
        return

    mp4s = sorted(rec_dir.glob("*.mp4"))
    if not mp4s:
        _record("Find recording", False, "No .mp4 files in data/recordings/")
        return

    latest = mp4s[-1]
    _record("Find recording", True, f"{latest.name} ({latest.stat().st_size / 1024:.0f} KB)")

    try:
        from core.chain_workflow import probe_video_duration
        dur = probe_video_duration(str(latest))
        _record("probe_video_duration(real)", dur > 0, f"duration={dur:.1f}s")
    except Exception as e:
        _record("probe_video_duration(real)", False, str(e)[:80])


def test_step_probe_integration():
    """Test _step_probe_duration with a real recording file."""
    _section("TIER 2: Step probe integration")

    rec_dir = ROOT / "data" / "recordings"
    mp4s = sorted(rec_dir.glob("*.mp4")) if rec_dir.is_dir() else []
    if not mp4s:
        _record("_step_probe_duration", False, "No recordings available")
        return

    try:
        from core.chain_workflow import _step_probe_duration
        ctx = {"recording_path": str(mp4s[-1])}
        result = _step_probe_duration(ctx)
        _record("_step_probe_duration", result.success,
                f"duration={result.data.get('video_duration', '?')}s")
    except Exception as e:
        _record("_step_probe_duration", False, str(e)[:80])


def test_step_collect_recordings():
    """Test _step_collect_recordings."""
    _section("TIER 2: Collect recordings")

    try:
        from core.chain_workflow import _step_collect_recordings
        ctx = {"recordings_dir": str(ROOT / "data" / "recordings")}
        result = _step_collect_recordings(ctx)
        count = result.data.get("recording_count", 0) if result.data else 0
        _record("_step_collect_recordings", result.success,
                f"{count} recordings found")
    except Exception as e:
        _record("_step_collect_recordings", False, str(e)[:80])


def test_step_export_copy_only():
    """Test _step_export_video in copy-only mode (no music, just copies video)."""
    _section("TIER 2: Export (copy-only mode)")

    rec_dir = ROOT / "data" / "recordings"
    mp4s = sorted(rec_dir.glob("*.mp4")) if rec_dir.is_dir() else []
    if not mp4s:
        _record("_step_export_video (copy)", False, "No recordings available")
        return

    try:
        from core.chain_workflow import _step_export_video
        ctx = {
            "recording_path": str(mp4s[-1]),
            "music_path": "",  # no music — triggers copy-only path
            "video_duration": 10,
        }
        result = _step_export_video(ctx)
        if result.success:
            final = result.data.get("final_video", "")
            size = result.data.get("final_size_mb", 0)
            _record("_step_export_video (copy)", True, f"{size:.1f} MB → {Path(final).name}")
            # Cleanup test output
            if os.path.exists(final):
                os.remove(final)
        else:
            _record("_step_export_video (copy)", False, result.error[:80])
    except Exception as e:
        _record("_step_export_video (copy)", False, str(e)[:80])


# ===================================================================
# TIER 3: E2E — full chain workflow simulation
# ===================================================================

def test_workflow_engine_dry_run():
    """Test WorkflowEngine with a minimal dummy workflow."""
    _section("TIER 3: Workflow engine dry run")

    try:
        from core.chain_workflow import WorkflowEngine, ChainWorkflow, ChainStep, StepResult

        steps_run = []

        def dummy_step(ctx):
            steps_run.append("dummy")
            ctx["dummy_output"] = "hello"
            return StepResult(success=True, message="ok", data={"dummy_output": "hello"})

        wf = ChainWorkflow(
            id="test_dry",
            title="Test Dry Run",
            description="Minimal test workflow",
            estimated_minutes=0,
            steps=[
                ChainStep(id="s1", name="Step One", description="test",
                          execute=dummy_step, estimated_seconds=1),
                ChainStep(id="s2", name="Step Two", description="test",
                          execute=dummy_step, estimated_seconds=1),
            ],
        )

        narrations = []
        engine = WorkflowEngine(
            narrate_fn=lambda t: narrations.append(t),
            on_progress=lambda c, t, n: None,
        )
        result = engine.run(wf)
        _record("Engine dry run", result.success,
                f"{result.steps_completed}/{result.steps_total} steps, "
                f"{len(narrations)} narrations, {len(steps_run)} steps executed")
    except Exception as e:
        _record("Engine dry run", False, str(e)[:80])


# ===================================================================
# Main
# ===================================================================

def run_all():
    """Run all tests and print summary."""
    print("\n" + "=" * 60)
    print("  ONYX CHAIN WORKFLOW — COMPONENT TEST SUITE")
    print("=" * 60)

    # Tier 1
    test_imports()
    test_chain_workflow_registry()
    test_node_registry()
    test_preset_workflows()
    test_ffmpeg_available()
    test_screen_recorder_init()
    test_dj_preferences()
    test_probe_duration_function()
    test_step_result_dataclass()
    test_justedit_module_import()

    # Tier 2
    test_probe_with_real_file()
    test_step_probe_integration()
    test_step_collect_recordings()
    test_step_export_copy_only()

    # Tier 3
    test_workflow_engine_dry_run()

    # Summary
    _section("SUMMARY")
    passed = sum(1 for _, p, _ in _results if p)
    failed = sum(1 for _, p, _ in _results if not p)
    total = len(_results)
    print(f"\n  Total: {total}  |  \033[92mPassed: {passed}\033[0m  |  \033[91mFailed: {failed}\033[0m\n")

    if failed:
        print("  Failed tests:")
        for name, p, detail in _results:
            if not p:
                print(f"    \033[91m✗\033[0m {name}: {detail}")
        print()

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
