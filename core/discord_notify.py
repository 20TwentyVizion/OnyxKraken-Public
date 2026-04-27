"""Public stub of core.discord_notify -- no Discord webhook in the open build."""
from __future__ import annotations


def _noop(*_args, **_kwargs) -> None:
    pass


notify_task_complete = _noop
notify_task_failed = _noop
notify_improvement = _noop
notify_daemon_event = _noop
notify_bbt_briefing = _noop
notify_bbt_commitment_reminder = _noop
