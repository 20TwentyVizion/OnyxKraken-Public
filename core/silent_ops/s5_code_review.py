"""S5 — Code Self-Review: LLM reviews random source files for bugs and improvements."""

import json
import os
import random
import time

from log import get_logger

_log = get_logger("silent_ops.s5")


def code_self_review(_extract_json, _mark_run) -> dict:
    """LLM reviews a random OnyxKraken source file for bugs, missing error
    handling, and potential improvements.  Results are stored in
    data/code_reviews.json keyed by file path.
    """
    from agent.model_router import router

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    # Candidate directories
    search_dirs = [
        os.path.join(project_root, "core"),
        os.path.join(project_root, "agent"),
        os.path.join(project_root, "apps", "modules"),
        os.path.join(project_root, "memory"),
        os.path.join(project_root, "desktop"),
    ]

    py_files = []
    for d in search_dirs:
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith(".py") and not f.startswith("__"):
                    py_files.append(os.path.join(d, f))

    if not py_files:
        _mark_run("code_self_review")
        return {"skipped": True, "reason": "no_files"}

    # Pick a random file we haven't reviewed recently
    reviews_path = os.path.join(project_root, "data", "code_reviews.json")
    existing_reviews = {}
    if os.path.exists(reviews_path):
        try:
            with open(reviews_path, "r", encoding="utf-8") as f:
                existing_reviews = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            _log.debug(f"Failed to load existing code reviews: {e}")

    # Prefer files not yet reviewed
    unreviewed = [f for f in py_files if f not in existing_reviews.get("reviews", {})]
    target = random.choice(unreviewed) if unreviewed else random.choice(py_files)

    try:
        with open(target, "r", encoding="utf-8") as f:
            code = f.read()
    except IOError:
        _mark_run("code_self_review")
        return {"skipped": True, "reason": "read_error", "file": target}

    # Truncate very long files
    if len(code) > 6000:
        code = code[:6000] + "\n# ... (truncated)"

    rel_path = os.path.relpath(target, project_root)
    prompt = (
        f"Review this OnyxKraken source file: {rel_path}\n\n"
        f"```python\n{code}\n```\n\n"
        "Identify:\n"
        "1. Bugs or logic errors\n"
        "2. Missing error handling or edge cases\n"
        "3. Performance issues\n"
        "4. Code style improvements\n\n"
        "Respond with ONLY a JSON object:\n"
        '{"findings": [{"severity": "high|medium|low", "line_hint": "approximate location", '
        '"issue": "description", "suggestion": "fix"}], "overall": "summary sentence"}\n'
        "Output ONLY JSON."
    )

    try:
        raw = router.get_content("reasoning", [{"role": "user", "content": prompt}])
        result = _extract_json(raw)
    except Exception as e:
        _mark_run("code_self_review")
        return {"error": str(e), "file": rel_path}

    if not result:
        _mark_run("code_self_review")
        return {"skipped": True, "reason": "llm_parse_failed", "file": rel_path}

    # Store review
    existing_reviews.setdefault("reviews", {})[target] = {
        "timestamp": time.time(),
        "findings": result.get("findings", []),
        "overall": result.get("overall", ""),
    }
    os.makedirs(os.path.dirname(reviews_path), exist_ok=True)
    with open(reviews_path, "w", encoding="utf-8") as f:
        json.dump(existing_reviews, f, indent=2, default=str)

    findings = result.get("findings", [])
    high_count = sum(1 for f in findings if f.get("severity") == "high")

    _mark_run("code_self_review")
    summary = {
        "file": rel_path,
        "findings": len(findings),
        "high_severity": high_count,
        "overall": result.get("overall", "")[:200],
    }
    _log.info(f"Code self-review of {rel_path}: {len(findings)} findings ({high_count} high)")
    return summary
