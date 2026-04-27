"""Prediction-Error Learning — update beliefs only when surprised (neuroscience rule #4).

Before executing a goal the agent predicts:
  - probability of success (0-1)
  - estimated duration (seconds)
  - expected difficulty ("easy", "medium", "hard")

After execution the outcome is compared.  When the prediction error
exceeds a configurable threshold the agent logs a *surprise event* and
triggers a belief update — otherwise the outcome is routine and beliefs
stay unchanged.

This mirrors dopaminergic prediction-error signalling: expected rewards
don't cause learning, only *unexpected* outcomes do.
"""

import json
import logging
import math
import os
import time
import threading
from dataclasses import dataclass, asdict
from typing import Optional

_log = logging.getLogger("prediction")

_PREDICTIONS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "predictions.json"
)

# Surprise threshold — prediction errors above this trigger belief updates
SURPRISE_THRESHOLD = 0.35


@dataclass
class Prediction:
    """A pre-execution prediction."""
    goal: str
    domain: str
    predicted_success: float      # 0-1 probability
    predicted_duration: float     # seconds
    predicted_difficulty: str     # easy / medium / hard
    timestamp: float = 0.0
    id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"pred_{int(self.timestamp * 1000)}"
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class PredictionOutcome:
    """Result of comparing prediction vs reality."""
    prediction_id: str
    actual_success: bool
    actual_duration: float
    success_error: float          # |predicted - actual| for success
    duration_error: float         # relative error for duration
    surprise_score: float         # combined error (0-1)
    is_surprise: bool             # surprise_score > threshold
    lesson: str                   # what was learned (if surprise)


class PredictionEngine:
    """Manages prediction→outcome→surprise→learning loop."""

    def __init__(self, path: str = _PREDICTIONS_FILE):
        self._path = path
        self._lock = threading.Lock()
        self._data = self._load()
        self._pending: dict[str, Prediction] = {}

    def _load(self) -> dict:
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "beliefs": {},        # domain -> {expected_success_rate, avg_duration}
            "surprises": [],      # list of surprise events
            "total_predictions": 0,
            "total_surprises": 0,
        }

    def _save(self):
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, default=str)
            os.replace(tmp, self._path)
        except OSError as e:
            _log.warning(f"Prediction save failed: {e}")

    # ------------------------------------------------------------------
    # Prediction generation
    # ------------------------------------------------------------------

    def predict(self, goal: str, domain: str = "general") -> Prediction:
        """Generate a prediction for a goal based on current beliefs.

        Uses domain-level beliefs (rolling averages from past outcomes)
        to estimate success probability and duration.
        """
        beliefs = self._data["beliefs"].get(domain, {})
        pred = Prediction(
            goal=goal[:200],
            domain=domain,
            predicted_success=beliefs.get("expected_success_rate", 0.5),
            predicted_duration=beliefs.get("avg_duration", 30.0),
            predicted_difficulty=self._infer_difficulty(
                beliefs.get("expected_success_rate", 0.5)
            ),
        )
        with self._lock:
            self._pending[pred.id] = pred
            self._data["total_predictions"] += 1
        _log.debug(f"Prediction [{pred.id}]: p(success)={pred.predicted_success:.2f}, "
                    f"est_duration={pred.predicted_duration:.0f}s, "
                    f"difficulty={pred.predicted_difficulty}")
        return pred

    # ------------------------------------------------------------------
    # Outcome comparison
    # ------------------------------------------------------------------

    def record_outcome(self, prediction_id: str, actual_success: bool,
                       actual_duration: float) -> PredictionOutcome:
        """Compare prediction vs actual outcome and detect surprise."""
        with self._lock:
            pred = self._pending.pop(prediction_id, None)

        if pred is None:
            # No matching prediction — create a minimal outcome
            return PredictionOutcome(
                prediction_id=prediction_id,
                actual_success=actual_success,
                actual_duration=actual_duration,
                success_error=0.0,
                duration_error=0.0,
                surprise_score=0.0,
                is_surprise=False,
                lesson="",
            )

        # Success error: |predicted_prob - actual_binary|
        actual_val = 1.0 if actual_success else 0.0
        success_error = abs(pred.predicted_success - actual_val)

        # Duration error: relative difference (capped at 1.0)
        if pred.predicted_duration > 0:
            duration_error = min(1.0, abs(actual_duration - pred.predicted_duration)
                                 / pred.predicted_duration)
        else:
            duration_error = 0.0

        # Combined surprise score (success matters more)
        surprise_score = success_error * 0.7 + duration_error * 0.3
        is_surprise = surprise_score > SURPRISE_THRESHOLD

        lesson = ""
        if is_surprise:
            if actual_success and pred.predicted_success < 0.5:
                lesson = f"Unexpectedly succeeded in '{pred.domain}' — raise confidence"
            elif not actual_success and pred.predicted_success >= 0.5:
                lesson = f"Unexpectedly failed in '{pred.domain}' — investigate weakness"
            elif duration_error > 0.5:
                direction = "slower" if actual_duration > pred.predicted_duration else "faster"
                lesson = f"Task was {direction} than expected in '{pred.domain}'"

            self._record_surprise(pred, actual_success, actual_duration,
                                  surprise_score, lesson)

        # Update beliefs (exponential moving average)
        self._update_beliefs(pred.domain, actual_success, actual_duration)

        outcome = PredictionOutcome(
            prediction_id=prediction_id,
            actual_success=actual_success,
            actual_duration=actual_duration,
            success_error=round(success_error, 3),
            duration_error=round(duration_error, 3),
            surprise_score=round(surprise_score, 3),
            is_surprise=is_surprise,
            lesson=lesson,
        )

        if is_surprise:
            _log.info(f"SURPRISE [{prediction_id}]: score={surprise_score:.2f} — {lesson}")
        else:
            _log.debug(f"Expected outcome [{prediction_id}]: score={surprise_score:.2f}")

        return outcome

    # ------------------------------------------------------------------
    # Belief updates
    # ------------------------------------------------------------------

    def _update_beliefs(self, domain: str, success: bool, duration: float,
                        alpha: float = 0.2):
        """Exponential moving average update of domain beliefs.

        alpha controls learning rate: higher = faster adaptation.
        """
        with self._lock:
            beliefs = self._data["beliefs"].setdefault(domain, {
                "expected_success_rate": 0.5,
                "avg_duration": 30.0,
                "sample_count": 0,
            })
            actual_s = 1.0 if success else 0.0
            beliefs["expected_success_rate"] = (
                (1 - alpha) * beliefs["expected_success_rate"] + alpha * actual_s
            )
            if duration > 0:
                beliefs["avg_duration"] = (
                    (1 - alpha) * beliefs["avg_duration"] + alpha * duration
                )
            beliefs["sample_count"] = beliefs.get("sample_count", 0) + 1
            self._save()

    def _record_surprise(self, pred: Prediction, actual_success: bool,
                         actual_duration: float, score: float, lesson: str):
        with self._lock:
            self._data["surprises"].append({
                "prediction_id": pred.id,
                "goal": pred.goal[:120],
                "domain": pred.domain,
                "predicted_success": pred.predicted_success,
                "actual_success": actual_success,
                "predicted_duration": pred.predicted_duration,
                "actual_duration": actual_duration,
                "surprise_score": round(score, 3),
                "lesson": lesson,
                "timestamp": time.time(),
            })
            # Cap at 100 surprise events
            if len(self._data["surprises"]) > 100:
                self._data["surprises"] = self._data["surprises"][-100:]
            self._data["total_surprises"] += 1
            self._save()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_difficulty(success_rate: float) -> str:
        if success_rate >= 0.7:
            return "easy"
        elif success_rate >= 0.4:
            return "medium"
        return "hard"

    def get_beliefs(self) -> dict:
        with self._lock:
            return dict(self._data.get("beliefs", {}))

    def get_recent_surprises(self, limit: int = 10) -> list[dict]:
        with self._lock:
            return self._data.get("surprises", [])[-limit:]

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_predictions": self._data["total_predictions"],
                "total_surprises": self._data["total_surprises"],
                "domains_tracked": len(self._data["beliefs"]),
                "beliefs": self._data["beliefs"],
                "pending_predictions": len(self._pending),
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def get_prediction_engine() -> PredictionEngine:
    from core.service_registry import services
    if not services.has("prediction_engine"):
        services.register_factory("prediction_engine", PredictionEngine)
    return services.get("prediction_engine", PredictionEngine)
