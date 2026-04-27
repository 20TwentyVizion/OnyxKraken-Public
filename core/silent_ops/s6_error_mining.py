"""S6 — Error Pattern Mining: cluster failures, pre-generate fix strategies."""

import json
import os
import time

from log import get_logger

_log = get_logger("silent_ops.s6")


def error_pattern_mining(_extract_json, _mark_run) -> dict:
    """Scan failures across all stores, cluster by pattern, pre-generate fix strategies.

    Collects errors from task history and self-improvement failed_tasks,
    asks LLM to cluster them and suggest preventive measures.
    """
    from agent.model_router import router

    errors = []

    # Collect from task history
    try:
        from memory.store import MemoryStore
        memory = MemoryStore()
        tasks = memory.get_all().get("task_history", [])
        for t in tasks[-30:]:
            if not t.get("success"):
                errors.append({
                    "source": "task_history",
                    "app": t.get("app", "unknown"),
                    "goal": t.get("goal", "")[:100],
                    "notes": t.get("notes", "")[:150],
                })
    except Exception as e:
        _log.debug(f"Error mining: could not read task history: {e}")

    # Collect from self-improvement failures
    try:
        from core.self_improvement import get_improvement_engine
        engine = get_improvement_engine()
        failed = engine.get_failed_tasks()
        for ft in failed[-15:]:
            errors.append({
                "source": "self_improvement",
                "app": ft.get("app_name", "unknown"),
                "goal": ft.get("goal", "")[:100],
                "notes": ft.get("error", "")[:150],
            })
    except Exception as e:
        _log.debug(f"Error mining: could not read self-improvement failures: {e}")

    if len(errors) < 3:
        _mark_run("error_pattern_mining")
        return {"skipped": True, "reason": "too_few_errors", "count": len(errors)}

    # Ask LLM to cluster and analyse
    error_lines = []
    for i, err in enumerate(errors[:25]):
        error_lines.append(
            f"[{i}] app={err['app']}, goal=\"{err['goal']}\", notes=\"{err['notes']}\""
        )

    prompt = (
        f"You are analysing {len(error_lines)} recent failures from OnyxKraken.\n\n"
        "Errors:\n" + "\n".join(error_lines) + "\n\n"
        "Cluster these errors by root cause pattern. For each cluster, suggest a preventive fix.\n"
        "Respond with ONLY a JSON object:\n"
        '{"clusters": [{"pattern": "description", "count": N, "fix": "suggested fix"}], '
        '"summary": "overall observation"}\n'
        "Output ONLY JSON."
    )

    try:
        raw = router.get_content("reasoning", [{"role": "user", "content": prompt}])
        result = _extract_json(raw)
    except Exception as e:
        _mark_run("error_pattern_mining")
        return {"error": str(e)}

    if not result:
        _mark_run("error_pattern_mining")
        return {"skipped": True, "reason": "llm_parse_failed"}

    # Store patterns in knowledge
    clusters = result.get("clusters", [])
    try:
        from core.knowledge import get_knowledge_store
        ks = get_knowledge_store()
        for cluster in clusters[:5]:
            ks.add(
                content=f"Error pattern: {cluster.get('pattern', '')}. "
                        f"Fix: {cluster.get('fix', '')}",
                category="task_patterns",
                tags=["error_pattern", "self-improvement"],
                source="silent_ops:error_pattern_mining",
            )
    except Exception as e:
        _log.debug(f"Failed to store error patterns in knowledge: {e}")

    _mark_run("error_pattern_mining")

    summary = {
        "errors_analysed": len(errors),
        "clusters_found": len(clusters),
        "summary": result.get("summary", "")[:200],
    }
    _log.info(f"Error pattern mining complete: {summary}")
    return summary
