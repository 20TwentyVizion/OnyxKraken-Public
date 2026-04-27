"""Metrics collection and reporting for benchmark runs."""

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

_log = logging.getLogger("eval.metrics")


@dataclass
class TaskMetrics:
    """Metrics for a single task run."""
    task_id: str
    goal: str
    app_name: str
    steps_planned: int = 0
    steps_completed: int = 0
    total_actions: int = 0
    total_time: float = 0.0
    aborted: bool = False
    failure_reason: str = ""
    verifier_results: list = field(default_factory=list)  # [{name, passed, detail}]

    @property
    def passed(self) -> bool:
        return all(v["passed"] for v in self.verifier_results)

    @property
    def verifiers_passed(self) -> int:
        return sum(1 for v in self.verifier_results if v["passed"])

    @property
    def verifiers_total(self) -> int:
        return len(self.verifier_results)


@dataclass
class BenchmarkReport:
    """Aggregate report for a full benchmark run."""
    timestamp: str = ""
    tasks_total: int = 0
    tasks_passed: int = 0
    tasks_failed: int = 0
    tasks_skipped: int = 0
    total_time: float = 0.0
    total_actions: int = 0
    task_results: list = field(default_factory=list)  # list of TaskMetrics dicts
    config_snapshot: dict = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        if self.tasks_total == 0:
            return 0.0
        return self.tasks_passed / self.tasks_total

    def summary(self) -> str:
        lines = [
            f"{'='*60}",
            f"  BENCHMARK REPORT — {self.timestamp}",
            f"{'='*60}",
            f"  Tasks: {self.tasks_passed}/{self.tasks_total} passed "
            f"({self.pass_rate:.0%})",
            f"  Failed: {self.tasks_failed} | Skipped: {self.tasks_skipped}",
            f"  Total time: {self.total_time:.1f}s | Total actions: {self.total_actions}",
            f"{'='*60}",
        ]

        for tr in self.task_results:
            status = "✅" if tr["passed"] else "❌"
            lines.append(
                f"  {status} {tr['task_id']}: {tr['goal'][:50]}"
                f"  ({tr['total_time']:.1f}s, {tr['total_actions']} actions)"
            )
            for v in tr.get("verifier_results", []):
                v_icon = "  ✓" if v["passed"] else "  ✗"
                lines.append(f"      {v_icon} {v['name']}: {v['detail']}")

        lines.append(f"{'='*60}")
        return "\n".join(lines)

    def save(self, path: str):
        """Save report as JSON."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, default=str)

    @classmethod
    def load(cls, path: str) -> "BenchmarkReport":
        """Load a saved report."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)
