"""S4 — Memory Compaction: summarize old task history, keep recent ones detailed."""

import json
import os
import time

from log import get_logger

_log = get_logger("silent_ops.s4")


def memory_compaction(_extract_json, _mark_run) -> dict:
    """Summarize old task history entries, keeping recent ones detailed.

    Tasks older than 7 days get grouped by week and replaced with
    LLM-generated weekly summaries.
    """
    from agent.model_router import router

    try:
        from memory.store import MemoryStore
        memory = MemoryStore()
        all_data = memory.get_all()
        tasks = all_data.get("task_history", [])
    except Exception as e:
        return {"skipped": True, "reason": f"memory_error: {e}"}

    if len(tasks) < 50:
        _mark_run("memory_compaction")
        return {"skipped": True, "reason": "too_few_tasks", "count": len(tasks)}

    now = time.time()
    seven_days_ago = now - 7 * 86400

    # Split into old and recent
    old_tasks = [t for t in tasks if t.get("timestamp", now) < seven_days_ago]
    recent_tasks = [t for t in tasks if t.get("timestamp", now) >= seven_days_ago]

    if len(old_tasks) < 20:
        _mark_run("memory_compaction")
        return {"skipped": True, "reason": "too_few_old_tasks", "count": len(old_tasks)}

    # Group old tasks into a single batch for summarisation
    successes = sum(1 for t in old_tasks if t.get("success"))
    failures = len(old_tasks) - successes
    apps_used = {}
    for t in old_tasks:
        app = t.get("app", "unknown")
        apps_used[app] = apps_used.get(app, 0) + 1

    prompt = (
        f"Summarise these {len(old_tasks)} old task history entries in 2-3 sentences:\n"
        f"  - {successes} successes, {failures} failures\n"
        f"  - Apps: {', '.join(f'{a} ({c})' for a, c in sorted(apps_used.items(), key=lambda x: -x[1])[:8])}\n"
        f"  - Sample goals: {'; '.join(t.get('goal', '')[:60] for t in old_tasks[:5])}\n\n"
        "Be concise. Output ONLY the summary text."
    )

    try:
        summary_text = router.get_content("reasoning", [{"role": "user", "content": prompt}]).strip()
    except Exception as e:
        _mark_run("memory_compaction")
        return {"error": str(e)}

    # Create a summary entry and replace old tasks
    summary_entry = {
        "goal": f"[COMPACTED] {len(old_tasks)} tasks",
        "app": "summary",
        "success": True,
        "timestamp": old_tasks[0].get("timestamp", now),
        "notes": summary_text,
        "compacted_count": len(old_tasks),
        "compacted_successes": successes,
        "compacted_failures": failures,
    }

    # Replace task history with summary + recent
    all_data["task_history"] = [summary_entry] + recent_tasks
    memory._data = all_data
    memory._save()

    _mark_run("memory_compaction")

    result = {
        "tasks_compacted": len(old_tasks),
        "tasks_remaining": len(recent_tasks) + 1,
        "summary": summary_text[:200],
    }
    _log.info(f"Memory compaction complete: {result}")

    # Store compaction event in knowledge
    try:
        from core.knowledge import get_knowledge_store
        ks = get_knowledge_store()
        ks.add(
            content=f"Memory compacted: {len(old_tasks)} old tasks → 1 summary. {summary_text[:150]}",
            category="general",
            tags=["self-improvement", "memory"],
            source="silent_ops:memory_compaction",
        )
    except Exception as e:
        _log.debug(f"Failed to store compaction event in knowledge: {e}")

    return result
