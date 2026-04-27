"""Agent Orchestrator — StepExecutor and TaskResult.

The observe → think → act loop.  Delegates to:
  - agent.observation    — context building + action requests
  - agent.task_runner    — top-level run() entry point + post-task reflection
  - agent.planner        — goal decomposition + step classification
  - agent.action_dispatch — registry-based action execution
  - agent.chat_wait      — SSIM-based chat response detection
  - agent.blender_ops    — Blender script execution + visual verification
"""

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

import config
from log import get_logger

_log = get_logger("agent")

from core.license import get_demo_tracker
from agent.context_router import get_context_router
from agent.error_recovery import ErrorDiagnoser
from agent.actions import (
    check_safety,
    format_action_for_display,
    parse_action,
    should_confirm,
)
from agent.action_dispatch import execute_action
try:
    from core.audit_log import audit, audit_action
except ImportError:
    def audit(*a, **kw): pass
    def audit_action(*a, **kw): pass
from agent.planner import decompose_goal, classify_step, _call_planner
from agent.chat_wait import wait_for_chat_response
from agent.observation import (
    _build_observation,
    _request_action,
    _CHAT_APP_NAMES,
    _VERIFIABLE_APPS,
)
# Import blender_ops to register its action handlers into the dispatch registry
try:
    import addons.blender.ops  # noqa: F401
except ImportError:
    pass  # Blender add-on not installed
try:
    from desktop.controller import (
        find_window,
        get_accessibility_tree,
        launch_desktop_item,
        list_windows,
        press_key,
        wait_for_app_ready,
    )
except (ImportError, RuntimeError):
    find_window = get_accessibility_tree = launch_desktop_item = None
    list_windows = press_key = wait_for_app_ready = None
    _log.info("Desktop automation unavailable — agent runs in chat-only mode")

try:
    from vision.analyzer import (
        capture_screenshot,
        save_screenshot,
    )
except ImportError:
    capture_screenshot = save_screenshot = None
from apps.registry import get_module_by_window_title
from memory.store import MemoryStore

# Backward-compat: run() moved to agent.task_runner
from agent.task_runner import run  # noqa: F401


# Backward compatibility: re-export _classify_step for test_smoke.py
_classify_step = classify_step


# ---------------------------------------------------------------------------
# StepExecutor — the main orchestrator class
# ---------------------------------------------------------------------------

MAX_HISTORY = 20  # keep last N exchange pairs (N*2 messages)


@dataclass
class TaskResult:
    """Structured result returned by the orchestrator after a task."""
    goal: str
    app_name: str
    steps_planned: int = 0
    steps_completed: int = 0
    total_actions: int = 0
    total_time: float = 0.0
    aborted: bool = False
    failure_reason: str = ""
    step_outcomes: list = field(default_factory=list)  # [{desc, type, status, actions}]
    final_window_title: str = ""
    history: list = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.steps_planned == 0:
            return 0.0
        return self.steps_completed / self.steps_planned


class StepExecutor:
    """Executes a sequence of typed plan steps for a given goal.

    Each step has a 'type' that determines the execution strategy:
        launch    — open an app via smart launch or fallback to LLM
        interact  — general observe→think→act loop
        chat_wait — wait for chat AI response, then read it
    """

    def __init__(self, goal: str, app_name: str, app_module, memory: MemoryStore,
                 headless: bool = False, progress_callback=None):
        self.goal = goal
        self.app_name = app_name
        self._original_app_name = app_name  # immutable — used for chat_wait guard
        self.app_module = app_module
        self.memory = memory
        self.headless = headless  # skip confirmation prompts (API/daemon mode)
        self.diagnoser = ErrorDiagnoser(memory, app_name=app_name)
        self.history: list[dict] = []
        self.current_window = None
        self.app_launched = False
        self._total_actions = 0
        self._step_outcomes: list[dict] = []
        self._aborted = False
        self._failure_reason = ""
        self._auto_gen_attempted = False
        self._progress_cb = progress_callback  # optional (step_idx, total, desc, status)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, steps: list[dict]) -> TaskResult:
        """Execute all typed steps in sequence. Returns TaskResult."""
        start_time = time.time()
        
        # Check demo mode limits
        demo_tracker = get_demo_tracker()
        if not demo_tracker.can_execute_task():
            _log.warning("Demo mode task limit reached")
            self._aborted = True
            self._failure_reason = f"Demo mode limit: {demo_tracker.get_remaining_tasks()} tasks remaining. Upgrade to full version for unlimited tasks."
            
            return TaskResult(
                goal=self.goal,
                app_name=self.app_name,
                steps_planned=len(steps),
                steps_completed=0,
                total_actions=0,
                total_time=0.0,
                aborted=True,
                failure_reason=self._failure_reason,
                step_outcomes=[],
                final_window_title="",
                history=[],
            )

        for step_idx, step in enumerate(steps):
            desc = step["description"]
            stype = step["type"]
            _log.info(f"--- Step {step_idx + 1}/{len(steps)}: {desc} [{stype}] ---")
            if self._progress_cb:
                self._progress_cb(step_idx, len(steps), desc, "started")

            actions_before = self._total_actions
            if stype == "launch":
                self._execute_launch_step(step)
            elif stype == "chat_wait":
                self._execute_chat_wait_step(step)
            elif stype == "filesystem":
                self._execute_filesystem_step(step)
            else:
                self._execute_interact_step(step, step_idx)

            step_actions = self._total_actions - actions_before
            step_status = "aborted" if self._aborted else "completed"
            self._step_outcomes.append({
                "description": desc,
                "type": stype,
                "status": step_status,
                "actions": step_actions,
            })
            if self._progress_cb:
                self._progress_cb(step_idx, len(steps), desc, step_status)

            self._trim_history()

            if self._aborted:
                break

        elapsed = time.time() - start_time
        
        # Record task completion for demo mode tracking
        if not self._aborted:
            demo_tracker.record_task()
            remaining = demo_tracker.get_remaining_tasks()
            if remaining >= 0:
                _log.info(f"Demo mode: {remaining} tasks remaining in this session")
        
        _log.info(f"{'='*60}")
        _log.info(f"  OnyxKraken — Goal completed (or all steps attempted)")
        _log.info(f"  Time: {elapsed:.1f}s | Actions: {self._total_actions} | Steps: {len(self._step_outcomes)}/{len(steps)}")
        _log.info(f"{'='*60}")

        win_title = ""
        if self.current_window:
            try:
                win_title = self.current_window.window_text()
            except Exception as e:
                _log.debug(f"Could not read window title: {e}")

        # Post-task cleanup: close windows Onyx opened
        self._cleanup_windows()

        return TaskResult(
            goal=self.goal,
            app_name=self.app_name,
            steps_planned=len(steps),
            steps_completed=sum(1 for s in self._step_outcomes if s["status"] == "completed"),
            total_actions=self._total_actions,
            total_time=elapsed,
            aborted=self._aborted,
            failure_reason=self._failure_reason,
            step_outcomes=self._step_outcomes,
            final_window_title=win_title,
            history=list(self.history),
        )

    # ------------------------------------------------------------------
    # Step handlers
    # ------------------------------------------------------------------

    def _execute_launch_step(self, step: dict):
        """Handle a 'launch' type step."""
        if self.app_launched:
            _log.info(f"App already launched. Skipping.")
            return

        # Check for a verified internal tool that replaces this app
        if self._try_internal_tool_launch():
            _log.info(f"Launched internal tool. Moving to next step.")
            return

        if self._try_smart_launch():
            _log.info(f"App ready. Moving to next step.")
            return

        # Fallback: let the LLM figure it out via the interact loop
        self._execute_interact_step(step, 0)

    def _execute_filesystem_step(self, step: dict):
        """Handle a 'filesystem' type step — execute file/command operations directly.

        Uses the planner model to extract exact parameters, then executes
        without involving the vision model at all.
        """
        desc = step["description"]

        # Check for hardcoded Blender build recipe first
        if self._try_blender_recipe(desc):
            return

        home_dir = os.path.expanduser("~")
        desktop_dir = os.path.join(home_dir, "Desktop")

        extraction_prompt = (
            f"Extract the exact file operation from this step description.\n"
            f"System paths: Home={home_dir}, Desktop={desktop_dir}\n\n"
            f"Step: {desc}\n"
            f"Overall goal: {self.goal}\n\n"
            f"Respond with ONLY a JSON object, one of these formats:\n"
            f'{{"action": "write_file", "path": "C:\\\\full\\\\path\\\\file.txt", "content": "text to write"}}\n'
            f'{{"action": "read_file", "path": "C:\\\\full\\\\path\\\\file.txt"}}\n'
            f'{{"action": "run_command", "command": "dir C:\\\\Users"}}\n'
            f'{{"action": "search_files", "directory": "C:\\\\path", "pattern": "*.txt"}}\n'
            f'{{"action": "run_python", "code": "import math\\nprint(math.factorial(10))", "timeout": 10}}\n'
            f'{{"action": "blender_python", "code": "from onyx_bpy import *\\nbuild_simple_house()", "save_after": true, "verify_after": true, "goal": "description for visual check", "timeout": 60}}\n'
            f'{{"action": "blender_query", "code": "import bpy\\nfor o in bpy.data.objects: print(o.name, o.type)"}}\n'
            f"IMPORTANT: For ANY Blender/bpy/onyx_bpy/3D modeling task, use blender_python (NOT run_python).\n"
            f"The onyx_bpy toolkit is auto-imported in blender_python scripts.\n"
            f"Use REAL absolute paths. Output ONLY the JSON."
        )

        raw = _call_planner(extraction_prompt)
        parsed = parse_action(raw)

        if parsed is None:
            # Try direct JSON extraction with balanced brace matching
            try:
                start = raw.find("{")
                if start >= 0:
                    depth = 0
                    for i in range(start, len(raw)):
                        if raw[i] == "{":
                            depth += 1
                        elif raw[i] == "}":
                            depth -= 1
                            if depth == 0:
                                parsed = json.loads(raw[start:i + 1])
                                break
            except (json.JSONDecodeError, ValueError) as e:
                _log.debug(f"Could not extract file operation JSON: {e}")

        if parsed is None:
            _log.info(f"Could not extract file operation. Falling back to interact step.")
            self._execute_interact_step(step, 0)
            return

        act = parsed.get("action", "")
        _log.info(f"Filesystem operation: {act}")

        # Build a full action dict and execute
        action = {
            "thought": desc,
            "action": act,
            "target": parsed.get("path", parsed.get("directory", "")),
            "target_type": "",
            "fallback_coords": [0, 0],
            "params": {k: v for k, v in parsed.items() if k != "action"},
        }

        self._total_actions += 1
        result = execute_action(action)
        _log.info(f"Result: {result}")

        self._record_action(action, f"Filesystem operation result: {result}")

    def _execute_chat_wait_step(self, step: dict):
        """Handle a 'chat_wait' type step — wait for response, then read it.

        Uses SSIM screen change detection to wait for the response to appear
        and generation to finish, then hands off to the interact loop where
        the LLM can naturally read_screen, scroll, and compose replies.
        """
        # Guard: only use chat_wait if the TASK's original app is a known chat app.
        # Uses _original_app_name because self.app_name gets mutated by auto-detection.
        is_task_chat_app = self._original_app_name in _CHAT_APP_NAMES
        if (self.app_module is None
                or not is_task_chat_app
                or not getattr(self.app_module, "is_chat_app", False)
                or not hasattr(self.app_module, "get_response_wait_config")):
            _log.info(f"Not a chat app or no wait config. Treating as interact step.")
            self._execute_interact_step(step, 0)
            return

        wait_config = self.app_module.get_response_wait_config()

        # Phase 1: Wait for response via SSIM (no vision model needed)
        screenshot, status = wait_for_chat_response(wait_config)
        if screenshot is None:
            _log.info("No screen change detected. Falling back to interact loop.")

        if status.get("responded"):
            _log.info("Response detected via SSIM. Handing off to interact loop to read it.")
            self._record_action(
                {
                    "thought": "Chat response detected — screen stabilized",
                    "action": "wait",
                    "target": "",
                    "params": {"seconds": 0},
                },
                "The AI chatbot has FINISHED generating its response (confirmed by screen stability). "
                "The response is COMPLETE — do NOT check status indicators or icons. "
                "Look at the screenshot, read the visible text, then use 'done' with a summary.",
            )

        # Phase 2: Hand off to interact loop for reading + potential reply
        # Override step description to guide the LLM toward reading, not status-checking
        read_step = {
            "description": (
                "The AI chatbot has finished responding. Look at the screenshot and read "
                "the response text that is visible on screen. If you need to see more, "
                "use scroll (negative clicks) to scroll down. Once you can see the response, "
                "use the 'done' action with reason containing a summary of what the AI said. "
                "Do NOT use read_screen — just look at the screenshot and report done."
            ),
            "type": "interact",
        }
        self._execute_interact_step(read_step, 0)

    def _execute_interact_step(self, step: dict, step_idx: int):
        """Handle a general 'interact' type step via the observe→think→act loop."""
        desc = step["description"]
        last_action_key = None
        last_result = ""
        repeat_count = 0
        recovery_attempts = 0
        MAX_RECOVERY_ATTEMPTS = 2

        # Context router — prevents drift on long steps
        ctx_router = get_context_router()
        ctx_router.reset()

        for iteration in range(config.MAX_AGENT_STEPS):
            # Observe
            screenshot = capture_screenshot()
            save_screenshot(screenshot, f"step{step_idx + 1}_iter{iteration}")

            self._try_detect_window()

            observation, tree = _build_observation(
                self.current_window, screenshot, self.app_module,
            )

            # Context injection — enrich observation when deep into a step
            injection = ctx_router.get_context_injection(
                history=self.history,
                current_step=desc,
                app_name=self.app_name,
                last_result=last_result,
            )
            if injection:
                observation += injection

            # Think
            action = _request_action(
                observation=observation,
                current_step=desc,
                overall_goal=self.goal,
                screenshot_img=screenshot,
                history=self.history,
            )

            # Repeat-action detection with error recovery
            action_key = (
                action.get("action"),
                action.get("target"),
                str(action.get("params", {})),
            )
            if action_key == last_action_key:
                repeat_count += 1
                if repeat_count >= 2:
                    _log.info(f"Repeat detected ({repeat_count + 1}x). Diagnosing...")
                    diag = self.diagnoser.diagnose_stuck(
                        goal=self.goal, current_step=desc,
                        repeated_action=action, repeat_count=repeat_count + 1,
                        observation=observation,
                    )
                    _log.info(f"[ErrorRecovery] {diag['diagnosis']}")
                    _log.info(f"[ErrorRecovery] Suggestion: {diag['recovery']}")

                    alt = diag.get("alternative_action")
                    if alt and isinstance(alt, dict):
                        _log.info(f"[ErrorRecovery] Trying alternative: {alt.get('action', '?')}")
                        self._record_action(action, f"Stuck repeating. Recovery: {diag['recovery']}")
                        action = {
                            "thought": diag["recovery"],
                            "action": alt.get("action", "done"),
                            "target": alt.get("target", ""),
                            "target_type": alt.get("target_type", ""),
                            "fallback_coords": alt.get("fallback_coords", [0, 0]),
                            "params": alt.get("params", {}),
                        }
                        repeat_count = 0
                        last_action_key = None
                    else:
                        _log.info(f"No alternative found. Moving to next step.")
                        break
            else:
                repeat_count = 0
                last_action_key = action_key

            _log.info(f"Proposed action:")
            _log.info(f"  {format_action_for_display(action)}")

            # Safety check
            safety = check_safety(self.app_name, action)
            if safety == "block":
                _log.warning(f"  ⛔ BLOCKED by safety rules. Skipping.")
                audit_action(self.app_name, action, safety_result="block", executed=False)
                self._record_action(
                    action,
                    "That action was BLOCKED by safety rules. Choose a different approach.",
                )
                continue

            # Confirmation check (skipped in headless/API mode and for auto_confirm modules)
            _module_auto = getattr(self.app_module, "auto_confirm", False)
            if not self.headless and not _module_auto and should_confirm(self.app_name, action):
                print(f"\n  Confirm this action? [y/n/q] ", end="")
                choice = input().strip().lower()
                if choice == "q":
                    _log.info("User aborted.")
                    self._aborted = True
                    self._failure_reason = "User aborted"
                    return
                if choice != "y":
                    _log.info("Action skipped by user.")
                    audit_action(self.app_name, action, safety_result=safety, executed=False, result="user_rejected")
                    self._record_action(
                        action,
                        "User rejected this action. Try a different approach.",
                    )
                    continue

            # Act
            self._total_actions += 1
            if action["action"] in ("done", "fail"):
                _log.info(f"{execute_action(action)}")
                if action["action"] == "fail":
                    reason = action.get("params", {}).get("reason", "LLM reported failure")
                    _log.info(f"Failure reported. Diagnosing...")
                    diag = self.diagnoser.diagnose(
                        goal=self.goal, current_step=desc,
                        failed_action=action, error_message=reason,
                        recent_history=self.history, observation=observation,
                    )
                    _log.info(f"[ErrorRecovery] {diag['diagnosis']}")
                    _log.info(f"[ErrorRecovery] {diag['recovery']}")
                    self._narrate(f"⚠️ {diag['diagnosis'][:80]}")
                    self._narrate(f"Recovery: {diag['recovery'][:80]}")

                    if diag.get("should_retry") and diag.get("alternative_action") and recovery_attempts < MAX_RECOVERY_ATTEMPTS:
                        recovery_attempts += 1
                        _log.info(f"[ErrorRecovery] Attempting recovery ({recovery_attempts}/{MAX_RECOVERY_ATTEMPTS})...")
                        self._narrate(f"Retrying... (attempt {recovery_attempts}/{MAX_RECOVERY_ATTEMPTS})")
                        self._total_actions -= 1  # undo the fail count
                        self._record_action(action, f"Recovery suggested: {diag['recovery']}")
                        continue  # retry the loop with new context in history

                    if diag.get("skip_step"):
                        _log.info(f"Skipping step on recovery advice.")
                        break

                    _log.info("Aborting — no recovery available.")
                    self._aborted = True
                    self._failure_reason = reason
                break

            result = execute_action(action, window=self.current_window, tree=tree, app_module=self.app_module)
            _log.info(f"Result: {result}")
            audit_action(self.app_name, action, safety_result=safety, executed=True, result=result[:200])
            last_result = result  # feed to context router on next iteration
            ctx_router.tick()

            # Detect action-level failures and diagnose
            # For blender_python/blender_query, only flag non-zero exit codes — not substring matches
            # (bpy output contains words like 'rotation_euler' which falsely match 'error')
            _is_blender_script = action["action"] in ("blender_python", "blender_query")
            if _is_blender_script:
                _action_failed = "exit=1" in result or result.startswith("BLOCKED") or result.startswith("Blender script")
            else:
                _action_failed = any(word in result.lower() for word in ("failed", "could not", "error", "blocked", "not found"))
            if _action_failed:
                _log.info(f"Action result indicates a problem. Diagnosing...")
                diag = self.diagnoser.diagnose(
                    goal=self.goal, current_step=desc,
                    failed_action=action, error_message=result,
                    recent_history=self.history, observation=observation,
                )
                _log.info(f"[ErrorRecovery] {diag['diagnosis']}")
                _log.info(f"[ErrorRecovery] {diag['recovery']}")
                self._narrate(f"⚠️ {diag['diagnosis'][:80]}")
                self._narrate(f"Recovery: {diag['recovery'][:80]}")
                self._record_action(
                    action,
                    f"Action had issues: {result}. Recovery advice: {diag['recovery']}",
                )
                time.sleep(0.5)
                continue

            # Post-action verification for type actions
            if (action["action"] == "type"
                    and self.current_window is not None
                    and self.app_name in _VERIFIABLE_APPS):
                typed_text = action.get("params", {}).get("text", "")
                if typed_text and len(typed_text) <= 200:
                    time.sleep(0.2)
                    try:
                        verify_tree = get_accessibility_tree(self.current_window, max_depth=3)
                        all_text = " ".join(el["name"] for el in verify_tree).lower()
                        all_text = re.sub(r'\s+', ' ', all_text)
                        check_text = re.sub(r'\s+', ' ', typed_text).strip().lower()
                        if check_text and check_text not in all_text:
                            _log.warning(f"Typed text not found in accessibility tree. May need retry.")
                            result += " [VERIFY: text may not have been typed correctly — check screenshot]"
                    except Exception as e:
                        _log.debug(f"Post-type verification failed (best-effort): {e}")

            # Chat app: auto-press Enter after typing to send the message
            if (action["action"] == "type"
                    and self.app_module is not None
                    and getattr(self.app_module, "is_chat_app", False)):
                time.sleep(0.3)
                press_key("enter")
                result += " [Enter was automatically pressed to send the message]"
                _log.info(f"Auto-pressed Enter to send message (chat app).")

            self._record_action(
                action,
                f"Action executed. Result: {result}. Take a moment to observe the new state.",
            )

            # Brief pause for the UI to update
            time.sleep(0.5)
        else:
            _log.info(f"Step hit iteration limit ({config.MAX_AGENT_STEPS}). Moving on.")

    # ------------------------------------------------------------------
    # Smart launch
    # ------------------------------------------------------------------

    # Patterns that indicate a 3D build request (for LLM fallback)
    _3D_BUILD_HINTS = ("blender", "3d model", "3d scene", "build a ", "create a ",
                       "model a ", "make a ", "render a ", "sculpt a ")
    _MAX_BUILD_ITERATIONS = 3

    def _narrate(self, text: str, phase: str = "building"):
        """Emit a narration message to the progress callback and log."""
        _log.info(f"[narrate] {text}")
        if self._progress_cb:
            self._progress_cb(0, 0, text, "narration")

    def _try_blender_recipe(self, step_desc: str) -> bool:
        """Check if the step/goal matches a Blender build recipe.

        Phase 3a: tries hardcoded recipes first.
        Phase 3b: falls back to LLM-generated build plans for unrecognized objects.
        Phase 3c: iteration loop — if verification fails, refine and retry.

        Returns True if a recipe was found and executed.
        """
        try:
            from addons.blender.pipeline import (
                match_recipe, get_recipe_action, generate_build_plan,
                refine_build_plan, parse_verify_result,
            )
        except ImportError:
            return False

        # Phase 3a: check hardcoded recipes
        recipe = match_recipe(step_desc) or match_recipe(self.goal)

        # Phase 3b: if no recipe, check if it looks like a 3D request and generate
        if recipe is None:
            combined = (step_desc + " " + self.goal).lower()
            is_3d = any(hint in combined for hint in self._3D_BUILD_HINTS)
            if not is_3d:
                return False
            self._narrate("Designing a build plan...")
            _log.info(f"No recipe match. Generating build plan via LLM for: {self.goal[:60]}")
            recipe = generate_build_plan(self.goal)
            if recipe is None:
                return False
        else:
            self._narrate(f"Found a recipe: {recipe.description}")

        # Execute with iteration loop (Phase 3c)
        current_script = recipe.script
        for iteration in range(self._MAX_BUILD_ITERATIONS):
            label = recipe.name if iteration == 0 else f"iteration_{iteration}"
            _log.info(f"Build attempt {iteration + 1}/{self._MAX_BUILD_ITERATIONS}: {label}")

            if iteration == 0:
                self._narrate("Setting up materials and geometry...")
            else:
                self._narrate(f"Refining the build (attempt {iteration + 1})...")

            action = get_recipe_action(recipe)
            self._total_actions += 1

            self._narrate("Running Blender script...")
            result = execute_action(action)
            _log.info(f"Build result: {result[:200] if result else '(none)'}")
            self._record_action(action, f"Build recipe result: {result}")

            # Phase 3c: check verification and iterate if needed
            vr = parse_verify_result(result or "")
            if not vr["needs_iteration"] or iteration >= self._MAX_BUILD_ITERATIONS - 1:
                if vr["needs_iteration"]:
                    self._narrate(f"Build scored {vr['score']}/10. Moving on.")
                    _log.info(f"Build still needs work after {iteration + 1} attempts. Moving on.")
                else:
                    self._narrate(f"Build complete! Score: {vr['score']}/10")
                    _log.info(f"Build passed verification (score: {vr['score']}/10)")
                break

            self._narrate(f"Score: {vr['score']}/10 — analyzing feedback...")
            _log.info(f"Build needs work (score: {vr['score']}/10). Refining...")
            refined = refine_build_plan(
                original_script=current_script,
                feedback=vr["feedback"],
                goal=self.goal,
                attempt=iteration + 1,
            )
            if refined is None:
                self._narrate("Could not refine further. Keeping current result.")
                _log.info("Could not refine build plan. Stopping iteration.")
                break
            recipe = refined
            current_script = refined.script

        return True

    def _try_internal_tool_launch(self) -> bool:
        """Check for a verified self-built tool that replaces the target app.

        Returns True if an internal tool was launched successfully.
        """
        try:
            from core.toolsmith import find_internal_replacement, launch_tool
        except ImportError:
            return False

        tool = find_internal_replacement(self.app_name)
        if tool is None:
            # Also check the goal text for app names
            goal_lower = self.goal.lower()
            from core.toolsmith import list_tools
            for t in list_tools():
                if not t.is_verified:
                    continue
                for repl in t.replaces:
                    if repl.lower() in goal_lower:
                        tool = t
                        break
                if tool:
                    break

        if tool is None:
            return False

        _log.info(f"Found internal tool: {tool.display_name} (replaces {', '.join(tool.replaces)})")
        proc = launch_tool(tool.name)
        if proc is None:
            _log.warning(f"Internal tool launch failed, falling back to external app.")
            return False

        # Wait for the tool window to appear
        time.sleep(1.5)
        if tool.window_title:
            self.current_window = find_window(tool.window_title)
        if self.current_window is None:
            # Try a broader search
            self.current_window = find_window(tool.display_name)
        if self.current_window:
            _log.info(f"Internal tool window found: {self.current_window.window_text()}")
        else:
            _log.info(f"Internal tool launched but window not found yet (may still be loading)")

        self.app_launched = True
        self._record_action(
            {
                "thought": f"Using self-built tool: {tool.display_name}",
                "action": "launch_tool",
                "target": tool.name,
                "params": {},
            },
            f"Launched internal tool: {tool.display_name}",
        )
        return True

    def _try_smart_launch(self) -> bool:
        """Attempt to launch the app via shortcut or command.

        Returns True if the app was launched and its window found.
        """
        if self.app_module is None:
            return False

        launched = False
        launch_label = ""

        # Method 1: desktop shortcut (.lnk)
        shortcut_name = getattr(self.app_module, "desktop_shortcut", None)
        if shortcut_name:
            _log.info(f"Smart launch: opening desktop shortcut '{shortcut_name}'")
            proc = launch_desktop_item(shortcut_name)
            if proc:
                launched = True
                launch_label = f"desktop shortcut: {shortcut_name}"

        # Method 2: direct command (exe) — no shell=True
        if not launched and self.app_module.launch_command:
            cmd = self.app_module.launch_command
            _log.info(f"Smart launch: running '{cmd}' directly")
            try:
                subprocess.Popen([cmd])
                launched = True
                launch_label = cmd
            except Exception as e:
                _log.error(f"Smart launch command failed: {e}")

        if not launched:
            return False

        # Wait for window
        is_browser_app = shortcut_name is not None and self.app_module.launch_command is None
        wait_time = 5 if is_browser_app else 2
        _log.info(f"Waiting {wait_time}s for app to load...")
        time.sleep(wait_time)

        hint = self.app_module.window_title_hint
        self.current_window = find_window(hint)
        if not self.current_window:
            timeout = 15 if is_browser_app else config.APP_LOAD_TIMEOUT
            _log.info(f"Waiting for window '{hint}' (timeout={timeout}s)...")
            self.current_window = wait_for_app_ready(hint, timeout=timeout)

        if not self.current_window:
            _log.warning(f"App launched but window not found. Falling back to LLM.")
            return False

        # Use is_loaded() if available
        try:
            if not self.app_module.is_loaded(self.current_window):
                _log.info(f"Window found but app still loading, waiting 3s...")
                time.sleep(3)
        except Exception as e:
            _log.warning(f"is_loaded check failed: {e}")

        _log.info(f"Window found: {self.current_window.window_text()}")
        self.app_launched = True

        # Remember this launch method for next time
        self.memory.remember_launch(self.app_module.app_name, "smart_launch", launch_label)

        self._record_action(
            {
                "thought": f"Launched {self.app_module.app_name}",
                "action": "launch_app",
                "target": launch_label,
                "params": {},
            },
            f"App launched successfully. Window: {self.current_window.window_text()}",
        )
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    _window_maximized = False

    def _try_detect_window(self):
        """Try to find/update the active window and auto-detect app module."""
        if self.current_window is None:
            windows = list_windows()
            if windows:
                self.current_window = find_window(windows[0]["title"])

        # Auto-maximize for vision-only modules (need full screen for screenshots)
        if (self.current_window is not None
                and not self._window_maximized
                and self.app_module is not None
                and getattr(self.app_module, "vision_only", False)):
            try:
                self.current_window.maximize()
                import time; time.sleep(0.5)
                self._window_maximized = True
                _log.info("Auto-maximized window for vision-only module")
            except Exception as e:
                _log.warning(f"Failed to maximize window: {e}")

        if self.app_module is None and self.current_window is not None:
            try:
                title = self.current_window.window_text()
                detected = get_module_by_window_title(title)
                if detected:
                    self.app_module = detected
                    self.app_name = detected.app_name
                    _log.info(f"Auto-detected app module: {detected.app_name}")
                elif not self._auto_gen_attempted:
                    # Only auto-gen for non-system windows with relevant titles
                    skip_titles = ("taskbar", "desktop", "program manager",
                                   "start", "search", "cortana", "notification")
                    title_lower = title.lower()
                    is_system = any(s in title_lower for s in skip_titles)
                    if not is_system and len(title) > 2:
                        self._auto_gen_attempted = True
                        try:
                            from apps.auto_gen import generate_module
                            from apps.registry import _registry
                            generated = generate_module(self.current_window, title)
                            if generated:
                                self.app_module = generated
                                self.app_name = generated.app_name
                                _registry[generated.app_name.lower()] = generated
                                _log.info(f"Auto-generated and registered module: {generated.app_name}")
                        except Exception as e:
                            _log.warning(f"Auto-generation failed: {e}")
            except Exception as e:
                _log.warning(f"Window title detection failed: {e}")

    # Apps that should NOT be auto-closed after task completion
    _KEEP_OPEN_APPS = ("blender",)

    def _cleanup_windows(self):
        """Close windows that Onyx opened during this task.

        Skips apps in _KEEP_OPEN_APPS (e.g., Blender during live sessions).
        Only closes if Onyx launched the app (self.app_launched == True).
        """
        if not self.app_launched or self.current_window is None:
            return

        # Don't close apps that should stay open
        app_lower = self.app_name.lower()
        if any(keep in app_lower for keep in self._KEEP_OPEN_APPS):
            _log.info(f"Keeping {self.app_name} open (in keep-open list)")
            return

        try:
            title = self.current_window.window_text()
            _log.info(f"Closing window opened during task: {title}")
            self.current_window.close()
            time.sleep(0.5)
            _log.info(f"Closed: {title}")
        except Exception as e:
            _log.debug(f"Could not close window: {e}")

    def _record_action(self, action: dict, user_response: str):
        """Append an action/response pair to history."""
        self.history.append({"role": "assistant", "content": json.dumps(action)})
        self.history.append({"role": "user", "content": user_response})

    def _trim_history(self):
        """Keep history bounded to MAX_HISTORY exchange pairs."""
        max_msgs = MAX_HISTORY * 2
        if len(self.history) > max_msgs:
            self.history = self.history[-max_msgs:]


