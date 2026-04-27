"""S8 — Test Generation: generate pytest tests for untested modules."""

import json
import os
import random
import time

from log import get_logger

_log = get_logger("silent_ops.s8")


def test_generation(_extract_json, _mark_run) -> dict:
    """Generate pytest test cases for a random untested module.

    Writes to data/generated_tests/test_{module}.py.
    """
    from agent.model_router import router

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    # Find modules that don't have corresponding tests
    module_dirs = ["core", "memory", "agent"]
    candidates = []
    for d in module_dirs:
        full = os.path.join(project_root, d)
        if not os.path.isdir(full):
            continue
        for f in os.listdir(full):
            if f.endswith(".py") and not f.startswith("__"):
                mod_name = f[:-3]
                test_path = os.path.join(project_root, "data", "generated_tests", f"test_{mod_name}.py")
                if not os.path.exists(test_path):
                    candidates.append((d, f, os.path.join(full, f)))

    if not candidates:
        _mark_run("test_generation")
        return {"skipped": True, "reason": "all_modules_covered"}

    dir_name, file_name, file_path = random.choice(candidates)
    mod_name = file_name[:-3]

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
    except IOError:
        _mark_run("test_generation")
        return {"skipped": True, "reason": "read_error"}

    if len(code) > 5000:
        code = code[:5000] + "\n# ... (truncated)"

    prompt = (
        f"Generate pytest test cases for this module: {dir_name}/{file_name}\n\n"
        f"```python\n{code}\n```\n\n"
        "Requirements:\n"
        "- Focus on edge cases, error paths, and boundary conditions\n"
        "- Use mocking for external dependencies (LLM calls, file I/O)\n"
        "- Each test should be self-contained\n"
        "- Include descriptive test names\n\n"
        "Output ONLY the Python test file content, no explanation."
    )

    try:
        test_code = router.get_content("reasoning", [{"role": "user", "content": prompt}]).strip()
    except Exception as e:
        _mark_run("test_generation")
        return {"error": str(e)}

    # Clean up markdown fences if present
    if test_code.startswith("```"):
        lines = test_code.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        test_code = "\n".join(lines)

    test_dir = os.path.join(project_root, "data", "generated_tests")
    test_path = os.path.join(test_dir, f"test_{mod_name}.py")
    os.makedirs(test_dir, exist_ok=True)
    with open(test_path, "w", encoding="utf-8") as f:
        f.write(test_code)

    _mark_run("test_generation")
    _log.info(f"Generated tests for {dir_name}/{file_name} → {test_path}")
    return {
        "module": f"{dir_name}/{file_name}",
        "test_file": test_path,
        "test_lines": test_code.count("\n") + 1,
    }
