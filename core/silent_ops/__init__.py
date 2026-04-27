"""Silent Operations — background tasks that improve OnyxKraken without opening any windows.

All operations here are pure computation: LLM calls, file I/O, JSON manipulation.
No pyautogui, no pywinauto, no GUI interaction.

Operations:
  S1 — Knowledge consolidation: merge duplicates, prune stale entries
  S2 — Prompt optimization: analyze task patterns for better prompts
  S3 — Benchmark regression analysis: detect trends across saved reports
  S4 — Memory compaction: summarize old task history
  S5 — Code self-review: LLM reviews random source files
  S6 — Error pattern mining: cluster failures, suggest fixes
  S7 — Daily digest: summarize daily learning and progress
  S8 — Test generation: generate pytest tests for untested modules

Each function:
  - Takes _extract_json and _mark_run as arguments (injected by dispatcher)
  - Returns a summary dict
  - Handles its own errors
  - Is safe to call from the autonomy daemon loop
"""

import json
import time
from typing import Optional

from log import get_logger

from .s1_knowledge import knowledge_consolidation
from .s2_prompts import prompt_optimization
from .s3_benchmark import benchmark_analysis
from .s4_memory import memory_compaction
from .s5_code_review import code_self_review
from .s6_error_mining import error_pattern_mining
from .s7_digest import daily_digest
from .s8_test_gen import test_generation

_log = get_logger("silent_ops")

# Cooldown tracking (per-operation, in seconds)
_cooldowns: dict[str, float] = {}
_last_run: dict[str, float] = {}

COOLDOWNS = {
    "knowledge_consolidation": 1800,   # 30 min
    "benchmark_analysis": 7200,        # 2 hours
    "prompt_optimization": 3600,       # 1 hour
    "error_pattern_mining": 1800,      # 30 min
    "memory_compaction": 86400,        # 24 hours
    "code_self_review": 2700,          # 45 min
    "daily_digest": 86400,             # 24 hours
    "test_generation": 7200,           # 2 hours
}


def _can_run(op_name: str) -> bool:
    """Check if an operation's cooldown has elapsed."""
    cooldown = COOLDOWNS.get(op_name, 600)
    last = _last_run.get(op_name, 0)
    return (time.time() - last) >= cooldown


def _mark_run(op_name: str):
    """Record that an operation just ran."""
    _last_run[op_name] = time.time()


from core.utils import extract_json as _extract_json  # shared utility


# ---------------------------------------------------------------------------
# Dispatcher — called by the autonomy daemon
# ---------------------------------------------------------------------------

# Ordered by priority — each entry is (name, callable)
_OPERATIONS = [
    ("knowledge_consolidation", knowledge_consolidation),
    ("benchmark_analysis", benchmark_analysis),
    ("prompt_optimization", prompt_optimization),
    ("error_pattern_mining", error_pattern_mining),
    ("memory_compaction", memory_compaction),
    ("code_self_review", code_self_review),
    ("daily_digest", daily_digest),
    ("test_generation", test_generation),
]


def run_next_silent_op() -> Optional[dict]:
    """Run the highest-priority silent operation whose cooldown has elapsed.

    Returns the operation summary, or None if nothing was eligible.
    """
    for op_name, op_fn in _OPERATIONS:
        if _can_run(op_name):
            _log.info(f"Running silent op: {op_name}")
            try:
                result = op_fn(_extract_json, _mark_run)
                result["operation"] = op_name
                return result
            except Exception as e:
                _log.error(f"Silent op '{op_name}' failed: {e}")
                _mark_run(op_name)  # still mark to avoid spam on repeated failures
                return {"operation": op_name, "error": str(e)}

    return None
