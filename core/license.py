"""Public stub of core.license.

The full license-enforcement logic lives in the private build of OnyxKraken.
This stub exposes just enough of the public API for the rest of the open
codebase to import and run without restrictions. Treat the public build as
the open-source-evaluation tier described in LICENSE (BSL-1.1).
"""
from __future__ import annotations
from typing import Any


class _OpenDemoTracker:
    """No-op tracker. Public build has no demo limits."""
    def record_task(self) -> None: ...
    def remaining(self) -> int: return 1_000_000
    @property
    def is_demo(self) -> bool: return False


_TRACKER = _OpenDemoTracker()


def get_demo_tracker() -> _OpenDemoTracker:
    return _TRACKER


def get_license_type() -> str:
    return "open"


def get_license() -> dict[str, Any]:
    return {"type": "open", "valid": True, "tier": "evaluation"}


def get_session() -> dict[str, Any]:
    return {"tasks_run": 0, "tier": "open"}


def is_app_allowed(_app_name: str) -> bool:
    return True


def activate_license(_key: str) -> bool:
    return True


def generate_key(*_args, **_kwargs) -> str:
    return "OPEN-BUILD-NO-KEY-REQUIRED"
