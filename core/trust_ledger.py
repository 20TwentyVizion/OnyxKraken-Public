"""Earned Autonomy — per-domain trust scores (neuroscience rule #5).

Trust expands through demonstrated competence and contracts on failures.
Each domain (e.g. "blender", "chrome", "notepad") has an independent
trust score from 0-100 that determines what autonomy level the agent
is allowed in that domain.

Trust levels:
  0-19  RESTRICTED — only pre-approved actions, human confirmation required
  20-39 CAUTIOUS   — common actions allowed, risky ones need confirmation
  40-59 STANDARD   — most actions allowed, only destructive ones gated
  60-79 TRUSTED    — full autonomy, occasional spot-checks
  80-100 AUTONOMOUS — full autonomy, no gates

Score changes:
  +3  per successful task
  -8  per failed task   (failures penalised harder — conservative by design)
  +1  bonus for streaks of 5+ successes
  -15 if a safety violation is detected
"""

import json
import logging
import os
import time
import threading
from enum import StrEnum

_log = logging.getLogger("trust")

_TRUST_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "trust_ledger.json"
)


class TrustLevel(StrEnum):
    RESTRICTED = "restricted"
    CAUTIOUS = "cautious"
    STANDARD = "standard"
    TRUSTED = "trusted"
    AUTONOMOUS = "autonomous"


# Score thresholds (inclusive lower bounds)
_LEVEL_THRESHOLDS = [
    (80, TrustLevel.AUTONOMOUS),
    (60, TrustLevel.TRUSTED),
    (40, TrustLevel.STANDARD),
    (20, TrustLevel.CAUTIOUS),
    (0,  TrustLevel.RESTRICTED),
]

# Score deltas
_SUCCESS_DELTA = 3
_FAILURE_DELTA = -8
_STREAK_BONUS = 1        # added on top when streak >= 5
_SAFETY_VIOLATION = -15
_INITIAL_SCORE = 25       # new domains start at CAUTIOUS


class TrustLedger:
    """Persistent per-domain trust ledger with event history."""

    def __init__(self, path: str = _TRUST_FILE):
        self._path = path
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                _log.warning(f"Trust ledger load failed: {e}")
        return {"domains": {}, "events": []}

    def _save(self):
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, default=str)
            os.replace(tmp, self._path)
        except OSError as e:
            _log.warning(f"Trust ledger save failed: {e}")

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    def _ensure_domain(self, domain: str) -> dict:
        domain = domain.lower().strip()
        if domain not in self._data["domains"]:
            self._data["domains"][domain] = {
                "score": _INITIAL_SCORE,
                "streak": 0,
                "total_successes": 0,
                "total_failures": 0,
                "created_at": time.time(),
                "last_updated": time.time(),
            }
        return self._data["domains"][domain]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_success(self, domain: str, goal: str = ""):
        """Record a successful task in *domain*."""
        with self._lock:
            d = self._ensure_domain(domain)
            delta = _SUCCESS_DELTA
            d["streak"] = max(0, d["streak"]) + 1
            if d["streak"] >= 5:
                delta += _STREAK_BONUS
            d["score"] = min(100, d["score"] + delta)
            d["total_successes"] += 1
            d["last_updated"] = time.time()
            self._record_event(domain, "success", delta, goal)
            self._save()
            _log.debug(f"Trust[{domain}] +{delta} → {d['score']} "
                        f"(streak {d['streak']})")

    def record_failure(self, domain: str, goal: str = ""):
        """Record a failed task in *domain*."""
        with self._lock:
            d = self._ensure_domain(domain)
            d["streak"] = min(0, d.get("streak", 0)) - 1
            d["score"] = max(0, d["score"] + _FAILURE_DELTA)
            d["total_failures"] += 1
            d["last_updated"] = time.time()
            self._record_event(domain, "failure", _FAILURE_DELTA, goal)
            self._save()
            _log.debug(f"Trust[{domain}] {_FAILURE_DELTA} → {d['score']}")

    def record_safety_violation(self, domain: str, detail: str = ""):
        """Record a safety violation — large penalty."""
        with self._lock:
            d = self._ensure_domain(domain)
            d["streak"] = 0
            d["score"] = max(0, d["score"] + _SAFETY_VIOLATION)
            d["last_updated"] = time.time()
            self._record_event(domain, "safety_violation", _SAFETY_VIOLATION, detail)
            self._save()
            _log.warning(f"Trust[{domain}] SAFETY VIOLATION {_SAFETY_VIOLATION} → {d['score']}")

    def get_score(self, domain: str) -> int:
        with self._lock:
            d = self._ensure_domain(domain)
            return d["score"]

    def get_level(self, domain: str) -> TrustLevel:
        score = self.get_score(domain)
        for threshold, level in _LEVEL_THRESHOLDS:
            if score >= threshold:
                return level
        return TrustLevel.RESTRICTED

    def is_allowed(self, domain: str, min_level: TrustLevel = TrustLevel.STANDARD) -> bool:
        """Check whether current trust in *domain* meets *min_level*."""
        current = self.get_level(domain)
        current_idx = [lv for _, lv in _LEVEL_THRESHOLDS].index(current)
        required_idx = [lv for _, lv in _LEVEL_THRESHOLDS].index(min_level)
        return current_idx <= required_idx  # lower index = higher trust

    def get_all_domains(self) -> dict:
        """Return {domain: {score, level, streak, ...}} for all known domains."""
        with self._lock:
            result = {}
            for domain, d in self._data["domains"].items():
                result[domain] = {
                    **d,
                    "level": self.get_level(domain).value,
                }
            return result

    def get_stats(self) -> dict:
        domains = self.get_all_domains()
        return {
            "total_domains": len(domains),
            "domains": domains,
            "total_events": len(self._data.get("events", [])),
        }

    # ------------------------------------------------------------------
    # Event log (capped at 200 entries)
    # ------------------------------------------------------------------

    def _record_event(self, domain: str, event_type: str, delta: int, detail: str):
        self._data.setdefault("events", []).append({
            "domain": domain,
            "type": event_type,
            "delta": delta,
            "detail": detail[:200] if detail else "",
            "timestamp": time.time(),
        })
        if len(self._data["events"]) > 200:
            self._data["events"] = self._data["events"][-200:]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def get_trust_ledger() -> TrustLedger:
    from core.service_registry import services
    if not services.has("trust_ledger"):
        services.register_factory("trust_ledger", TrustLedger)
    return services.get("trust_ledger", TrustLedger)
