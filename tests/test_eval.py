"""Quick test that the eval harness loads and compiles."""

import config
from log import setup_logging
setup_logging(config.LOG_LEVEL)

from eval.benchmark import load_tasks
from eval.verifiers import build_verifiers

tasks = load_tasks()
print(f"{len(tasks)} tasks loaded:")
for t in tasks:
    verifiers = build_verifiers(t.get("verifiers", []))
    print(f"  {t['id']}: {t['goal'][:55]}  ({len(verifiers)} verifiers)")

print("\nAll verifiers built successfully.")
print("Eval harness ready.")
