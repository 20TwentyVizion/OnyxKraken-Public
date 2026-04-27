"""Pipeline Orchestrator — "Onyx's Hands."

Chains components in sequence. Each step feeds into the next.
Handles sequencing, error recovery, status reporting.

Usage:
    from core.components.pipeline import Pipeline, PipelineStep

    pipe = Pipeline("render_and_upload", [
        PipelineStep("blender", "build_scene", {"description": "a robot cat"}),
        PipelineStep("blender", "render", {"output": "cat.mp4"}),
        PipelineStep("music", "generate_track", {"mood": "playful"}),
        PipelineStep("video_edit", "combine", {}),  # reads chain_data from prev steps
        PipelineStep("youtube", "upload", {"title": "Onyx Builds a Robot Cat"}),
    ])
    result = pipe.run()

Chain data:
    Each step's ComponentResult.chain_data is merged into a shared context dict.
    Subsequent steps can access outputs from earlier steps via this context.
    Example: Blender renders to "cat.mp4" → chain_data={"video_path": "cat.mp4"}
             Music generates "track.wav" → chain_data={"audio_path": "track.wav"}
             Video edit reads both from the pipeline context.
"""

import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

from core.components.base import ComponentResult

_log = logging.getLogger("core.components.pipeline")


# ---------------------------------------------------------------------------
# Pipeline step
# ---------------------------------------------------------------------------

@dataclass
class PipelineStep:
    """A single step in a pipeline."""
    component: str          # component name (e.g. "blender")
    action: str             # action name (e.g. "build_scene")
    params: Dict = field(default_factory=dict)
    # Optional: override params with values from chain context
    # e.g. {"video_path": "blender.artifact_path"} would inject
    # the artifact_path from the blender step into video_path param
    param_mapping: Dict = field(default_factory=dict)
    # If True, pipeline continues even if this step fails
    optional: bool = False
    # Human-readable description
    description: str = ""
    # Condition: skip this step if a chain_data key is falsy
    skip_if_missing: str = ""

    def __post_init__(self):
        if not self.description:
            self.description = f"{self.component}.{self.action}"


# ---------------------------------------------------------------------------
# Step result
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    """Result of a single pipeline step."""
    step_index: int
    component: str
    action: str
    description: str
    result: ComponentResult
    skipped: bool = False
    duration: float = 0.0

    @property
    def ok(self) -> bool:
        return self.skipped or self.result.ok


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Result of a complete pipeline execution."""
    pipeline_name: str
    steps: List[StepResult] = field(default_factory=list)
    chain_data: Dict = field(default_factory=dict)
    total_duration: float = 0.0
    completed: bool = False
    failed_at: int = -1         # index of first failed step, -1 if none
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.completed and self.failed_at == -1

    @property
    def summary(self) -> str:
        total = len(self.steps)
        done = sum(1 for s in self.steps if s.ok)
        if self.ok:
            return f"Pipeline '{self.pipeline_name}' completed: {done}/{total} steps in {self.total_duration:.1f}s"
        return f"Pipeline '{self.pipeline_name}' failed at step {self.failed_at + 1}/{total}: {self.error}"

    def to_dict(self) -> Dict:
        return {
            "pipeline_name": self.pipeline_name,
            "ok": self.ok,
            "completed": self.completed,
            "total_duration": round(self.total_duration, 2),
            "failed_at": self.failed_at,
            "error": self.error,
            "chain_data": self.chain_data,
            "steps": [
                {
                    "index": s.step_index,
                    "component": s.component,
                    "action": s.action,
                    "description": s.description,
                    "ok": s.ok,
                    "skipped": s.skipped,
                    "duration": round(s.duration, 2),
                    "error": s.result.error if not s.skipped else "",
                    "summary": s.result.summary if not s.skipped else "skipped",
                }
                for s in self.steps
            ],
        }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Pipeline:
    """Chains Onyx components in sequence.

    Each step's output feeds into the next via shared chain_data.
    If a step fails (and isn't optional), the pipeline stops.
    """

    def __init__(self, name: str, steps: List[PipelineStep],
                 on_step_complete: Optional[Callable] = None,
                 on_step_failed: Optional[Callable] = None,
                 dry_run: bool = False):
        """
        Args:
            name: Pipeline identifier (for logging/tracking).
            steps: Ordered list of PipelineSteps.
            on_step_complete: Callback(step_index, StepResult) after each step.
            on_step_failed: Callback(step_index, StepResult) on failure.
            dry_run: If True, validate the pipeline without executing.
        """
        self.name = name
        self.steps = steps
        self._on_complete = on_step_complete
        self._on_failed = on_step_failed
        self._dry_run = dry_run

    def validate(self) -> Dict:
        """Check that all referenced components and actions exist.

        Returns:
            {"valid": bool, "issues": [...]}
        """
        from core.components.registry import component_registry

        issues = []
        for i, step in enumerate(self.steps):
            comp = component_registry.get(step.component)
            if comp is None:
                issues.append(f"Step {i}: component '{step.component}' not found")
                continue
            action_names = [a.name for a in comp.get_actions()]
            if step.action not in action_names:
                issues.append(
                    f"Step {i}: component '{step.component}' has no action "
                    f"'{step.action}' (available: {action_names})"
                )
        return {"valid": len(issues) == 0, "issues": issues}

    def run(self) -> PipelineResult:
        """Execute the pipeline, step by step.

        Returns PipelineResult with full execution trace.
        """
        from core.components.registry import component_registry

        result = PipelineResult(pipeline_name=self.name)
        chain_data: Dict[str, Any] = {}
        start = time.time()

        _log.info("Pipeline '%s' starting (%d steps)", self.name, len(self.steps))

        for i, step in enumerate(self.steps):
            # Check skip condition
            if step.skip_if_missing and not chain_data.get(step.skip_if_missing):
                sr = StepResult(
                    step_index=i,
                    component=step.component,
                    action=step.action,
                    description=step.description,
                    result=ComponentResult(status="skipped",
                                          summary=f"Skipped: '{step.skip_if_missing}' not in context"),
                    skipped=True,
                )
                result.steps.append(sr)
                _log.info("  Step %d/%d SKIPPED: %s", i + 1, len(self.steps),
                          step.description)
                continue

            # Resolve param mappings from chain_data
            resolved_params = dict(step.params)
            for param_key, chain_key in step.param_mapping.items():
                if chain_key in chain_data:
                    resolved_params[param_key] = chain_data[chain_key]

            # Inject full chain context so components can access it
            resolved_params["_chain_data"] = chain_data

            if self._dry_run:
                sr = StepResult(
                    step_index=i,
                    component=step.component,
                    action=step.action,
                    description=step.description,
                    result=ComponentResult(status="done",
                                          summary=f"[DRY RUN] {step.description}"),
                )
                result.steps.append(sr)
                continue

            # Execute
            _log.info("  Step %d/%d: %s", i + 1, len(self.steps), step.description)
            step_start = time.time()

            comp_result = component_registry.run(
                step.component, step.action, resolved_params
            )

            step_duration = time.time() - step_start

            sr = StepResult(
                step_index=i,
                component=step.component,
                action=step.action,
                description=step.description,
                result=comp_result,
                duration=step_duration,
            )
            result.steps.append(sr)

            # Merge chain data from this step
            if comp_result.chain_data:
                chain_data.update(comp_result.chain_data)
            # Also store artifact info under component name
            if comp_result.artifact_path:
                chain_data[f"{step.component}_artifact"] = comp_result.artifact_path
                chain_data[f"{step.component}_artifact_type"] = comp_result.artifact_type

            # Callbacks
            if comp_result.ok:
                _log.info("    DONE (%.1fs): %s", step_duration,
                          comp_result.summary or "ok")
                if self._on_complete:
                    try:
                        self._on_complete(i, sr)
                    except Exception:
                        pass
            else:
                _log.warning("    FAILED (%.1fs): %s", step_duration,
                             comp_result.error or comp_result.summary)
                if self._on_failed:
                    try:
                        self._on_failed(i, sr)
                    except Exception:
                        pass

                if not step.optional:
                    result.failed_at = i
                    result.error = comp_result.error or f"Step {i} failed"
                    break

        result.chain_data = chain_data
        result.total_duration = time.time() - start
        result.completed = result.failed_at == -1

        status = "completed" if result.ok else f"failed at step {result.failed_at + 1}"
        _log.info("Pipeline '%s' %s in %.1fs",
                  self.name, status, result.total_duration)

        return result

    def __repr__(self) -> str:
        return f"<Pipeline '{self.name}' [{len(self.steps)} steps]>"
