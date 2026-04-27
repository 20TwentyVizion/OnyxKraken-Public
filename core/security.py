"""Public stub of core.security -- anti-tamper logic is private build only."""
from __future__ import annotations


class _OpenTrialManager:
    """No-op trial manager. The public build has no trial gating."""
    def is_trial_active(self) -> bool: return False
    def days_remaining(self) -> int: return 365
    def record_session(self) -> None: ...


_TRIAL = _OpenTrialManager()


def get_trial_manager() -> _OpenTrialManager:
    return _TRIAL
