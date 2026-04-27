"""Analytics routes — learning stats, benchmark trends, meta-metric."""

import glob
import json
import logging
import os
import time

from fastapi import APIRouter

_log = logging.getLogger("server")

router = APIRouter()


# ---------------------------------------------------------------------------
# Unified learning stats (consumed by onyx-web StatsPanel)
# ---------------------------------------------------------------------------

@router.get("/api/learning")
async def learning_stats():
    """Unified learning stats — aggregates memory, knowledge, and self-improvement data.

    Designed for the web face's Stats panel to surface the self-improvement flywheel.
    """
    data = {"available": True}

    # Task history from memory
    try:
        from memory.store import MemoryStore
        mem = MemoryStore()
        all_data = mem.get_all()
        tasks = all_data.get("task_history", [])
        successes = sum(1 for t in tasks if t.get("success"))
        data["tasks"] = {
            "total": len(tasks),
            "successes": successes,
            "success_rate": round(successes / len(tasks) * 100) if tasks else 0,
            "recent": tasks[-5:][::-1],  # newest first
            "apps_used": list({t.get("app", "unknown") for t in tasks}),
        }
    except Exception as e:
        _log.debug(f"Learning stats: could not read task history: {e}")
        data["tasks"] = None

    # Knowledge store
    try:
        from core.knowledge import get_knowledge_store
        ks = get_knowledge_store()
        ks_stats = ks.get_stats()
        data["knowledge"] = {
            "total_entries": ks_stats.get("total_entries", 0),
            "categories": ks_stats.get("entries_by_category", {}),
        }
    except Exception as e:
        _log.debug(f"Learning stats: could not read knowledge store: {e}")
        data["knowledge"] = None

    # Self-improvement engine
    try:
        from core.self_improvement import get_improvement_engine
        engine = get_improvement_engine()
        si_stats = engine.get_stats()
        gaps = engine.get_unresolved_gaps()
        data["self_improvement"] = {
            **si_stats,
            "unresolved_gaps": [
                {"description": g.get("description", "")[:120], "type": g.get("gap_type", "")}
                for g in gaps[:5]
            ],
        }
    except Exception as e:
        _log.debug(f"Learning stats: could not read self-improvement engine: {e}")
        data["self_improvement"] = None

    # Mind stats (identity, reflections)
    try:
        from core.mind import get_mind
        mind = get_mind()
        mind_data = mind.get_stats()
        data["mind"] = mind_data
    except Exception as e:
        _log.debug(f"Learning stats: could not read mind state: {e}")
        data["mind"] = None

    return data


# ---------------------------------------------------------------------------
# Benchmark trends (consumed by onyx-web StatsPanel)
# ---------------------------------------------------------------------------

@router.get("/api/benchmarks")
async def benchmark_trends(limit: int = 20):
    """Return benchmark trend data — pass rates & timing across recent runs."""
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "eval_reports")
    if not os.path.isdir(reports_dir):
        return {"runs": [], "total_reports": 0}

    files = sorted(glob.glob(os.path.join(reports_dir, "bench_*.json")))
    files = files[-limit:]  # most recent N

    runs = []
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                report = json.load(f)
            total = report.get("tasks_total", 0)
            passed = report.get("tasks_passed", 0)
            runs.append({
                "timestamp": report.get("timestamp", ""),
                "tasks_total": total,
                "tasks_passed": passed,
                "tasks_failed": report.get("tasks_failed", 0),
                "pass_rate": round(passed / total * 100) if total else 0,
                "total_time": round(report.get("total_time", 0), 1),
                "total_actions": report.get("total_actions", 0),
            })
        except (json.JSONDecodeError, IOError, KeyError):
            continue

    return {
        "runs": runs,
        "total_reports": len(runs),
        "best_pass_rate": max((r["pass_rate"] for r in runs), default=0),
        "latest_pass_rate": runs[-1]["pass_rate"] if runs else 0,
    }


# ---------------------------------------------------------------------------
# Meta-metric — improvement rate per idle hour
# ---------------------------------------------------------------------------

@router.get("/api/meta-metric")
async def meta_metric():
    """Improvement rate per idle hour — the north-star metric."""
    metrics = {"timestamp": time.time()}

    # Daemon uptime
    try:
        from core.autonomy import get_daemon
        daemon = get_daemon()
        stats = daemon.get_stats()
        log = stats.get("recent_log", [])
        silent_ops = sum(1 for e in log if e.get("type") == "silent_op")
        metrics["daemon_state"] = stats.get("state", "unknown")
        metrics["tasks_completed"] = stats.get("tasks_completed", 0)
        metrics["tasks_failed"] = stats.get("tasks_failed", 0)
        metrics["silent_ops_recent"] = silent_ops
    except Exception as e:
        _log.debug(f"Meta-metric: could not read daemon stats: {e}")

    # Knowledge growth
    try:
        from core.knowledge import get_knowledge_store
        ks = get_knowledge_store()
        k_stats = ks.get_stats()
        metrics["knowledge_entries"] = k_stats.get("total_entries", 0)
        metrics["knowledge_retrievals"] = k_stats.get("total_retrievals", 0)
    except Exception as e:
        _log.debug(f"Meta-metric: could not read knowledge stats: {e}")

    # Success rate (recent vs older)
    try:
        from memory.store import MemoryStore
        memory = MemoryStore()
        tasks = memory.get_all().get("task_history", [])
        if len(tasks) >= 10:
            mid = len(tasks) // 2
            older = tasks[:mid]
            recent = tasks[mid:]
            older_rate = sum(1 for t in older if t.get("success")) / len(older) * 100
            recent_rate = sum(1 for t in recent if t.get("success")) / len(recent) * 100
            metrics["success_rate_older"] = round(older_rate, 1)
            metrics["success_rate_recent"] = round(recent_rate, 1)
            metrics["success_rate_delta"] = round(recent_rate - older_rate, 1)
        elif tasks:
            rate = sum(1 for t in tasks if t.get("success")) / len(tasks) * 100
            metrics["success_rate_recent"] = round(rate, 1)
    except Exception as e:
        _log.debug(f"Meta-metric: could not read success rate: {e}")

    # Gaps resolved
    try:
        from core.self_improvement import get_improvement_engine
        si = get_improvement_engine().get_stats()
        total_gaps = si.get("total_gaps_identified", 0)
        unresolved = len(si.get("unresolved_gaps", []))
        metrics["gaps_identified"] = total_gaps
        metrics["gaps_resolved"] = total_gaps - unresolved
        metrics["modules_generated"] = si.get("total_modules_generated", 0)
    except Exception as e:
        _log.debug(f"Meta-metric: could not read gaps data: {e}")

    # Mind stats
    try:
        from core.mind import get_mind
        ms = get_mind().get_stats()
        metrics["reflections"] = ms.get("total_reflections", 0)
        metrics["proactive_goals"] = ms.get("proactive_goals_generated", 0)
        metrics["proactive_completed"] = ms.get("proactive_goals_completed", 0)
    except Exception as e:
        _log.debug(f"Meta-metric: could not read mind stats: {e}")

    # Composite score
    score = 0
    score += metrics.get("knowledge_entries", 0) * 0.5
    score += metrics.get("gaps_resolved", 0) * 5
    score += metrics.get("modules_generated", 0) * 10
    score += metrics.get("reflections", 0) * 2
    score += max(0, metrics.get("success_rate_delta", 0)) * 3
    score += metrics.get("silent_ops_recent", 0) * 1
    metrics["improvement_score"] = round(score, 1)

    return metrics
