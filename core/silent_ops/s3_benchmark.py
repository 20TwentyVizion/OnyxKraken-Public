"""S3 — Benchmark Regression Analysis: detect trends across saved reports."""

import glob
import json
import os
import time

from log import get_logger

_log = get_logger("silent_ops.s3")


def benchmark_analysis(_extract_json, _mark_run) -> dict:
    """Analyze saved benchmark reports for trends, regressions, and improvements.

    Reads all bench_*.json from eval_reports/, tracks per-task pass/fail trends,
    detects regressions and improvements, and stores insights.

    Returns:
        Summary dict with total_reports, regressions, improvements, insights.
    """
    from agent.model_router import router

    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "eval_reports")
    if not os.path.isdir(reports_dir):
        return {"skipped": True, "reason": "no_reports_dir"}

    files = sorted(glob.glob(os.path.join(reports_dir, "bench_*.json")))
    if len(files) < 3:
        return {"skipped": True, "reason": "too_few_reports", "count": len(files)}

    # Load all reports
    reports = []
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                reports.append(json.load(f))
        except (json.JSONDecodeError, IOError):
            continue

    # Build per-task history
    task_history: dict[str, list[dict]] = {}
    for report in reports:
        ts = report.get("timestamp", "")
        for tr in report.get("task_results", []):
            tid = tr.get("task_id", "unknown")
            task_history.setdefault(tid, []).append({
                "timestamp": ts,
                "passed": tr.get("passed", False),
                "time": tr.get("total_time", 0),
                "actions": tr.get("total_actions", 0),
            })

    # Detect regressions and improvements
    regressions = []
    improvements = []
    for task_id, runs in task_history.items():
        if len(runs) < 2:
            continue
        recent = runs[-3:]  # last 3 runs
        older = runs[:-3] if len(runs) > 3 else runs[:1]

        recent_rate = sum(1 for r in recent if r["passed"]) / len(recent)
        older_rate = sum(1 for r in older if r["passed"]) / len(older) if older else 0

        if recent_rate < older_rate - 0.3:
            regressions.append({"task_id": task_id, "recent_rate": recent_rate, "older_rate": older_rate})
        elif recent_rate > older_rate + 0.3:
            improvements.append({"task_id": task_id, "recent_rate": recent_rate, "older_rate": older_rate})

    # Overall trend
    if len(reports) >= 2:
        first_half = reports[:len(reports)//2]
        second_half = reports[len(reports)//2:]
        avg_first = sum(r.get("tasks_passed", 0) / max(r.get("tasks_total", 1), 1) for r in first_half) / len(first_half)
        avg_second = sum(r.get("tasks_passed", 0) / max(r.get("tasks_total", 1), 1) for r in second_half) / len(second_half)
        trend = "improving" if avg_second > avg_first + 0.05 else "declining" if avg_second < avg_first - 0.05 else "stable"
    else:
        trend = "insufficient_data"

    # Ask LLM for insight if we have meaningful data
    insight = ""
    if regressions or improvements:
        data_summary = f"Analyzed {len(reports)} benchmark reports across {len(task_history)} tasks.\n"
        data_summary += f"Overall trend: {trend}\n"
        if regressions:
            data_summary += f"REGRESSIONS ({len(regressions)}):\n"
            for r in regressions[:5]:
                data_summary += f"  - {r['task_id']}: was {r['older_rate']:.0%} → now {r['recent_rate']:.0%}\n"
        if improvements:
            data_summary += f"IMPROVEMENTS ({len(improvements)}):\n"
            for i in improvements[:5]:
                data_summary += f"  - {i['task_id']}: was {i['older_rate']:.0%} → now {i['recent_rate']:.0%}\n"

        prompt = (
            "You are OnyxKraken's self-analysis system reviewing benchmark trends.\n\n"
            f"{data_summary}\n"
            "Provide a concise 2-3 sentence insight about what's happening and what to prioritize.\n"
            "Output ONLY the insight text, no JSON."
        )

        try:
            insight = router.get_content("reasoning", [{"role": "user", "content": prompt}]).strip()
        except Exception as e:
            _log.warning(f"Benchmark insight generation failed: {e}")

    # Write analysis to file
    analysis = {
        "timestamp": time.time(),
        "total_reports": len(reports),
        "total_tasks": len(task_history),
        "trend": trend,
        "regressions": regressions,
        "improvements": improvements,
        "insight": insight,
        "per_task_summary": {
            tid: {
                "total_runs": len(runs),
                "pass_rate": round(sum(1 for r in runs if r["passed"]) / len(runs) * 100),
                "avg_time": round(sum(r["time"] for r in runs) / len(runs), 1),
            }
            for tid, runs in task_history.items()
        },
    }

    analysis_path = os.path.join(reports_dir, "trend_analysis.json")
    try:
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2, default=str)
        _log.info(f"Benchmark analysis written to {analysis_path}")
    except IOError as e:
        _log.warning(f"Failed to write trend analysis: {e}")

    # Store insight in knowledge
    if insight:
        try:
            from core.knowledge import get_knowledge_store
            ks = get_knowledge_store()
            ks.add(
                content=f"Benchmark analysis: {insight}",
                category="general",
                tags=["benchmark", "self-improvement", "trends"],
                source="silent_ops:benchmark_analysis",
            )
        except Exception as e:
            _log.debug(f"Failed to store benchmark insight in knowledge: {e}")

    _mark_run("benchmark_analysis")

    summary = {
        "total_reports": len(reports),
        "trend": trend,
        "regressions": len(regressions),
        "improvements": len(improvements),
        "insight": insight[:200] if insight else "",
    }
    _log.info(f"Benchmark analysis complete: {summary}")
    return summary
