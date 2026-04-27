"""Quick test of the planner with cloud model + fallback."""

import config
from log import setup_logging
setup_logging(config.LOG_LEVEL)

from apps.registry import discover_modules
discover_modules()

from agent.orchestrator import decompose_goal

goal = "Open Grok and ask it what the best approach to building an autonomous AI agent is"
print(f"Goal: {goal}\n")

steps = decompose_goal(goal)

print("\n=== PLAN RESULTS ===")
for i, s in enumerate(steps, 1):
    print(f"  {i}. {s['description']}  [{s['type']}]")
print()
