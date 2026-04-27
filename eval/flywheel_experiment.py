"""Flywheel Experiment — measure whether OnyxKraken actually improves over time.

Runs a configurable subset of benchmark tasks, records time-series metrics to
``data/flywheel_metrics.json``, and can generate a trend report.

Modes:
    normal   — full agent with knowledge, self-improvement, and memory active
    baseline — knowledge retrieval and self-improvement advice are disabled
               so we can compare "with flywheel" vs "without"

Usage:
    python -m eval.flywheel_experiment                # run once (normal)
    python -m eval.flywheel_experiment --baseline      # run once (baseline)
    python -m eval.flywheel_experiment --report         # print trend report
    python -m eval.flywheel_experiment --schedule 6     # run every 6 hours
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from log import setup_logging, get_logger

setup_logging(config.LOG_LEVEL)
_log = get_logger("eval.flywheel")

METRICS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "flywheel_metrics.json")

# Tasks to use for flywheel measurement — a representative mix of easy, medium, hard
FLYWHEEL_TASK_IDS = [
    "notepad_hello",        # easy — type text
    "write_file_desktop",   # easy — filesystem
    "chrome_open",          # easy — launch
    "run_command_dir",      # medium — command execution
    "python_compute",       # medium — python eval
    "chrome_navigate",      # medium — multi-step
    "grok_ask_question",    # hard — chat wait + LLM
]


def _load_metrics() -> list[dict]:
    """Load existing flywheel metrics from disk."""
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            _log.warning(f"Could not load flywheel metrics: {e}")
    return []


def _save_metrics(metrics: list[dict]):
    """Save flywheel metrics to disk."""
    os.makedirs(os.path.dirname(METRICS_FILE), exist_ok=True)
    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)


def _get_flywheel_stats() -> dict:
    """Snapshot current flywheel data sizes for context."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    stats = {}
    for fname in ["knowledge.json", "self_improvement.json", "memory.json", "mind_state.json"]:
        fpath = os.path.join(data_dir, fname)
        if os.path.exists(fpath):
            stats[fname] = os.path.getsize(fpath)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    stats[f"{fname}_entries"] = len(data)
                elif isinstance(data, dict):
                    # Count entries in common structures
                    for key in ("entries", "task_history", "failures", "advice"):
                        if key in data and isinstance(data[key], list):
                            stats[f"{fname}_{key}"] = len(data[key])
            except Exception:
                pass
    return stats


def run_flywheel_sample(mode: str = "normal",
                        task_ids: Optional[list[str]] = None) -> dict:
    """Run a flywheel measurement sample.

    Args:
        mode: "normal" (full flywheel) or "baseline" (knowledge/improvement disabled)
        task_ids: Override which task IDs to run. Defaults to FLYWHEEL_TASK_IDS.

    Returns:
        A sample dict with timestamp, mode, per-task results, and aggregate stats.
    """
    from eval.benchmark import load_tasks, run_task
    from apps.registry import discover_modules
    discover_modules()

    ids = task_ids or FLYWHEEL_TASK_IDS
    tasks = load_tasks(filter_ids=ids)
    if not tasks:
        _log.error("No matching tasks found for flywheel experiment.")
        return {}

    # In baseline mode, temporarily neuter knowledge retrieval and improvement advice
    _patched = {}
    if mode == "baseline":
        _log.info("BASELINE MODE — disabling knowledge retrieval and self-improvement advice")
        try:
            from core.knowledge import get_knowledge_store
            ks = get_knowledge_store()
            _original_search = ks.search
            ks.search = lambda *a, **kw: []  # return no results
            _patched["knowledge_search"] = (ks, "search", _original_search)
        except Exception as e:
            _log.warning(f"Could not patch knowledge store: {e}")

        try:
            from core.self_improvement import get_improvement_engine
            ie = get_improvement_engine()
            _original_get_advice = ie.get_planning_advice
            ie.get_planning_advice = lambda *a, **kw: ""  # return no advice
            _patched["improvement_advice"] = (ie, "get_planning_advice", _original_get_advice)
        except Exception as e:
            _log.warning(f"Could not patch improvement engine: {e}")

    # Snapshot flywheel state before run
    flywheel_before = _get_flywheel_stats()

    sample = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "flywheel_data_before": flywheel_before,
        "tasks": [],
        "tasks_total": len(tasks),
        "tasks_passed": 0,
        "tasks_failed": 0,
        "total_time": 0.0,
        "total_actions": 0,
    }

    _log.info(f"{'='*60}")
    _log.info(f"  FLYWHEEL EXPERIMENT — {len(tasks)} tasks ({mode} mode)")
    _log.info(f"{'='*60}")

    run_start = time.time()

    for task in tasks:
        try:
            metrics = run_task(task, auto_mode=True)
            task_result = {
                "task_id": metrics.task_id,
                "passed": metrics.passed,
                "total_time": metrics.total_time,
                "total_actions": metrics.total_actions,
                "steps_planned": metrics.steps_planned,
                "steps_completed": metrics.steps_completed,
                "verifiers_passed": metrics.verifiers_passed,
                "verifiers_total": metrics.verifiers_total,
            }
            sample["tasks"].append(task_result)
            if metrics.passed:
                sample["tasks_passed"] += 1
            else:
                sample["tasks_failed"] += 1
            sample["total_actions"] += metrics.total_actions
        except Exception as e:
            _log.error(f"Task {task['id']} crashed: {e}")
            sample["tasks"].append({
                "task_id": task["id"],
                "passed": False,
                "total_time": 0,
                "total_actions": 0,
                "error": str(e),
            })
            sample["tasks_failed"] += 1

    sample["total_time"] = time.time() - run_start

    # Snapshot flywheel state after run
    sample["flywheel_data_after"] = _get_flywheel_stats()

    # Restore patched functions
    for key, (obj, attr, original) in _patched.items():
        setattr(obj, attr, original)
        _log.info(f"Restored {key}")

    # Compute aggregate metrics
    sample["pass_rate"] = sample["tasks_passed"] / sample["tasks_total"] if sample["tasks_total"] else 0
    passed_tasks = [t for t in sample["tasks"] if t.get("passed")]
    if passed_tasks:
        sample["avg_time_passed"] = sum(t["total_time"] for t in passed_tasks) / len(passed_tasks)
        sample["avg_actions_passed"] = sum(t["total_actions"] for t in passed_tasks) / len(passed_tasks)
    else:
        sample["avg_time_passed"] = 0
        sample["avg_actions_passed"] = 0

    # Save
    all_metrics = _load_metrics()
    all_metrics.append(sample)
    _save_metrics(all_metrics)

    _log.info(f"\n{'='*60}")
    _log.info(f"  FLYWHEEL SAMPLE COMPLETE ({mode})")
    _log.info(f"  Pass rate: {sample['pass_rate']:.0%} ({sample['tasks_passed']}/{sample['tasks_total']})")
    _log.info(f"  Total time: {sample['total_time']:.1f}s | Actions: {sample['total_actions']}")
    if passed_tasks:
        _log.info(f"  Avg time (passed): {sample['avg_time_passed']:.1f}s | Avg actions: {sample['avg_actions_passed']:.1f}")
    _log.info(f"  Saved to: {METRICS_FILE}")
    _log.info(f"{'='*60}")

    return sample


def generate_report() -> str:
    """Generate a trend report from all flywheel samples."""
    metrics = _load_metrics()
    if not metrics:
        return "No flywheel data collected yet. Run `python -m eval.flywheel_experiment` first."

    lines = [
        f"{'='*70}",
        f"  FLYWHEEL EXPERIMENT — TREND REPORT",
        f"  Samples: {len(metrics)} | First: {metrics[0]['timestamp'][:10]} | Latest: {metrics[-1]['timestamp'][:10]}",
        f"{'='*70}",
        "",
    ]

    # Separate normal vs baseline
    normal = [m for m in metrics if m.get("mode") == "normal"]
    baseline = [m for m in metrics if m.get("mode") == "baseline"]

    if normal:
        lines.append(f"  --- NORMAL MODE ({len(normal)} samples) ---")
        lines.append(f"  {'Date':<12} {'Pass Rate':>10} {'Avg Time':>10} {'Avg Actions':>12} {'Knowledge':>10}")
        lines.append(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*12} {'-'*10}")
        for s in normal:
            date = s["timestamp"][:10]
            pr = f"{s.get('pass_rate', 0):.0%}"
            at = f"{s.get('avg_time_passed', 0):.1f}s"
            aa = f"{s.get('avg_actions_passed', 0):.1f}"
            kb = s.get("flywheel_data_before", {}).get("knowledge.json", 0)
            kb_str = f"{kb/1024:.0f}KB" if kb else "?"
            lines.append(f"  {date:<12} {pr:>10} {at:>10} {aa:>12} {kb_str:>10}")

        # Trend calculation
        if len(normal) >= 2:
            first, last = normal[0], normal[-1]
            pr_delta = (last.get("pass_rate", 0) - first.get("pass_rate", 0)) * 100
            at_delta = last.get("avg_time_passed", 0) - first.get("avg_time_passed", 0)
            aa_delta = last.get("avg_actions_passed", 0) - first.get("avg_actions_passed", 0)
            lines.append("")
            lines.append(f"  TREND (first → latest):")
            lines.append(f"    Pass rate:   {pr_delta:+.1f}pp")
            lines.append(f"    Avg time:    {at_delta:+.1f}s {'(faster ✅)' if at_delta < 0 else '(slower ⚠️)' if at_delta > 0 else '(same)'}")
            lines.append(f"    Avg actions: {aa_delta:+.1f} {'(fewer ✅)' if aa_delta < 0 else '(more ⚠️)' if aa_delta > 0 else '(same)'}")

    if baseline:
        lines.append("")
        lines.append(f"  --- BASELINE MODE ({len(baseline)} samples) ---")
        for s in baseline:
            date = s["timestamp"][:10]
            pr = f"{s.get('pass_rate', 0):.0%}"
            at = f"{s.get('avg_time_passed', 0):.1f}s"
            lines.append(f"  {date:<12} {pr:>10} {at:>10}")

    # A/B comparison
    if normal and baseline:
        avg_normal_pr = sum(s.get("pass_rate", 0) for s in normal) / len(normal)
        avg_baseline_pr = sum(s.get("pass_rate", 0) for s in baseline) / len(baseline)
        avg_normal_time = sum(s.get("avg_time_passed", 0) for s in normal) / len(normal)
        avg_baseline_time = sum(s.get("avg_time_passed", 0) for s in baseline) / len(baseline)

        lines.append("")
        lines.append(f"  --- A/B COMPARISON ---")
        lines.append(f"  {'Metric':<20} {'Normal':>12} {'Baseline':>12} {'Delta':>12}")
        lines.append(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*12}")
        pr_d = (avg_normal_pr - avg_baseline_pr) * 100
        lines.append(f"  {'Pass rate':<20} {avg_normal_pr:>11.0%} {avg_baseline_pr:>11.0%} {pr_d:>+11.1f}pp")
        t_d = avg_normal_time - avg_baseline_time
        lines.append(f"  {'Avg time':<20} {avg_normal_time:>10.1f}s {avg_baseline_time:>10.1f}s {t_d:>+10.1f}s")

        lines.append("")
        if pr_d > 0:
            lines.append(f"  ✅ FLYWHEEL IS HELPING: +{pr_d:.1f}pp pass rate with knowledge & self-improvement active")
        elif pr_d < 0:
            lines.append(f"  ⚠️ FLYWHEEL MAY BE HURTING: {pr_d:.1f}pp pass rate — investigate knowledge quality")
        else:
            lines.append(f"  ➡️ NO DIFFERENCE: flywheel data is not impacting pass rate (yet)")

    lines.append("")
    lines.append(f"{'='*70}")
    return "\n".join(lines)


def run_scheduled(interval_hours: float = 6, max_runs: int = 28):
    """Run the flywheel experiment on a schedule.

    Default: every 6 hours for 7 days (28 runs).
    """
    interval_s = interval_hours * 3600
    _log.info(f"Scheduled flywheel experiment: every {interval_hours}h, max {max_runs} runs")

    for i in range(max_runs):
        _log.info(f"\n--- Scheduled run {i+1}/{max_runs} ---")
        try:
            run_flywheel_sample(mode="normal")
        except Exception as e:
            _log.error(f"Flywheel sample failed: {e}")

        if i < max_runs - 1:
            next_run = datetime.fromtimestamp(time.time() + interval_s)
            _log.info(f"Next run at: {next_run.strftime('%Y-%m-%d %H:%M')}")
            time.sleep(interval_s)

    _log.info("\nScheduled experiment complete. Generating report...")
    print(generate_report())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="OnyxKraken Flywheel Experiment")
    parser.add_argument("--baseline", action="store_true",
                        help="Run in baseline mode (knowledge/improvement disabled)")
    parser.add_argument("--report", action="store_true",
                        help="Print trend report from collected data")
    parser.add_argument("--schedule", type=float, default=0,
                        help="Run on schedule every N hours (e.g., --schedule 6)")
    parser.add_argument("--ids", nargs="*",
                        help="Override task IDs (e.g., --ids notepad_hello chrome_open)")
    args = parser.parse_args()

    if args.report:
        print(generate_report())
        return

    if args.schedule > 0:
        run_scheduled(interval_hours=args.schedule)
        return

    mode = "baseline" if args.baseline else "normal"
    run_flywheel_sample(mode=mode, task_ids=args.ids)


if __name__ == "__main__":
    main()
