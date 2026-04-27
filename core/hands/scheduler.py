"""Hand Scheduler — manages activation, scheduling, and execution of Hands.

Runs as a background thread, checking each active Hand's schedule
and executing it when due. Integrates with telemetry for tracking
and SystemHealth for pre-flight checks.

Usage:
    from core.hands.scheduler import HandScheduler
    from core.hands.builtin import ContentHand, PracticeHand

    scheduler = HandScheduler()
    scheduler.register(ContentHand())
    scheduler.register(PracticeHand())
    scheduler.start()

    # Check status
    for info in scheduler.dashboard():
        print(info)

    # Later
    scheduler.stop()
"""

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

from core.hands.base import Hand, HandResult, HandStatus

_log = logging.getLogger("core.hands.scheduler")

_ROOT = Path(__file__).resolve().parent.parent.parent
_STATE_FILE = _ROOT / "data" / "hands_state.json"


class HandScheduler:
    """Manages the lifecycle and scheduling of all registered Hands."""

    def __init__(self, check_interval: float = 30.0):
        self._hands: dict[str, Hand] = {}
        self._next_run: dict[str, float] = {}   # hand_id -> next run timestamp
        self._check_interval = check_interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    # -- Registration --

    def register(self, hand: Hand):
        """Register a Hand with the scheduler."""
        hid = hand.manifest.id
        with self._lock:
            self._hands[hid] = hand
            # Schedule first run: now + schedule_minutes (or never if 0)
            if hand.manifest.schedule_minutes > 0 and hand.manifest.enabled:
                self._next_run[hid] = time.time() + 60  # first run in 1 minute
            else:
                self._next_run[hid] = 0
        _log.info("Registered Hand: %s (%s)", hand.manifest.name, hid)

    def unregister(self, hand_id: str):
        """Remove a Hand from the scheduler."""
        with self._lock:
            self._hands.pop(hand_id, None)
            self._next_run.pop(hand_id, None)

    def get_hand(self, hand_id: str) -> Optional[Hand]:
        return self._hands.get(hand_id)

    def list_hands(self) -> list[str]:
        return list(self._hands.keys())

    # -- Activation --

    def activate(self, hand_id: str) -> bool:
        """Activate a Hand (enable it and start scheduling)."""
        hand = self._hands.get(hand_id)
        if not hand:
            return False
        hand.manifest.enabled = True
        hand._status = HandStatus.IDLE
        if hand.manifest.schedule_minutes > 0:
            self._next_run[hand_id] = time.time() + 60
        hand.on_activate()
        self._save_state()
        return True

    def deactivate(self, hand_id: str) -> bool:
        """Deactivate a Hand (disable scheduling)."""
        hand = self._hands.get(hand_id)
        if not hand:
            return False
        hand.manifest.enabled = False
        hand._status = HandStatus.DISABLED
        self._next_run[hand_id] = 0
        hand.on_deactivate()
        self._save_state()
        return True

    # -- Manual execution --

    def run_now(self, hand_id: str) -> Optional[HandResult]:
        """Execute a Hand immediately, bypassing the schedule."""
        hand = self._hands.get(hand_id)
        if not hand:
            _log.warning("Unknown hand: %s", hand_id)
            return None
        return self._execute_hand(hand)

    # -- Execution --

    def _execute_hand(self, hand: Hand) -> HandResult:
        """Execute a single Hand with pre-flight, timing, and telemetry."""
        hid = hand.manifest.id
        _log.info("Executing Hand: %s", hid)
        hand._status = HandStatus.RUNNING

        # Pre-flight check
        ok, reason = hand.preflight()
        if not ok:
            _log.warning("Hand '%s' preflight failed: %s", hid, reason)
            result = HandResult(
                success=False,
                error=f"Preflight failed: {reason}",
            )
            hand._metrics.record(result)
            hand._status = HandStatus.IDLE
            self._record_telemetry(hand, result)
            return result

        # Execute with timeout enforcement
        start = time.time()
        max_seconds = hand.manifest.max_runtime_seconds
        try:
            _result_box: list[HandResult] = []
            exec_thread = threading.Thread(
                target=lambda: _result_box.append(hand.execute()),
                name=f"Hand-{hid}",
                daemon=True,
            )
            exec_thread.start()
            exec_thread.join(timeout=max_seconds if max_seconds > 0 else None)

            if exec_thread.is_alive():
                elapsed = time.time() - start
                _log.warning("Hand '%s' killed — exceeded %ds runtime (ran %.0fs)",
                             hid, max_seconds, elapsed)
                result = HandResult(
                    success=False,
                    error=f"Killed: exceeded {max_seconds}s max runtime",
                    duration=elapsed,
                )
                try:
                    from core.audit_log import audit as _audit
                    _audit("hand.killed", hand_id=hid, max_seconds=max_seconds,
                           elapsed=elapsed)
                except ImportError:
                    pass
            elif _result_box:
                result = _result_box[0]
                result.duration = time.time() - start
            else:
                result = HandResult(
                    success=False,
                    error="Hand execute() returned no result",
                    duration=time.time() - start,
                )
        except Exception as exc:
            _log.error("Hand '%s' raised: %s", hid, exc, exc_info=True)
            result = HandResult(
                success=False,
                error=str(exc),
                duration=time.time() - start,
            )

        # Update metrics
        hand._metrics.record(result)
        hand._status = HandStatus.IDLE if result.success else HandStatus.ERROR

        # Schedule next run
        if hand.manifest.schedule_minutes > 0 and hand.manifest.enabled:
            self._next_run[hid] = time.time() + hand.manifest.schedule_minutes * 60

        # Record telemetry
        self._record_telemetry(hand, result)
        self._save_state()

        _log.info("Hand '%s' %s: %s (%.1fs)",
                  hid, "OK" if result.success else "FAIL",
                  result.message or result.error, result.duration)
        return result

    def _record_telemetry(self, hand: Hand, result: HandResult):
        """Record Hand execution in the telemetry system."""
        try:
            from core.telemetry import telemetry
            telemetry.record(
                action_type="hand",
                intent=f"Hand:{hand.manifest.id} — {hand.manifest.name}",
                result="success" if result.success else "failure",
                result_detail=result.message,
                duration=result.duration,
                error=result.error,
                metadata={
                    "hand_id": hand.manifest.id,
                    "items_processed": result.items_processed,
                    "data": result.data,
                },
            )
        except Exception:
            pass  # Telemetry is non-critical

    # -- Scheduler loop --

    def start(self):
        """Start the background scheduler thread."""
        if self._thread and self._thread.is_alive():
            _log.warning("Scheduler already running")
            return
        self._stop_event.clear()
        self._load_state()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="HandScheduler",
            daemon=True,
        )
        self._thread.start()
        _log.info("Hand scheduler started (%d hands registered)", len(self._hands))

    def stop(self):
        """Stop the scheduler."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._save_state()
        _log.info("Hand scheduler stopped")

    def _run_loop(self):
        """Main scheduler loop — checks which Hands are due and runs them."""
        while not self._stop_event.is_set():
            now = time.time()
            with self._lock:
                due_hands = [
                    self._hands[hid]
                    for hid, next_time in self._next_run.items()
                    if next_time > 0 and now >= next_time
                    and hid in self._hands
                    and self._hands[hid].manifest.enabled
                    and self._hands[hid].status != HandStatus.RUNNING
                ]

            for hand in due_hands:
                if self._stop_event.is_set():
                    break
                try:
                    self._execute_hand(hand)
                except Exception as exc:
                    _log.error("Scheduler error for '%s': %s",
                              hand.manifest.id, exc)

            self._stop_event.wait(self._check_interval)

    # -- State persistence --

    def _save_state(self):
        """Save scheduler state (enabled/disabled, next run times)."""
        try:
            state = {}
            for hid, hand in self._hands.items():
                met = hand.metrics
                state[hid] = {
                    "enabled": hand.manifest.enabled,
                    "next_run": self._next_run.get(hid, 0),
                    "total_runs": met.total_runs,
                    "successful_runs": met.successful_runs,
                    "failed_runs": met.failed_runs,
                    "total_items": met.total_items_processed,
                    "total_runtime": met.total_runtime,
                    "last_run_time": met.last_run_time,
                    "streak": met.streak,
                }
            _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _STATE_FILE.write_text(
                json.dumps(state, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            _log.debug("Failed to save state: %s", exc)

    def _load_state(self):
        """Restore scheduler state from disk."""
        if not _STATE_FILE.exists():
            return
        try:
            state = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            for hid, data in state.items():
                hand = self._hands.get(hid)
                if not hand:
                    continue
                hand.manifest.enabled = data.get("enabled", True)
                self._next_run[hid] = data.get("next_run", 0)
                # Restore metrics
                met = hand._metrics
                met.total_runs = data.get("total_runs", 0)
                met.successful_runs = data.get("successful_runs", 0)
                met.failed_runs = data.get("failed_runs", 0)
                met.total_items_processed = data.get("total_items", 0)
                met.total_runtime = data.get("total_runtime", 0)
                met.last_run_time = data.get("last_run_time", 0)
                met.streak = data.get("streak", 0)
                if not hand.manifest.enabled:
                    hand._status = HandStatus.DISABLED
            _log.info("Restored state for %d hands", len(state))
        except Exception as exc:
            _log.debug("Failed to load state: %s", exc)

    # -- Dashboard --

    def dashboard(self) -> list[dict]:
        """Get dashboard info for all registered Hands."""
        return [hand.get_dashboard_info() for hand in self._hands.values()]

    def dashboard_summary(self) -> str:
        """Get a text summary of all Hands for display."""
        lines = ["=== Onyx Hands Dashboard ===", ""]
        for hand in self._hands.values():
            lines.append(hand.get_summary())
            next_run = self._next_run.get(hand.manifest.id, 0)
            if next_run > 0:
                secs = max(0, next_run - time.time())
                if secs < 60:
                    lines.append(f"  Next run: {secs:.0f}s")
                else:
                    lines.append(f"  Next run: {secs / 60:.0f}min")
            lines.append("")
        return "\n".join(lines)
