"""S2 — Prompt Template Optimization: analyze task patterns for better prompts."""

import json
import os
import time

from log import get_logger

_log = get_logger("silent_ops.s2")


def prompt_optimization(_extract_json, _mark_run) -> dict:
    """Analyze task history to find which patterns lead to success vs failure.

    Groups tasks by app_name, compares success/failure patterns, and generates
    actionable prompt improvement suggestions stored in data/prompt_suggestions.json.
    """
    from agent.model_router import router

    try:
        from memory.store import MemoryStore
        memory = MemoryStore()
        tasks = memory.get_all().get("task_history", [])
    except Exception as e:
        return {"skipped": True, "reason": f"memory_error: {e}"}

    if len(tasks) < 10:
        return {"skipped": True, "reason": "too_few_tasks", "count": len(tasks)}

    # Group by app
    by_app: dict[str, dict[str, list]] = {}
    for t in tasks[-50:]:
        app = t.get("app", "unknown")
        by_app.setdefault(app, {"success": [], "failure": []})
        key = "success" if t.get("success") else "failure"
        by_app[app][key].append(t.get("goal", "")[:120])

    # Only analyse apps with both successes and failures
    candidates = {app: data for app, data in by_app.items()
                  if data["success"] and data["failure"]}

    if not candidates:
        _mark_run("prompt_optimization")
        return {"skipped": True, "reason": "no_mixed_apps"}

    suggestions = {}
    for app, data in list(candidates.items())[:3]:
        prompt = (
            f"You are analysing task history for the '{app}' application module.\n\n"
            f"SUCCESSFUL tasks ({len(data['success'])}):\n"
            + "\n".join(f"  - {g}" for g in data["success"][:8]) + "\n\n"
            f"FAILED tasks ({len(data['failure'])}):\n"
            + "\n".join(f"  - {g}" for g in data["failure"][:8]) + "\n\n"
            "What patterns distinguish successes from failures? "
            "Suggest 2-3 concrete prompt improvements that would help the agent succeed more often.\n"
            "Respond with ONLY a JSON object:\n"
            '{"patterns": "what you noticed", "suggestions": ["suggestion1", "suggestion2"]}\n'
            "Output ONLY JSON."
        )
        try:
            raw = router.get_content("reasoning", [{"role": "user", "content": prompt}])
            result = _extract_json(raw)
            if result:
                suggestions[app] = result
        except Exception as e:
            _log.warning(f"Prompt optimization error for '{app}': {e}")

    # Write suggestions
    if suggestions:
        suggestions_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "prompt_suggestions.json"
        )
        existing = {}
        if os.path.exists(suggestions_path):
            try:
                with open(suggestions_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                _log.debug(f"Failed to load prompt suggestions: {e}")

        existing["last_updated"] = time.time()
        existing.setdefault("by_app", {}).update(suggestions)

        os.makedirs(os.path.dirname(suggestions_path), exist_ok=True)
        with open(suggestions_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, default=str)

        _log.info(f"Prompt optimization: generated suggestions for {list(suggestions.keys())}")

    _mark_run("prompt_optimization")
    return {
        "apps_analysed": len(suggestions),
        "apps": list(suggestions.keys()),
    }
