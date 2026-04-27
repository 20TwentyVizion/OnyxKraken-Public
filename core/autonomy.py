"""Autonomy Daemon — background goal pursuit and self-improvement on a timer.

Runs as a background thread, periodically:
  1. Checks for queued goals and executes them
  2. Runs self-improvement cycles when idle
  3. Monitors system state and can proactively suggest actions

Inspired by EVERA's AutonomousDaemon, adapted for OnyxKraken's desktop focus.
"""

import os
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional

from log import get_logger

_log = get_logger("daemon")


class DaemonState(StrEnum):
    IDLE = "idle"
    EXECUTING = "executing"
    IMPROVING = "improving"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class QueuedGoal:
    """A goal queued for background execution."""
    goal: str
    app_name: str = "unknown"
    priority: int = 0  # higher = more urgent
    queued_at: float = 0.0


class AutonomyDaemon:
    """Background daemon that pursues goals, self-improves, and thinks proactively.

    The daemon is the autonomic nervous system of the entity:
      - Executes queued goals
      - Generates proactive goals via the Mind when idle
      - Runs self-improvement cycles periodically
      - Reflects on performance at regular intervals
      - Notifies via Discord on state changes

    Usage:
        daemon = AutonomyDaemon()
        daemon.start()
        daemon.queue_goal("Open Notepad and type Hello")
        # ... later
        daemon.stop()
    """

    def __init__(
        self,
        improve_interval: float = 300.0,    # self-improve every 5 min when idle
        reflect_interval: float = 600.0,    # reflect every 10 min
        proactive_interval: float = 120.0,  # generate proactive goal every 2 min when idle
        check_interval: float = 5.0,        # check queue every 5s
        max_consecutive_failures: int = 3,   # pause after N consecutive failures
    ):
        self.improve_interval = improve_interval
        self.reflect_interval = reflect_interval
        self.proactive_interval = proactive_interval
        self.check_interval = check_interval
        self.max_consecutive_failures = max_consecutive_failures

        self._state = DaemonState.STOPPED
        self._thread: Optional[threading.Thread] = None
        self._goal_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # not paused initially

        self._consecutive_failures = 0
        self._last_improve_time = 0.0
        self._last_reflect_time = 0.0
        self._last_proactive_time = 0.0
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._proactive_completed = 0
        self._training_focus: Optional[str] = None  # e.g. "blender"
        self._session_budget: dict = {  # resource budgets per training session
            "max_session_seconds": 1800,   # 30 min per session
            "max_renders": 10,
            "max_research_calls": 5,
            "renders_used": 0,
            "research_calls_used": 0,
            "session_start": 0.0,
            "exercises_attempted": 0,
            "reviews_done": 0,
        }
        self._last_training_time = 0.0
        self._training_cooldown = 600.0  # 10 min between training sessions
        self._log: list[dict] = []
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        return self._state

    @property
    def training_focus(self) -> Optional[str]:
        """Current training focus domain (e.g. 'blender'). None = unconstrained."""
        return self._training_focus

    def set_training_focus(self, focus: Optional[str]):
        """Set or clear the training focus domain.

        When set, proactive goals are constrained to this domain.
        Set to None to clear focus and allow any proactive goals.

        Args:
            focus: Domain name (e.g. 'blender') or None to clear.
        """
        old = self._training_focus
        self._training_focus = focus.lower().strip() if focus else None
        if self._training_focus:
            _log.info(f"Training focus set: {self._training_focus}")
            self._log_event("focus_set", focus=self._training_focus)
        else:
            _log.info(f"Training focus cleared (was: {old})")
            self._log_event("focus_cleared", was=old)

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def start(self):
        """Start the autonomy daemon."""
        if self._state not in (DaemonState.STOPPED,):
            _log.warning(f"Already running (state={self._state})")
            return

        self._stop_event.clear()
        self._pause_event.set()
        self._state = DaemonState.IDLE
        self._thread = threading.Thread(target=self._main_loop, daemon=True, name="AutonomyDaemon")
        self._thread.start()
        _log.info("Started.")

    def stop(self):
        """Stop the daemon gracefully."""
        self._stop_event.set()
        self._pause_event.set()  # unblock if paused
        self._state = DaemonState.STOPPED
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        _log.info("Stopped.")

    def pause(self):
        """Pause the daemon (finishes current task first)."""
        self._pause_event.clear()
        self._state = DaemonState.PAUSED
        _log.info("Paused.")

    def resume(self):
        """Resume the daemon."""
        self._pause_event.set()
        self._state = DaemonState.IDLE
        _log.info("Resumed.")

    # ------------------------------------------------------------------
    # Goal queue
    # ------------------------------------------------------------------

    def queue_goal(self, goal: str, app_name: str = "unknown", priority: int = 0):
        """Add a goal to the background execution queue."""
        item = QueuedGoal(
            goal=goal,
            app_name=app_name,
            priority=priority,
            queued_at=time.time(),
        )
        # PriorityQueue uses lowest-first, so negate priority
        self._goal_queue.put((-priority, time.time(), item))
        self._log_event("queued", goal=goal)
        _log.info(f"Goal queued: {goal[:60]}... (priority={priority})")

    def queue_size(self) -> int:
        return self._goal_queue.qsize()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _main_loop(self):
        """Main daemon loop — the autonomic nervous system of the entity.

        Priority order:
          1. Execute queued goals (user-submitted or proactive)
          2. Reflect on performance (periodic)
          3. Generate proactive goals via the Mind (when truly idle)
          4. Run self-improvement cycles (periodic)
        """
        _log.info("Main loop started.")
        self._notify("Daemon started — OnyxKraken is now autonomous.")

        try:
            self._main_loop_inner()
        except Exception as e:
            _log.error(f"FATAL — main loop crashed: {e}")
            self._log_event("fatal_error", reason=str(e))
            import traceback
            traceback.print_exc()
        finally:
            self._state = DaemonState.STOPPED
            _log.info("Main loop exited.")

    def _main_loop_inner(self):
        """Inner main loop — separated so top-level handler catches everything."""
        while not self._stop_event.is_set():
            # Check for pause
            self._pause_event.wait()
            if self._stop_event.is_set():
                break

            # 1. Execute queued goals
            try:
                _, _, queued = self._goal_queue.get_nowait()
                self._execute_goal(queued)
                continue
            except queue.Empty:
                pass  # expected — no goals queued

            now = time.time()

            # 2. Training cycle (when focus is set, replaces proactive goals)
            if (self._training_focus
                    and now - self._last_training_time >= self._training_cooldown):
                try:
                    self._run_training_cycle()
                except Exception as e:
                    _log.error(f"Training cycle error: {e}")
                    self._log_event("training_cycle_error", reason=str(e))
                self._last_training_time = now
                continue

            # 3. Reflection cycle (periodic)
            if now - self._last_reflect_time >= self.reflect_interval:
                self._run_reflection()
                self._last_reflect_time = now
                continue

            # 4. Proactive goal generation via the Mind (skipped during training)
            if (not self._training_focus
                    and now - self._last_proactive_time >= self.proactive_interval):
                self._run_proactive()
                self._last_proactive_time = now
                continue

            # 5. Self-improvement cycle (periodic)
            if now - self._last_improve_time >= self.improve_interval:
                self._run_improvement()
                self._last_improve_time = now
                continue

            # 6. Ecosystem workflow schedules (check for due workflows)
            try:
                from apps.workflow_scheduler import get_scheduler
                scheduler = get_scheduler()
                due_results = scheduler.execute_due()
                if due_results:
                    for dr in due_results:
                        self._log_event("scheduled_workflow",
                                        schedule_id=dr.get("schedule_id"),
                                        ok=dr.get("ok"))
                    continue
            except Exception as e:
                _log.debug(f"Workflow scheduler error: {e}")

            # 7. Silent operations (knowledge consolidation, benchmark analysis, etc.)
            try:
                from core.silent_ops import run_next_silent_op
                result = run_next_silent_op()
                if result:
                    self._log_event("silent_op", **result)
                    continue
            except Exception as e:
                _log.debug(f"Silent op error: {e}")

            # 8. BBT proactive briefings (morning + evening)
            try:
                self._check_bbt_briefings()
            except Exception as e:
                _log.debug(f"BBT briefing check error: {e}")

            # Sleep before next check
            self._stop_event.wait(timeout=self.check_interval)

    def _execute_goal(self, queued: QueuedGoal):
        """Execute a single queued goal."""
        self._state = DaemonState.EXECUTING
        goal = queued.goal
        app_name = queued.app_name
        is_proactive = getattr(queued, '_proactive', False)
        _log.info(f"Executing: {goal}")

        # Prediction-error learning: predict before acting
        _prediction_id = None
        try:
            from core.prediction_engine import get_prediction_engine
            pe = get_prediction_engine()
            pred = pe.predict(goal, domain=app_name if app_name != "unknown" else "general")
            _prediction_id = pred.id
        except Exception as e:
            _log.debug(f"Prediction skipped: {e}")

        # Earned-autonomy gate: block proactive goals in low-trust domains
        if is_proactive and app_name != "unknown":
            try:
                from core.trust_ledger import get_trust_ledger, TrustLevel
                ledger = get_trust_ledger()
                if not ledger.is_allowed(app_name, TrustLevel.CAUTIOUS):
                    _log.info(f"Trust too low for proactive goal in '{app_name}' "
                              f"(score={ledger.get_score(app_name)}). Skipping.")
                    self._log_event("trust_blocked", goal=goal, domain=app_name)
                    self._state = DaemonState.IDLE
                    return
            except Exception as e:
                _log.debug(f"Trust check skipped: {e}")

        try:
            from agent.orchestrator import run
            result = run(goal, app_name=app_name, headless=True)
            success = not result.aborted and result.steps_completed == result.steps_planned

            # Update trust ledger
            try:
                from core.trust_ledger import get_trust_ledger
                ledger = get_trust_ledger()
                domain = app_name if app_name != "unknown" else "general"
                if success:
                    ledger.record_success(domain, goal[:120])
                else:
                    ledger.record_failure(domain, goal[:120])
            except Exception as e:
                _log.debug(f"Trust ledger update skipped: {e}")

            if success:
                self._consecutive_failures = 0
                self._tasks_completed += 1
                self._log_event("completed", goal=goal, time=result.total_time)
                _log.info(f"Goal completed: {goal[:60]}...")
                if is_proactive:
                    self._proactive_completed += 1
                    try:
                        from core.mind import get_mind
                        get_mind().record_proactive_success()
                    except Exception as e:
                        _log.debug(f"Could not record proactive success: {e}")
            else:
                self._consecutive_failures += 1
                self._tasks_failed += 1
                self._log_event("failed", goal=goal, reason=result.failure_reason)
                _log.info(f"Goal failed: {goal[:60]}...")

            # Auto-pause after too many consecutive failures
            if self._consecutive_failures >= self.max_consecutive_failures:
                msg = f"{self._consecutive_failures} consecutive failures. Auto-pausing."
                _log.warning(msg)
                self._notify(f"⚠️ {msg}")
                self.pause()
                return

            # Prediction-error learning: record outcome
            if _prediction_id:
                try:
                    from core.prediction_engine import get_prediction_engine
                    pe = get_prediction_engine()
                    outcome = pe.record_outcome(
                        _prediction_id, actual_success=success,
                        actual_duration=result.total_time,
                    )
                    if outcome.is_surprise:
                        self._log_event("surprise", lesson=outcome.lesson,
                                        score=outcome.surprise_score)
                except Exception as e:
                    _log.debug(f"Prediction outcome skipped: {e}")

            # System 1 fast reflection (cheap, no LLM)
            try:
                from core.mind import get_mind
                s1 = get_mind().reflect_fast(
                    goal=goal, success=success, app=app_name,
                    duration=result.total_time,
                )
                if s1.get("alert"):
                    self._log_event("system1_alert", alert=s1["alert"])
            except Exception as e:
                _log.debug(f"System1 reflection skipped: {e}")

        except Exception as e:
            self._consecutive_failures += 1
            self._tasks_failed += 1
            self._log_event("error", goal=goal, reason=str(e))
            _log.error(f"Goal execution error: {e}")

        self._state = DaemonState.IDLE

    def _run_improvement(self):
        """Run a self-improvement cycle."""
        self._state = DaemonState.IMPROVING
        _log.info("Running self-improvement cycle...")

        try:
            from core.self_improvement import get_improvement_engine
            engine = get_improvement_engine()
            summary = engine.run_improvement_cycle()
            self._log_event("improved", **summary)
            # Notify if something was generated
            if summary.get("modules_generated", 0) > 0:
                try:
                    from core.discord_notify import notify_improvement
                    notify_improvement(
                        gaps=summary.get("gaps_identified", 0),
                        modules=summary.get("modules_generated", 0),
                    )
                except Exception as e2:
                    _log.debug(f"Improvement notification failed: {e2}")
        except Exception as e:
            _log.error(f"Self-improvement error: {e}")
            self._log_event("improve_error", reason=str(e))

        self._state = DaemonState.IDLE

    def _run_reflection(self):
        """Run a reflection cycle via the Mind (System 2 deep consolidation)."""
        self._state = DaemonState.IMPROVING
        _log.info("Running deep reflection (System 2)...")

        try:
            from core.mind import get_mind
            mind = get_mind()
            result = mind.reflect_deep()
            self._log_event("reflected",
                            insight=result.get("insight", "")[:100],
                            mood=result.get("mood", "ready"),
                            outcomes_reviewed=result.get("system1_outcomes_reviewed", 0))
        except Exception as e:
            _log.error(f"Reflection error: {e}")
            self._log_event("reflect_error", reason=str(e))

        self._state = DaemonState.IDLE

    def _run_training_cycle(self):
        """Run a structured training cycle using the curriculum + review pipeline.

        Training loop (when training_focus='blender'):
          1. Check curriculum → pick next unmastered exercise
          2. Generate goal from exercise prompt → execute via orchestrator
          3. Run verify script → record result
          4. If failed 3+ times → demote skill, research the technique
          5. Every 5 exercises → review 1 old OnyxProjects file
          6. Respect session budgets (time, renders, API calls)
        """
        if self._training_focus != "blender":
            return

        self._state = DaemonState.EXECUTING
        _log.info("=== BLENDER TRAINING CYCLE ===")

        # Reset session budget
        budget = self._session_budget
        budget["renders_used"] = 0
        budget["research_calls_used"] = 0
        budget["session_start"] = time.time()
        budget["exercises_attempted"] = 0
        budget["reviews_done"] = 0

        try:
            from addons.blender.curriculum import get_curriculum
            curriculum = get_curriculum()

            # Training session: attempt exercises until budget exhausted
            while not self._stop_event.is_set():
                elapsed = time.time() - budget["session_start"]
                if elapsed >= budget["max_session_seconds"]:
                    _log.info(f"Session time limit reached ({elapsed:.0f}s)")
                    break
                if budget["renders_used"] >= budget["max_renders"]:
                    _log.info("Render budget exhausted")
                    break

                # Periodic review: every 5 exercises, review an old project
                if (budget["exercises_attempted"] > 0
                        and budget["exercises_attempted"] % 5 == 0
                        and budget["reviews_done"] < 1):
                    self._training_review_old_project()
                    budget["reviews_done"] += 1
                    continue

                # Get next exercise
                exercise = curriculum.next_exercise()
                if exercise is None:
                    _log.info("All exercises at current level complete!")
                    _log.info(f"{curriculum.get_stats_summary()}")
                    break

                ex_id = exercise["id"]
                ex_state = curriculum._data["exercises"].get(ex_id, {})
                attempts = ex_state.get("attempts", 0)

                # If attempted 3+ times, demote and research
                if attempts >= 3 and not ex_state.get("passed", False):
                    if ex_id not in curriculum._data.get("demoted_skills", []):
                        curriculum.demote_exercise(ex_id)
                        self._training_research_skill(exercise)
                        budget["research_calls_used"] += 1
                        continue

                # Execute the exercise
                _log.info(f"Exercise: {exercise['name']} (L{exercise['level']})")
                self._training_execute_exercise(exercise, curriculum)
                budget["exercises_attempted"] += 1
                budget["renders_used"] += 1

        except Exception as e:
            _log.error(f"Training error: {e}")
            self._log_event("training_error", reason=str(e))

        # Session summary
        elapsed = time.time() - budget["session_start"]
        _log.info(f"Session complete: {budget['exercises_attempted']} exercises, "
              f"{budget['reviews_done']} reviews, {elapsed:.0f}s")
        self._log_event("training_session",
                        exercises=budget["exercises_attempted"],
                        reviews=budget["reviews_done"],
                        duration=round(elapsed, 1))

        try:
            from addons.blender.curriculum import get_curriculum
            _log.info(f"{get_curriculum().get_stats_summary()}")
        except Exception as e:
            _log.debug(f"Blender curriculum stats unavailable: {e}")

        self._state = DaemonState.IDLE

    def _training_execute_exercise(self, exercise: dict, curriculum):
        """Execute a single curriculum exercise via the orchestrator."""
        try:
            from agent.orchestrator import run
            goal = (
                f"BLENDER TRAINING EXERCISE: {exercise['name']}\n"
                f"{exercise['prompt']}\n"
                "Use onyx_bpy toolkit. Run in headless mode (--background). "
                "Use blender_python action with save_after=true."
            )
            result = run(goal, app_name="blender", headless=True)
            success = not result.aborted and result.steps_completed == result.steps_planned

            # Score based on completion
            score = 7.5 if success else 3.0
            curriculum.record_result(
                exercise["id"],
                score=score,
                passed=success,
                feedback=result.failure_reason if not success else "Completed via orchestrator",
            )

            if success:
                self._consecutive_failures = 0
                self._tasks_completed += 1
            else:
                self._consecutive_failures += 1
                self._tasks_failed += 1

        except Exception as e:
            print(f"[Training] Exercise execution error: {e}")
            curriculum.record_result(
                exercise["id"], score=0, passed=False,
                feedback=f"Execution error: {e}",
            )

    def _training_research_skill(self, exercise: dict):
        """Research a skill that OnyxKraken is struggling with."""
        try:
            from addons.blender.research import research_topic
            topic = exercise["name"].replace("_", " ")
            print(f"[Training] Researching failed skill: {topic}")
            research_topic(topic)  # Will store in knowledge if videos provided
            self._log_event("training_research", topic=topic, exercise=exercise["id"])
        except Exception as e:
            print(f"[Training] Research error: {e}")

    def _training_review_old_project(self):
        """Review one old OnyxProjects file during training."""
        try:
            from addons.blender.review import get_reviewer
            reviewer = get_reviewer()
            inventory = reviewer.scan_projects()
            priority = reviewer.prioritize(inventory, max_count=1)
            if priority:
                print(f"\n[Training] Reviewing old project: {priority[0]['name']}")
                reviewer.review_file(priority[0]["path"])
                self._log_event("training_review", file=priority[0]["name"])
        except Exception as e:
            print(f"[Training] Review error: {e}")

    def _run_proactive(self):
        """Ask the Mind for a proactive goal and queue it."""
        print("[Daemon] Consulting the Mind for proactive goals...")

        try:
            from core.mind import get_mind
            mind = get_mind()
            goal_data = mind.generate_proactive_goal(
                training_focus=self._training_focus,
            )
            if goal_data and goal_data.get("goal"):
                goal_text = goal_data["goal"]
                app_name = goal_data.get("app_name", "unknown")
                priority = goal_data.get("priority", 1)
                item = QueuedGoal(
                    goal=goal_text,
                    app_name=app_name,
                    priority=priority,
                    queued_at=time.time(),
                )
                item._proactive = True
                self._goal_queue.put((-priority, time.time(), item))
                self._log_event("proactive_goal",
                                goal=goal_text,
                                reason=goal_data.get("reason", ""),
                                category=goal_data.get("category", ""))
        except Exception as e:
            print(f"[Daemon] Proactive goal error: {e}")

    def _notify(self, message: str):
        """Send a Discord notification (best-effort)."""
        try:
            from core.discord_notify import notify_daemon_event
            notify_daemon_event(message)
        except Exception as e:
            _log.debug(f"Discord daemon notification failed: {e}")

    # ------------------------------------------------------------------
    # BBT Proactive Briefings
    # ------------------------------------------------------------------

    _bbt_last_briefing_date: str = ""
    _bbt_last_reminder_date: str = ""

    def _check_bbt_briefings(self):
        """Check if it's time to send a BBT morning briefing or evening reminder.

        Schedule:
          - Morning briefing:  7:00-10:00 AM, once per day
          - Evening reminder:  8:00-10:00 PM, once per day (if commitments exist)
        """
        import datetime as _dt
        import requests as _req

        now = _dt.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        hour = now.hour
        bbt_url = os.environ.get("BBT_API_URL", "http://127.0.0.1:3600")

        # Morning briefing: 7-10 AM
        if 7 <= hour < 10 and self._bbt_last_briefing_date != today_str:
            _log.info("BBT: Generating proactive morning briefing...")
            try:
                r = _req.get(f"{bbt_url}/api/briefing?format=text", timeout=120)
                if r.status_code == 200:
                    from core.discord_notify import notify_bbt_briefing
                    notify_bbt_briefing(r.text)
                    self._bbt_last_briefing_date = today_str
                    self._log_event("bbt_briefing_sent")
                    _log.info("BBT: Morning briefing sent to Discord.")
                else:
                    _log.debug(f"BBT briefing API returned {r.status_code}")
            except _req.exceptions.ConnectionError:
                _log.debug("BBT not running — skipping morning briefing")
            except Exception as e:
                _log.debug(f"BBT briefing error: {e}")

        # Evening commitment reminder: 8-10 PM
        if 20 <= hour < 22 and self._bbt_last_reminder_date != today_str:
            try:
                r = _req.get(f"{bbt_url}/api/state", timeout=10)
                if r.status_code == 200:
                    state = r.json()
                    commitments = state.get("coachMemory", [])
                    if commitments:
                        from core.discord_notify import notify_bbt_commitment_reminder
                        notify_bbt_commitment_reminder(commitments)
                        self._bbt_last_reminder_date = today_str
                        self._log_event("bbt_reminder_sent", count=len(commitments))
                        _log.info(f"BBT: Evening reminder sent ({len(commitments)} commitments).")
            except _req.exceptions.ConnectionError:
                _log.debug("BBT not running — skipping evening reminder")
            except Exception as e:
                _log.debug(f"BBT reminder error: {e}")

    # ------------------------------------------------------------------
    # Logging / stats
    # ------------------------------------------------------------------

    def _log_event(self, event_type: str, **kwargs):
        with self._lock:
            self._log.append({
                "type": event_type,
                "timestamp": time.time(),
                **kwargs,
            })
            # Cap log
            if len(self._log) > 200:
                self._log = self._log[-200:]

    def get_stats(self) -> dict:
        with self._lock:
            stats = {
                "state": self._state,
                "training_focus": self._training_focus,
                "tasks_completed": self._tasks_completed,
                "tasks_failed": self._tasks_failed,
                "proactive_completed": self._proactive_completed,
                "consecutive_failures": self._consecutive_failures,
                "queue_size": self._goal_queue.qsize(),
                "recent_log": self._log[-10:],
            }
            # Include mind stats if available
            try:
                from core.mind import get_mind
                stats["mind"] = get_mind().get_stats()
            except Exception as e:
                _log.debug(f"Could not get mind stats: {e}")
            # Include trust ledger
            try:
                from core.trust_ledger import get_trust_ledger
                stats["trust"] = get_trust_ledger().get_stats()
            except Exception as e:
                _log.debug(f"Could not get trust stats: {e}")
            return stats


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_daemon: Optional[AutonomyDaemon] = None


def get_daemon() -> AutonomyDaemon:
    global _daemon
    if _daemon is None:
        _daemon = AutonomyDaemon()
    return _daemon
