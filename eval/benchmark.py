"""Benchmark runner — execute tasks and measure OnyxKraken performance."""

import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from log import setup_logging
setup_logging(config.LOG_LEVEL)

from apps.registry import discover_modules, list_modules
from agent.orchestrator import run, TaskResult
try:
    from desktop.controller import list_windows
except (ImportError, RuntimeError):
    def list_windows(): return []
from eval.verifiers import build_verifiers
from eval.metrics import TaskMetrics, BenchmarkReport


TASKS_FILE = os.path.join(os.path.dirname(__file__), "tasks.json")
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "eval_reports")


def load_tasks(filter_tags: Optional[list[str]] = None,
               filter_ids: Optional[list[str]] = None) -> list[dict]:
    """Load task definitions, optionally filtered by tags or IDs."""
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    if filter_ids:
        tasks = [t for t in tasks if t["id"] in filter_ids]
    if filter_tags:
        tasks = [t for t in tasks if any(tag in t.get("tags", []) for tag in filter_tags)]

    return tasks


def _cleanup_windows(app_hint: str):
    """Close ALL known app windows before each task to prevent cross-task interference."""
    import subprocess
    # Kill known standalone processes (safe — these are test apps only)
    _KILL_PROCESSES = [
        "notepad.exe",
        "calc.exe",
        "CalculatorApp.exe",
    ]
    for proc in _KILL_PROCESSES:
        try:
            subprocess.run(
                ["taskkill", "/f", "/im", proc],
                capture_output=True, timeout=5,
            )
        except Exception:
            pass  # process kill is best-effort cleanup

    # Close app windows by title pattern (don't kill chrome.exe — user may be browsing)
    # Add new app patterns here as needed
    _CLOSE_TITLE_PATTERNS = ["grok", "blender"]
    try:
        from pywinauto import Desktop
        for win in Desktop(backend="uia").windows():
            try:
                title = win.window_text().lower()
                if any(pat in title for pat in _CLOSE_TITLE_PATTERNS):
                    win.close()
            except Exception:
                pass  # window close is best-effort
    except Exception:
        pass  # pywinauto enumeration may fail

    # Windows 11 Notepad restores previous tabs on reopen.
    # Kill first, wait for shutdown to finish writing state, then nuke the state dir.
    time.sleep(1.0)
    tab_state_dir = os.path.expandvars(
        r"%LOCALAPPDATA%\Packages\Microsoft.WindowsNotepad_8wekyb3d8bbwe\LocalState\TabState"
    )
    if os.path.isdir(tab_state_dir):
        for f in os.listdir(tab_state_dir):
            fpath = os.path.join(tab_state_dir, f)
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
            except Exception:
                pass  # stale Notepad state cleanup is best-effort
    time.sleep(0.5)


def run_task(task: dict, auto_mode: bool = True) -> TaskMetrics:
    """Run a single benchmark task and collect metrics."""
    task_id = task["id"]
    goal = task["goal"]
    app_name = task.get("app_name", "unknown")

    # Pre-task cleanup for test isolation
    _cleanup_windows(app_name)

    print(f"\n{'#'*60}")
    print(f"  BENCHMARK TASK: {task_id}")
    print(f"  Goal: {goal}")
    print(f"{'#'*60}\n")

    # Override autonomy mode for benchmarking
    original_mode = config.AUTONOMY_MODE
    if auto_mode:
        config.AUTONOMY_MODE = "auto"

    metrics = TaskMetrics(
        task_id=task_id,
        goal=goal,
        app_name=app_name,
    )

    try:
        result = run(goal=goal, app_name=app_name)

        metrics.steps_planned = result.steps_planned
        metrics.steps_completed = result.steps_completed
        metrics.total_actions = result.total_actions
        metrics.total_time = result.total_time
        metrics.aborted = result.aborted
        metrics.failure_reason = result.failure_reason

        # Run verifiers
        verifiers = build_verifiers(task.get("verifiers", []))
        for verifier in verifiers:
            try:
                passed, detail = verifier(result)
            except Exception as e:
                passed, detail = False, f"Verifier error: {e}"
            metrics.verifier_results.append({
                "name": verifier.__name__,
                "passed": passed,
                "detail": detail,
            })

    except Exception as e:
        metrics.aborted = True
        metrics.failure_reason = f"Exception: {e}"
        metrics.verifier_results.append({
            "name": "execution",
            "passed": False,
            "detail": f"Task crashed: {e}",
        })

    finally:
        config.AUTONOMY_MODE = original_mode

    # Print task result
    status = "PASS" if metrics.passed else "FAIL"
    print(f"\n  [{status}] {task_id}: {metrics.verifiers_passed}/{metrics.verifiers_total} verifiers passed")
    for v in metrics.verifier_results:
        icon = "✓" if v["passed"] else "✗"
        print(f"    {icon} {v['name']}: {v['detail']}")

    return metrics


def run_benchmark(filter_tags: Optional[list[str]] = None,
                  filter_ids: Optional[list[str]] = None,
                  auto_mode: bool = True) -> BenchmarkReport:
    """Run the full benchmark suite and generate a report."""
    discover_modules()

    tasks = load_tasks(filter_tags=filter_tags, filter_ids=filter_ids)
    if not tasks:
        print("No tasks matched the filter criteria.")
        return BenchmarkReport()

    print(f"\n{'='*60}")
    print(f"  ONYX BENCHMARK — {len(tasks)} tasks queued")
    print(f"  Models: vision={config.VISION_MODEL}, planner={config.PLANNER_MODEL}")
    print(f"  Auto mode: {auto_mode}")
    print(f"{'='*60}\n")

    report = BenchmarkReport(
        timestamp=datetime.now().isoformat(),
        tasks_total=len(tasks),
        config_snapshot={
            "models": config.MODELS,
            "autonomy_mode": config.AUTONOMY_MODE,
            "max_agent_steps": config.MAX_AGENT_STEPS,
        },
    )

    bench_start = time.time()

    for task in tasks:
        metrics = run_task(task, auto_mode=auto_mode)
        result_dict = asdict(metrics)
        result_dict["passed"] = metrics.passed
        report.task_results.append(result_dict)

        if metrics.passed:
            report.tasks_passed += 1
        else:
            report.tasks_failed += 1
        report.total_actions += metrics.total_actions

    report.total_time = time.time() - bench_start

    # Print summary
    print(report.summary())

    # Save report
    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(REPORTS_DIR, f"bench_{ts}.json")
    report.save(report_path)
    print(f"\n  Report saved: {report_path}")

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="OnyxKraken Benchmark Runner")
    parser.add_argument("--tags", nargs="*", help="Filter tasks by tags (e.g., --tags basic launch)")
    parser.add_argument("--ids", nargs="*", help="Filter tasks by IDs (e.g., --ids notepad_open)")
    parser.add_argument("--no-auto", action="store_true", help="Don't override autonomy mode to auto")
    args = parser.parse_args()

    run_benchmark(
        filter_tags=args.tags,
        filter_ids=args.ids,
        auto_mode=not args.no_auto,
    )


if __name__ == "__main__":
    main()
