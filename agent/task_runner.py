"""Top-level task runner — goal decomposition, execution, and post-task reflection.

This is the main entry point called by main.py, the API server, the autonomy
daemon, and the benchmark harness.  It orchestrates the full lifecycle:

    1. Recall similar past tasks from memory
    2. Discover app modules
    3. Decompose goal into typed steps (via planner)
    4. Execute steps via StepExecutor
    5. Post-task: record to memory, self-improvement, knowledge capture, discord
"""

import config
from log import get_logger

_log = get_logger("agent.task_runner")

from agent.planner import decompose_goal
from apps.registry import discover_modules, get_module, list_modules
from memory.store import MemoryStore


def run(goal: str, app_name: str = "unknown", headless: bool = False,
        progress_callback=None):
    """Run the agent orchestrator for a given goal.

    Args:
        goal: The high-level goal to accomplish.
        app_name: Name of the target application (for safety rules).
        headless: If True, skip confirmation prompts (API/daemon mode).
        progress_callback: Optional callable(step_idx, total, description, status).

    Returns:
        TaskResult with structured outcome data.
    """
    # Lazy import to avoid circular dependency
    from agent.orchestrator import StepExecutor, TaskResult  # noqa: F811

    # License check — enforce demo limits
    from core.license import (
        get_license, get_session, is_app_allowed,
        get_upgrade_message, get_tier_display,
    )
    lic = get_license()
    session = get_session()

    if not session.can_run_task(lic):
        _log.warning("Demo task limit reached.")
        print(get_upgrade_message())
        return TaskResult(
            goal=goal, app_name=app_name, aborted=True,
            failure_reason="Demo task limit reached. Upgrade to continue.",
        )

    if not is_app_allowed(app_name):
        msg = (
            f"The '{app_name}' module requires a paid license.\n"
            f"  Current tier: {get_tier_display()}\n"
            f"  Upgrade at: https://markvizion.gumroad.com/l/onyxkraken\n"
            f"  Activate:   python main.py activate ONYX-XXXX-XXXX-XXXX-XXXX"
        )
        _log.warning(msg)
        print(f"\n{msg}\n")
        return TaskResult(
            goal=goal, app_name=app_name, aborted=True,
            failure_reason=f"App '{app_name}' not available in demo mode.",
        )

    # Increment session task counter
    session.increment()
    remaining = session.remaining_tasks(lic)
    if remaining is not None:
        _log.info(f"[License] Demo mode — {remaining} task(s) remaining this session")

    memory = MemoryStore()

    _log.info(f"{'='*60}")
    _log.info(f"  OnyxKraken — Goal: {goal}")
    _log.info(f"  Autonomy mode: {config.AUTONOMY_MODE}")
    _log.info(f"{'='*60}")

    # Show relevant past experience (enhanced with unified memory)
    unified_context = ""
    try:
        from memory.unified import get_unified_memory
        umem = get_unified_memory()
        unified_context = umem.get_task_context(goal, app_name, max_items=6)
        if unified_context:
            _log.info("Unified memory context loaded.")
    except Exception as e:
        _log.debug(f"Unified memory unavailable: {e}")

    similar = memory.recall_similar_tasks(goal, limit=3)
    if similar:
        _log.info(f"Found {len(similar)} similar past tasks:")
        for t in similar:
            status = "✅" if t["success"] else "❌"
            _log.info(f"  {status} \"{t['goal'][:50]}\" ({t['total_time']}s)")
            if t.get("notes"):
                _log.info(f"     Note: {t['notes'][:80]}")

    # Discover app modules
    discover_modules()
    app_module = get_module(app_name)
    if app_module:
        _log.info(f"Loaded app module: {app_module.app_name}")
    else:
        _log.info(f"No specific module for '{app_name}', using generic mode.")

    # Decompose the goal into typed steps (memory-augmented)
    _log.info("Decomposing goal into steps...")
    steps = decompose_goal(goal, memory=memory)
    _log.info(f"Plan ({len(steps)} steps):")
    for i, s in enumerate(steps, 1):
        _log.info(f"  {i}. {s['description']}  [{s['type']}]")

    # Post-planner module detection: scan steps for known app names
    if app_module is None:
        all_text = " ".join(s["description"] for s in steps).lower()
        for mod_name in list_modules():
            if mod_name in all_text:
                app_module = get_module(mod_name)
                if app_module:
                    app_name = app_module.app_name
                    _log.info(f"Detected app module from plan: {app_module.app_name}")
                    break

    # Execute
    executor = StepExecutor(goal, app_name, app_module, memory, headless=headless,
                            progress_callback=progress_callback)
    result = executor.run(steps)

    # Post-task reflection
    _post_task_reflect(result, goal, app_name, memory)

    return result


def _post_task_reflect(result, goal: str, app_name: str, memory: MemoryStore):
    """Record outcomes to memory, self-improvement, knowledge, and discord."""
    success = not result.aborted and result.steps_completed == result.steps_planned
    notes = ""
    if result.aborted:
        notes = f"Aborted: {result.failure_reason}"
    elif result.steps_completed < result.steps_planned:
        notes = f"Incomplete: {result.steps_completed}/{result.steps_planned} steps"

    memory.record_task(
        goal=goal,
        app_name=app_name,
        steps_planned=result.steps_planned,
        steps_completed=result.steps_completed,
        total_time=result.total_time,
        success=success,
        notes=notes,
    )
    _log.info(f"Task recorded. Total memories: {len(memory.get_all()['task_history'])} tasks.")

    # Self-improvement: record failures for later analysis
    if not success:
        try:
            from core.self_improvement import get_improvement_engine
            improvement = get_improvement_engine()
            actions_tried = [
                s.get("type", "unknown") for s in result.step_outcomes
            ]
            improvement.record_failure(
                goal=goal,
                error=result.failure_reason or notes,
                app_name=app_name,
                actions_tried=actions_tried,
            )
        except Exception as e:
            _log.warning(f"Could not record failure: {e}")

    # Knowledge capture: learn from successful tasks
    if success and result.steps_completed > 0:
        try:
            from core.knowledge import get_knowledge_store
            ks = get_knowledge_store()

            # Store the successful execution pattern
            step_types = [s.get("type", "?") for s in result.step_outcomes]
            step_descs = [s.get("description", "?")[:60] for s in result.step_outcomes]
            pattern = (
                f"Goal: \"{goal[:100]}\" | App: {app_name} | "
                f"Steps: {' → '.join(step_types)} | "
                f"Time: {result.total_time:.1f}s | Actions: {result.total_actions}"
            )
            ks.add_task_pattern(pattern, source=f"task:{goal[:60]}")

            # Store app-specific knowledge if we learned something
            if app_name != "unknown" and result.total_actions > 0:
                approach = " → ".join(step_descs[:5])
                ks.add_app_knowledge(
                    app_name,
                    f"Successful approach for \"{goal[:80]}\": {approach}",
                    source=f"task:{goal[:60]}",
                )

            _log.info(f"Learned patterns from successful task.")
        except Exception as e:
            _log.warning(f"Knowledge capture failed: {e}")

    # Emit task events via event bus
    try:
        from core.events import bus, TASK_COMPLETED, TASK_FAILED
        event_data = {
            "goal": goal, "app_name": app_name, "success": success,
            "steps_planned": result.steps_planned,
            "steps_completed": result.steps_completed,
            "total_time": result.total_time,
        }
        bus.emit(TASK_COMPLETED if success else TASK_FAILED, event_data)
    except Exception:
        pass

    # Discord webhook notifications (fire-and-forget)
    try:
        from core.discord_notify import notify_task_complete, notify_task_failed
        if success:
            step_types = [s.get("type", "?") for s in result.step_outcomes]
            notify_task_complete(
                goal=goal,
                time_s=result.total_time,
                actions=result.total_actions,
                steps=f"{result.steps_completed}/{result.steps_planned} ({' → '.join(step_types)})",
                app=app_name,
            )
        else:
            notify_task_failed(
                goal=goal,
                reason=result.failure_reason or notes,
                app=app_name,
            )
    except Exception as e:
        _log.debug(f"Discord notification failed (best-effort): {e}")
