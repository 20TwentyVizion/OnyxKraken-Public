"""Base skill framework — protocol, registry, and confidence tracking.

A Skill is a high-level capability that combines LLM reasoning, app modules,
APIs, and tools into a coherent pipeline. Skills self-register and track
their own performance metrics (confidence, usage, success rate).
"""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
# REMOVED (unused): from typing import Any, Dict, List, Optional, Protocol

_log = logging.getLogger("core.skills")

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SKILLS_DB = os.path.join(_ROOT, "data", "skills.json")


# ---------------------------------------------------------------------------
# Skill Protocol
# ---------------------------------------------------------------------------

class Skill(ABC):
    """Abstract base for all Onyx skills."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill identifier (e.g. 'content_creation')."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """What this skill can do."""
        ...

    @property
    def category(self) -> str:
        """Skill category (e.g. 'creative', 'technical', 'business')."""
        return "general"

    @property
    def capabilities(self) -> List[str]:
        """List of specific things this skill can do."""
        return []

    @property
    def required_modules(self) -> List[str]:
        """App module names this skill depends on."""
        return []

    @property
    def required_tokens(self) -> List[str]:
        """Environment variable names for API tokens this skill needs."""
        return []

    def check_readiness(self) -> Dict[str, Any]:
        """Check if all dependencies are available.

        Returns:
            Dict with 'ready': bool, 'missing': list of missing deps.
        """
        missing = []
        for token_name in self.required_tokens:
            if not os.environ.get(token_name):
                missing.append(f"env:{token_name}")
        return {"ready": len(missing) == 0, "missing": missing}

    @abstractmethod
    def execute(self, action: str, params: Optional[Dict] = None) -> Dict:
        """Execute a skill action.

        Args:
            action: The specific action to perform.
            params: Action parameters.

        Returns:
            Result dict with 'ok', 'data', and optionally 'error'.
        """
        ...

    def get_actions(self) -> List[Dict]:
        """List available actions for this skill."""
        return []


# ---------------------------------------------------------------------------
# Skill Metrics
# ---------------------------------------------------------------------------

@dataclass
class SkillMetrics:
    """Performance metrics for a skill."""
    name: str
    total_uses: int = 0
    successes: int = 0
    failures: int = 0
    last_used: float = 0.0
    confidence: float = 0.5  # 0.0 to 1.0
    avg_duration_s: float = 0.0
    total_duration_s: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_uses == 0:
            return 0.0
        return self.successes / self.total_uses

    def record_use(self, success: bool, duration_s: float = 0.0):
        """Record a skill usage."""
        self.total_uses += 1
        if success:
            self.successes += 1
        else:
            self.failures += 1
        self.last_used = time.time()
        self.total_duration_s += duration_s
        if self.total_uses > 0:
            self.avg_duration_s = self.total_duration_s / self.total_uses

        # Update confidence based on recent performance (exponential moving average)
        alpha = 0.3  # weight of new observation
        observation = 1.0 if success else 0.0
        self.confidence = alpha * observation + (1 - alpha) * self.confidence


# ---------------------------------------------------------------------------
# Skill Registry
# ---------------------------------------------------------------------------

class SkillRegistry:
    """Global registry of all Onyx skills with persistence."""

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._metrics: Dict[str, SkillMetrics] = {}
        self._load_metrics()

    def register(self, skill: Skill) -> None:
        """Register a skill instance."""
        self._skills[skill.name] = skill
        if skill.name not in self._metrics:
            self._metrics[skill.name] = SkillMetrics(name=skill.name)
        _log.info("Registered skill: %s (%s)", skill.name, skill.display_name)

    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> List[Dict]:
        """List all skills with their metrics."""
        result = []
        for name, skill in self._skills.items():
            metrics = self._metrics.get(name, SkillMetrics(name=name))
            readiness = skill.check_readiness()
            result.append({
                "name": skill.name,
                "display_name": skill.display_name,
                "description": skill.description,
                "category": skill.category,
                "capabilities": skill.capabilities,
                "ready": readiness["ready"],
                "missing": readiness.get("missing", []),
                "confidence": metrics.confidence,
                "success_rate": metrics.success_rate,
                "total_uses": metrics.total_uses,
                "last_used": metrics.last_used,
            })
        return result

    def record_use(self, skill_name: str, success: bool, duration_s: float = 0.0):
        """Record a skill usage for metrics tracking."""
        if skill_name not in self._metrics:
            self._metrics[skill_name] = SkillMetrics(name=skill_name)
        self._metrics[skill_name].record_use(success, duration_s)
        self._save_metrics()

    def get_metrics(self, skill_name: str) -> Optional[SkillMetrics]:
        return self._metrics.get(skill_name)

    # -- Persistence --

    def _load_metrics(self):
        """Load metrics from disk."""
        if os.path.exists(_SKILLS_DB):
            try:
                with open(_SKILLS_DB, "r") as f:
                    data = json.load(f)
                for entry in data.get("metrics", []):
                    m = SkillMetrics(**entry)
                    self._metrics[m.name] = m
            except Exception as e:
                _log.warning("Failed to load skills metrics: %s", e)

    def _save_metrics(self):
        """Persist metrics to disk."""
        os.makedirs(os.path.dirname(_SKILLS_DB), exist_ok=True)
        data = {
            "metrics": [asdict(m) for m in self._metrics.values()],
            "last_saved": time.time(),
        }
        try:
            with open(_SKILLS_DB, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            _log.warning("Failed to save skills metrics: %s", e)


# Singleton (delegates to service registry)

def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry singleton."""
    from core.service_registry import services
    if not services.has("skill_registry"):
        services.register_factory("skill_registry", SkillRegistry)
    return services.get("skill_registry", SkillRegistry)
