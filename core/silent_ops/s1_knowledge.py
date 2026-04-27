"""S1 — Knowledge Consolidation: merge duplicates, prune stale entries."""

import json
import os
import time

from log import get_logger

_log = get_logger("silent_ops.s1")


def knowledge_consolidation(_extract_json, _mark_run) -> dict:
    """Merge duplicate knowledge entries, prune stale ones, summarise verbose groups.

    Groups entries by category + overlapping tags, then asks the LLM to
    consolidate each group that has potential duplicates.

    Returns:
        Summary dict with entries_before, entries_after, groups_consolidated.
    """
    from core.knowledge import get_knowledge_store
    from agent.model_router import router

    ks = get_knowledge_store()
    entries = ks.get_all()
    if len(entries) < 5:
        _log.info("Knowledge consolidation skipped — too few entries")
        return {"skipped": True, "reason": "too_few_entries", "count": len(entries)}

    entries_before = len(entries)

    # Group by category
    groups: dict[str, list[dict]] = {}
    for e in entries:
        cat = e.get("category", "general")
        groups.setdefault(cat, []).append(e)

    groups_consolidated = 0
    entries_removed = 0

    for category, group in groups.items():
        if len(group) < 3:
            continue

        # Build content list for LLM
        content_lines = []
        for i, e in enumerate(group):
            tags = ", ".join(e.get("tags", []))
            content_lines.append(f"[{i}] ({tags}) {e['content'][:300]}")

        if len(content_lines) > 30:
            content_lines = content_lines[:30]

        prompt = (
            f"You are reviewing {len(content_lines)} knowledge entries in the '{category}' category.\n"
            "Identify DUPLICATE or REDUNDANT entries that say essentially the same thing.\n"
            "Return ONLY a JSON object:\n"
            '{"duplicates": [[idx1, idx2, ...], [idx3, idx4, ...]], '
            '"stale": [idx5, idx6], '
            '"summary": "what you found"}\n\n'
            "- 'duplicates': groups of entry indices that are duplicates of each other (keep first, remove rest)\n"
            "- 'stale': indices of entries that are outdated or no longer useful\n"
            "- If no duplicates or stale entries, return empty arrays.\n\n"
            "Entries:\n" + "\n".join(content_lines) + "\n\nOutput ONLY JSON."
        )

        try:
            raw = router.get_content("reasoning", [{"role": "user", "content": prompt}])
            result = _extract_json(raw)
            if not result:
                continue

            # Collect indices to remove
            remove_indices = set()
            for dup_group in result.get("duplicates", []):
                if isinstance(dup_group, list) and len(dup_group) > 1:
                    # Keep first, remove rest
                    for idx in dup_group[1:]:
                        if isinstance(idx, int) and 0 <= idx < len(group):
                            remove_indices.add(idx)

            for idx in result.get("stale", []):
                if isinstance(idx, int) and 0 <= idx < len(group):
                    remove_indices.add(idx)

            # Remove identified entries
            if remove_indices:
                ids_to_remove = {group[i]["id"] for i in remove_indices if i < len(group)}
                for entry_id in ids_to_remove:
                    ks.remove(entry_id)
                    entries_removed += 1
                groups_consolidated += 1

                _log.info(
                    f"Consolidated '{category}': removed {len(ids_to_remove)} entries "
                    f"({result.get('summary', '')[:80]})"
                )

        except Exception as e:
            _log.warning(f"Consolidation error for '{category}': {e}")
            continue

    entries_after = len(ks.get_all())
    _mark_run("knowledge_consolidation")

    summary = {
        "entries_before": entries_before,
        "entries_after": entries_after,
        "entries_removed": entries_removed,
        "groups_consolidated": groups_consolidated,
    }
    _log.info(f"Knowledge consolidation complete: {summary}")

    # Store result as knowledge entry
    if entries_removed > 0:
        try:
            ks.add(
                content=f"Knowledge consolidation: merged {entries_removed} duplicate/stale entries "
                        f"across {groups_consolidated} categories. "
                        f"Store went from {entries_before} to {entries_after} entries.",
                category="general",
                tags=["self-improvement", "consolidation"],
                source="silent_ops:knowledge_consolidation",
            )
        except Exception as e:
            _log.debug(f"Failed to store consolidation result in knowledge: {e}")

    return summary
