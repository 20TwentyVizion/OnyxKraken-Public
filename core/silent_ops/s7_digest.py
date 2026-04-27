"""S7 — Daily Digest Generation: summarize daily learning and progress."""

import datetime
import os
import time

from log import get_logger

_log = get_logger("silent_ops.s7")


def daily_digest(_extract_json, _mark_run) -> dict:
    """Generate a daily summary of everything Onyx learned and did.

    Writes to data/digests/YYYY-MM-DD.md.  Runs once per day.
    """
    from agent.model_router import router

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    today = datetime.date.today().isoformat()

    digest_dir = os.path.join(project_root, "data", "digests")
    digest_path = os.path.join(digest_dir, f"{today}.md")

    # Skip if today's digest already exists
    if os.path.exists(digest_path):
        _mark_run("daily_digest")
        return {"skipped": True, "reason": "already_generated", "date": today}

    # Gather data
    sections = []

    # Task history
    try:
        from memory.store import MemoryStore
        memory = MemoryStore()
        tasks = memory.get_all().get("task_history", [])
        today_start = time.time() - 86400
        recent = [t for t in tasks if t.get("timestamp", 0) >= today_start]
        if recent:
            s = sum(1 for t in recent if t.get("success"))
            sections.append(f"TASKS: {len(recent)} tasks ({s} succeeded, {len(recent)-s} failed)")
    except Exception as e:
        _log.debug(f"Digest: could not read task history: {e}")

    # Knowledge
    try:
        from core.knowledge import get_knowledge_store
        ks = get_knowledge_store()
        stats = ks.get_stats()
        sections.append(f"KNOWLEDGE: {stats.get('total_entries', 0)} entries total")
    except Exception as e:
        _log.debug(f"Digest: could not read knowledge stats: {e}")

    # Mind state
    try:
        from core.mind import get_mind
        mind = get_mind()
        ms = mind.get_stats()
        sections.append(f"MIND: mood={ms.get('mood','?')}, focus={ms.get('focus','?')}")
        sections.append(f"REFLECTIONS: {ms.get('total_reflections',0)} total, "
                        f"proactive goals: {ms.get('proactive_goals_generated',0)} generated, "
                        f"{ms.get('proactive_goals_completed',0)} completed")
    except Exception as e:
        _log.debug(f"Digest: could not read mind state: {e}")

    # Self-improvement
    try:
        from core.self_improvement import get_improvement_engine
        si = get_improvement_engine().get_stats()
        sections.append(f"SELF-IMPROVEMENT: {si.get('total_gaps_identified',0)} gaps, "
                        f"{si.get('total_modules_generated',0)} modules generated")
    except Exception as e:
        _log.debug(f"Digest: could not read self-improvement stats: {e}")

    if not sections:
        _mark_run("daily_digest")
        return {"skipped": True, "reason": "no_data"}

    prompt = (
        f"Generate a concise daily digest for OnyxKraken, date {today}.\n\n"
        "Data:\n" + "\n".join(f"  - {s}" for s in sections) + "\n\n"
        "Write a short markdown digest (3-5 bullet points) summarising key events, "
        "progress, and what to focus on tomorrow. Be specific and concise."
    )

    try:
        digest_text = router.get_content("reasoning", [{"role": "user", "content": prompt}]).strip()
    except Exception as e:
        _mark_run("daily_digest")
        return {"error": str(e)}

    # Write digest
    os.makedirs(digest_dir, exist_ok=True)
    with open(digest_path, "w", encoding="utf-8") as f:
        f.write(f"# OnyxKraken Daily Digest — {today}\n\n{digest_text}\n")

    _mark_run("daily_digest")
    _log.info(f"Daily digest written: {digest_path}")
    return {"date": today, "path": digest_path, "length": len(digest_text)}
