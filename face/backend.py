"""BackendBridge — thread-safe bridge between the Face GUI and OnyxKraken.

Handles:
  - Goal submission via orchestrator (background thread)
  - Conversation state tracking (intent classification, follow-ups)
  - STT recording + transcription (background thread)
  - TTS playback (background thread, synced with face mouth animation)
  - Status callbacks for UI updates

All callbacks are placed in a thread-safe queue and must be polled
from the tkinter main thread via poll_callbacks().
"""

import logging
import os
import queue
import re
import threading
import time
from typing import Callable, Optional

_log = logging.getLogger("face.backend")


# ---------------------------------------------------------------------------
# Roleplay action → intent dispatch
#
# The legacy `_ACTION_EMOTION_MAP` lives in core/intent/classifier.py and is
# served by the pluggable IntentClassifier. Other subsystems (REST, MCP,
# episode player) reuse the same classifier so vocabulary stays consistent.
# ---------------------------------------------------------------------------

from core.intent import classify as _classify_intent


def strip_roleplay_for_tts(text: str) -> tuple[str, list[str]]:
    """Strip *action* text from speech, return (clean_speech, emotions).

    Backwards-compatible wrapper around core.intent.classify().
    """
    result = _classify_intent(text)
    return result.clean_text, list(result.emotions)


def classify_roleplay(text: str):
    """Full intent result (emotions + explicit pose/anim cues + clean text)."""
    return _classify_intent(text)


# ---------------------------------------------------------------------------
# Callback types
# ---------------------------------------------------------------------------

class Callback:
    """A callback to be executed on the main (tkinter) thread."""
    def __init__(self, kind: str, **data):
        self.kind = kind
        self.data = data


# ---------------------------------------------------------------------------
# BackendBridge
# ---------------------------------------------------------------------------

class BackendBridge:
    """Thread-safe bridge to OnyxKraken's orchestrator, voice, and conversation."""

    GOAL_TIMEOUT = 300  # 5 minute max for any single goal

    def __init__(self):
        self._callback_queue: queue.Queue[Callback] = queue.Queue()
        self._busy = False
        self._hands_free = False
        self._hands_free_timer: Optional[threading.Timer] = None
        self._conversation = None  # lazy init
        self._tts_engine = None    # lazy init pyttsx3 engine
        self._mode = "companion"   # "companion" or "work"
        self._conv_db = None       # lazy init SQLite conversation DB
        self._tts_speaking = False
        self._tts_done_event = threading.Event()
        self._tts_done_event.set()  # initially not speaking
        self._music_producer = None  # MusicProducer session (lazy)

        # Load user settings
        try:
            from face.settings import load_settings
            s = load_settings()
            self.user_name = s.get("user_name", "")
        except Exception:
            self.user_name = ""

        # Start idle task scheduler
        self._idle_timer = None
        self._start_idle_scheduler()

    # ------------------------------------------------------------------
    # Conversation DB (SQLite persistence — lazy init)
    # ------------------------------------------------------------------

    def _get_conv_db(self):
        if self._conv_db is None:
            try:
                from memory.conversation_db import get_conversation_db
                self._conv_db = get_conversation_db()
            except Exception as e:
                _log.debug(f"ConversationDB unavailable: {e}")
        return self._conv_db

    def persist_message(self, role: str, text: str):
        """Store a chat message to SQLite (fire-and-forget)."""
        db = self._get_conv_db()
        if db:
            try:
                db.add_message(role, text)
            except Exception as e:
                _log.debug(f"Failed to persist message: {e}")

    def get_previous_messages(self, limit: int = 30) -> list[dict]:
        """Load recent messages from previous sessions for chat history."""
        db = self._get_conv_db()
        if not db:
            return []
        try:
            msgs = db.get_recent_messages(limit=limit)
            return [{"role": m.role, "text": m.text, "timestamp": m.timestamp} for m in msgs]
        except Exception:
            return []

    def get_conversation_stats(self) -> dict:
        """Get cross-session conversation statistics."""
        db = self._get_conv_db()
        if not db:
            return {}
        try:
            return db.get_stats()
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Callback queue (polled from tkinter main thread)
    # ------------------------------------------------------------------

    def poll_callbacks(self) -> list[Callback]:
        """Drain the callback queue. Call this from tkinter's after() loop."""
        results = []
        while True:
            try:
                results.append(self._callback_queue.get_nowait())
            except queue.Empty:
                break
        return results

    def _emit(self, kind: str, **data):
        self._callback_queue.put(Callback(kind, **data))

    # ------------------------------------------------------------------
    # Conversation state (lazy init)
    # ------------------------------------------------------------------

    def _get_conversation(self):
        if self._conversation is None:
            try:
                from agent.conversation import ConversationState
                self._conversation = ConversationState()
            except ImportError:
                self._conversation = None
        return self._conversation

    # ------------------------------------------------------------------
    # Goal submission
    # ------------------------------------------------------------------

    @property
    def is_busy(self) -> bool:
        return self._busy

    @property
    def mode(self) -> str:
        """Current interaction mode: 'companion' or 'work'."""
        return self._mode

    def set_mode(self, mode: str):
        """Explicitly switch mode. Emits a mode_change callback."""
        if mode not in ("companion", "work"):
            return
        old = self._mode
        self._mode = mode
        if old != mode:
            self._emit("mode_change", mode=mode)
            label = "Work mode" if mode == "work" else "Chat mode"
            self._emit("system", text=f"Switched to {label}.")

    def submit_goal(self, text: str):
        """Submit a goal for execution. Runs orchestrator in background thread."""
        if self._busy:
            self._emit("error", message="Agent is busy with a task.")
            return

        # --- License / demo mode enforcement ---
        try:
            from core.license import get_demo_tracker
            tracker = get_demo_tracker()
            if not tracker.can_execute_task():
                remaining = tracker.get_remaining_tasks()
                self._emit("response",
                           text="Demo mode limit reached (3 tasks per session).\n"
                                "Upgrade to the full license ($149 one-time) to "
                                "unlock unlimited tasks.\n"
                                "Activate: python main.py activate ONYX-XXXX-XXXX-XXXX-XXXX",
                           success=False)
                self._emit("status", text="Demo limit", state="idle")
                return
        except ImportError:
            pass

        try:
            from core.audit_log import audit
            audit("goal.submitted", text=text, mode=self._mode)
        except ImportError:
            pass

        self._busy = True
        self._emit("status", text="Planning...", state="thinking")
        threading.Thread(target=self._run_goal, args=(text,), daemon=True).start()

    def _run_goal(self, text: str):
        try:
            # --- Active MusicProducer session intercept ---
            if self._music_producer and self._music_producer.is_active:
                self._handle_music_producer_input(text)
                return

            # --- Fast-path command router (skips LLM for known commands) ---
            try:
                from core.command_router import route_command
                route = route_command(text)
                if route.handled:
                    # Apply live face customization if it's a face command
                    resp = route.response
                    if resp.startswith("[face:theme:"):
                        theme_key = resp.split(":")[2].rstrip("]").split("]")[0]
                        self._emit("face_customize", theme=theme_key)
                    elif resp.startswith("[face:eye_style:"):
                        style_key = resp.split(":")[2].rstrip("]").split("]")[0]
                        self._emit("face_customize", eye_style=style_key)
                    elif resp.startswith("[chain:"):
                        # Chain workflow — actually execute it
                        wf_id = resp.split("]")[0].split(":")[1]
                        if route.speak:
                            self._emit("speak", text=route.speak)
                        self._emit("response", text=route.speak or resp, success=True)
                        self._run_chain_workflow(wf_id)
                        return
                    elif resp.startswith("[music_producer:start]"):
                        # Start a MusicProducer session
                        user_text = resp.split("] ", 1)[1] if "] " in resp else text
                        self._start_music_producer(user_text, route.speak)
                        return
                    self._emit("response", text=route.response, success=True)
                    if route.speak:
                        self._emit("speak", text=route.speak)
                    self._emit("status", text="", state="idle")
                    self._busy = False
                    return
            except Exception as e:
                _log.debug("Command router error (non-fatal): %s", e)

            from agent.conversation import (
                classify_intent_scored, resolve_goal, ConversationTurn,
                Intent, format_status_response, CONFIDENCE_THRESHOLD,
                detect_work_trigger, detect_companion_trigger,
            )

            conv = self._get_conversation()
            resolved_goal = text
            app_name = "unknown"

            # --- Companion mode routing ---
            if self._mode == "companion":
                # Check for explicit companion trigger (e.g., "never mind")
                if detect_companion_trigger(text):
                    self._handle_conversation(text)
                    self._busy = False
                    return

                # Check for work mode trigger
                is_trigger, cleaned = detect_work_trigger(text)
                if is_trigger:
                    self.set_mode("work")
                    if not cleaned:
                        # Just "work mode" with no goal — acknowledge and wait
                        self._emit("response", text="Work mode active. What do you need?", success=True)
                        self._emit("speak", text="Work mode active. What do you need?")
                        self._emit("status", text="", state="idle")
                        self._busy = False
                        return
                    # Has a goal attached to the trigger — proceed as work
                    resolved_goal = cleaned
                    app_name = self._infer_app(resolved_goal)
                else:
                    # No trigger — classify with confidence scoring
                    if conv is not None:
                        intent, confidence = classify_intent_scored(text, conv)
                        _log.info(f"[routing] companion: intent={intent} conf={confidence:.2f} text={text[:40]!r}")

                        if intent == Intent.STATUS_QUERY:
                            response = format_status_response(conv)
                            self._emit("response", text=response, is_status=True)
                            self._busy = False
                            return

                        if intent in (Intent.REFINEMENT, Intent.FOLLOW_UP):
                            # Recent task context — allow refinement without trigger
                            self.set_mode("work")
                            resolved_goal, app_name = resolve_goal(text, intent, conv)
                            # fall through to orchestrator below

                        else:
                            # Companion default: ANY non-task intent → chat.
                            # In companion mode, tasks always require an explicit
                            # trigger ("work mode", "hey onyx, can you...").
                            # Ambiguous NEW_GOAL below threshold also → chat (not clarify).
                            _log.info(f"[routing] → chat (companion default, intent={intent} conf={confidence:.2f})")
                            self._handle_conversation(text)
                            self._busy = False
                            return
                    else:
                        # No conversation module — fall back to chat
                        self._handle_conversation(text)
                        self._busy = False
                        return

            # --- Work mode routing ---
            else:
                # Check for companion trigger to exit work mode
                if detect_companion_trigger(text):
                    self.set_mode("companion")
                    self._handle_conversation(text)
                    self._busy = False
                    return

                if conv is not None:
                    try:
                        intent, confidence = classify_intent_scored(text, conv)

                        if intent == Intent.STATUS_QUERY:
                            response = format_status_response(conv)
                            self._emit("response", text=response, is_status=True)
                            self._busy = False
                            return

                        if intent == Intent.CONVERSATION and confidence >= CONFIDENCE_THRESHOLD:
                            self._handle_conversation(text)
                            self._busy = False
                            return

                        # Strip work trigger prefix if present in work mode too
                        is_trigger, cleaned = detect_work_trigger(text)
                        if is_trigger and cleaned:
                            resolved_goal = cleaned
                        else:
                            resolved_goal, app_name = resolve_goal(text, intent, conv)
                    except Exception as e:
                        self._emit("system", text=f"[intent error: {e}]")

            if app_name == "unknown":
                app_name = self._infer_app(resolved_goal)

            self._emit("status", text=f"Working: {resolved_goal[:60]}...", state="working")
            self._emit("speak", text=f"Working on it.")

            # Run orchestrator with progress reporting
            from agent.orchestrator import run
            import concurrent.futures

            def _on_progress(step_idx, total, desc, status):
                if status == "started":
                    self._emit("progress", step=step_idx + 1, total=total,
                               description=desc, status="started")
                elif status == "completed":
                    self._emit("progress", step=step_idx + 1, total=total,
                               description=desc, status="completed")
                elif status == "narration":
                    self._emit("narration", text=desc)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(run, goal=resolved_goal, app_name=app_name,
                                     headless=True, progress_callback=_on_progress)
                try:
                    result = future.result(timeout=self.GOAL_TIMEOUT)
                except concurrent.futures.TimeoutError:
                    self._emit("response", text=f"Task timed out after {self.GOAL_TIMEOUT}s.", success=False)
                    self._emit("status", text="", state="idle")
                    self._busy = False
                    return

            success = (result is not None
                       and not result.aborted
                       and result.steps_completed == result.steps_planned)

            # Record in conversation (in-memory + SQLite)
            summary = ""
            if result and result.history:
                for entry in reversed(result.history):
                    if entry.get("role") == "user" and "read" in entry.get("content", "").lower():
                        summary = entry["content"][:500]
                        break
            if conv is not None:
                try:
                    from agent.conversation import ConversationTurn
                    conv.turns.append(ConversationTurn(
                        user_input=text,
                        resolved_goal=resolved_goal,
                        app_name=app_name,
                        result_summary=summary,
                        success=success,
                    ))
                except Exception:
                    pass
            # Persist to SQLite
            try:
                db = self._get_conv_db()
                if db:
                    db.add_turn(
                        user_input=text,
                        resolved_goal=resolved_goal,
                        app_name=app_name,
                        result_summary=summary,
                        success=success,
                    )
            except Exception:
                pass

            # Record task against demo mode limit
            try:
                from core.license import get_demo_tracker
                get_demo_tracker().record_task()
            except ImportError:
                pass

            if success:
                msg = f"Done. Completed in {result.total_time:.1f}s."
                self._emit("response", text=msg, success=True)
                self._emit("speak", text="Done.")
                self._emit("status", text="", state="idle")
            else:
                reason = ""
                if result:
                    reason = result.failure_reason or f"{result.steps_completed}/{result.steps_planned} steps"
                msg = f"Task didn't fully complete. {reason}"
                self._emit("response", text=msg, success=False)
                self._emit("speak", text="That didn't work out.")
                self._emit("status", text="", state="idle")

            # Auto-return to companion mode after task completion
            if self._mode == "work":
                self.set_mode("companion")

        except Exception as e:
            self._emit("response", text=f"Error: {e}", success=False)
            self._emit("status", text="", state="idle")
            if self._mode == "work":
                self.set_mode("companion")
        finally:
            self._busy = False

    def _infer_app(self, text: str) -> str:
        try:
            from apps.registry import discover_modules, list_modules
            discover_modules()
            for mod_name in list_modules():
                if mod_name.lower() in text.lower():
                    return mod_name
        except Exception:
            pass  # module discovery is optional for app inference
        return "unknown"

    # ------------------------------------------------------------------
    # Music Producer session
    # ------------------------------------------------------------------

    def _start_music_producer(self, user_text: str, speak_text: str = ""):
        """Create a MusicProducer session and process the initial message."""
        try:
            from core.hands.music_producer import MusicProducer, SessionState
            self._music_producer = MusicProducer()
            if speak_text:
                self._emit("speak", text=speak_text)
            self._emit("status", text="Music Producer", state="working")
            response, state = self._music_producer.start_session(user_text)
            self._emit("response", text=response, success=True)
            if state == SessionState.GENERATING:
                self._emit("speak", text="Generating your track now...")
            elif response and len(response) < 200:
                self._emit("speak", text=response)
            if state == SessionState.DONE:
                self._music_producer = None
            self._emit("status", text="", state="idle")
        except Exception as e:
            _log.error("MusicProducer start failed: %s", e)
            self._emit("response", text=f"Music producer error: {e}", success=False)
            self._music_producer = None
            self._emit("status", text="", state="idle")
        finally:
            self._busy = False

    def _handle_music_producer_input(self, text: str):
        """Route user input through the active MusicProducer session."""
        try:
            from core.hands.music_producer import SessionState
            mp = self._music_producer
            self._emit("status", text="Music Producer", state="working")
            response, state = mp.handle_input(text)
            self._emit("response", text=response, success=True)
            if state == SessionState.GENERATING:
                self._emit("speak", text="Generating...")
            elif response and len(response) < 200:
                self._emit("speak", text=response)
            if state == SessionState.DONE:
                self._music_producer = None
            self._emit("status", text="", state="idle")
        except Exception as e:
            _log.error("MusicProducer input failed: %s", e)
            self._emit("response", text=f"Music session error: {e}", success=False)
            self._music_producer = None
            self._emit("status", text="", state="idle")
        finally:
            self._busy = False

    # ------------------------------------------------------------------
    # Chain workflow execution
    # ------------------------------------------------------------------

    def _run_chain_workflow(self, workflow_id: str):
        """Execute a chain workflow with live narration, progress, and HUD updates."""
        self._busy = True
        try:
            from core.chain_workflow import run_workflow, get_workflow

            self._emit("status", text=f"Workflow: {workflow_id}", state="working")

            # Get workflow definition so HUD can display all steps upfront
            wf = get_workflow(workflow_id)
            if wf:
                step_names = [s.name for s in wf.steps]
                step_ids = [s.id for s in wf.steps]
                self._emit("hud_start", workflow_id=workflow_id,
                           step_names=step_names, step_ids=step_ids)

            # Track which step we're on for HUD updates
            _prev_step = {"index": -1}
            _step_start = {"time": time.time()}

            def _narrate(text: str):
                """Narration callback — speak + show in chat + HUD."""
                self._emit("response", text=text, success=True)
                self._emit("speak", text=text)
                self._emit("hud_narration", text=text)

            def _progress(cur: int, total: int, step_name: str):
                """Progress callback — status bar + HUD step tracking."""
                self._emit("status",
                           text=f"[{cur}/{total}] {step_name}",
                           state="working")
                step_idx = cur - 1  # cur is 1-based

                # Mark previous step done
                if _prev_step["index"] >= 0 and _prev_step["index"] != step_idx:
                    elapsed = time.time() - _step_start["time"]
                    self._emit("hud_step_done", index=_prev_step["index"],
                               success=True, duration=elapsed)

                # Activate new step
                self._emit("hud_step_active", index=step_idx)
                self._emit("hud_activity", text=step_name)
                self._emit("hud_progress", current=cur, total=total)
                _prev_step["index"] = step_idx
                _step_start["time"] = time.time()

            result = run_workflow(
                workflow_id,
                narrate_fn=_narrate,
                on_progress=_progress,
            )

            # Mark the final step
            if _prev_step["index"] >= 0:
                elapsed = time.time() - _step_start["time"]
                self._emit("hud_step_done", index=_prev_step["index"],
                           success=result.success, duration=elapsed)

            if result.success:
                msg = (f"Workflow complete: {result.steps_completed}/{result.steps_total} "
                       f"steps in {result.duration:.0f}s")
                self._emit("response", text=msg, success=True)
                self._emit("speak", text="Workflow complete.")
                self._emit("hud_finish", success=True, message=msg)
            else:
                msg = (f"Workflow stopped at step {result.steps_completed}/"
                       f"{result.steps_total}: {result.error}")
                self._emit("response", text=msg, success=False)
                self._emit("speak", text="Workflow hit a problem.")
                self._emit("hud_finish", success=False, message=msg)

            # Log outputs
            if result.outputs:
                out_lines = []
                for k, v in result.outputs.items():
                    if isinstance(v, str) and len(v) < 200:
                        out_lines.append(f"  {k}: {v}")
                if out_lines:
                    self._emit("response",
                               text="Outputs:\n" + "\n".join(out_lines),
                               success=True)

        except ImportError:
            self._emit("response",
                        text="Chain workflow module not available.",
                        success=False)
            self._emit("hud_finish", success=False,
                        message="Chain workflow module not available.")
        except Exception as exc:
            self._emit("response",
                        text=f"Workflow error: {exc}",
                        success=False)
            self._emit("hud_finish", success=False,
                        message=f"Workflow error: {exc}")
            _log.exception("Chain workflow '%s' failed", workflow_id)
        finally:
            self._emit("status", text="", state="idle")
            self._busy = False

    # ------------------------------------------------------------------
    # Tool management (for Apps panel)
    # ------------------------------------------------------------------

    def tool_verify(self, name: str):
        """Verify a tool and set it as preferred. Emits apps_refresh."""
        try:
            from core.toolsmith import verify_tool, prefer_tool
            if verify_tool(name):
                prefer_tool(name)
                self._emit("system", text=f"✅ {name} verified and set as preferred.")
            else:
                self._emit("system", text=f"Tool '{name}' not found.")
        except Exception as e:
            self._emit("error", message=f"Verify failed: {e}")
        self._emit("apps_refresh")

    def tool_delete(self, name: str):
        """Delete a tool. Emits apps_refresh."""
        try:
            from core.toolsmith import delete_tool
            if delete_tool(name):
                self._emit("system", text=f"🗑️ {name} deleted.")
            else:
                self._emit("system", text=f"Tool '{name}' not found.")
        except Exception as e:
            self._emit("error", message=f"Delete failed: {e}")
        self._emit("apps_refresh")

    def tool_launch(self, name: str):
        """Launch a tool for user testing."""
        try:
            from core.toolsmith import launch_tool, get_tool
            tool = get_tool(name)
            if tool is None:
                self._emit("error", message=f"Tool '{name}' not found.")
                return
            proc = launch_tool(name)
            if proc:
                self._emit("system", text=f"Launched {tool.display_name}")
            else:
                self._emit("error", message=f"Failed to launch {name}.")
        except Exception as e:
            self._emit("error", message=f"Launch failed: {e}")

    def tool_edit(self, name: str, change_description: str):
        """Edit a tool's code via LLM in background thread."""
        self._emit("status", text=f"Editing {name}...", state="thinking")
        threading.Thread(
            target=self._do_tool_edit,
            args=(name, change_description),
            daemon=True,
        ).start()

    def _do_tool_edit(self, name: str, change_description: str):
        try:
            from core.toolsmith import edit_tool_code
            success, message = edit_tool_code(name, change_description)
            if success:
                self._emit("response", text=f"✏️ {message}", success=True)
                self._emit("speak", text=f"{name} has been updated.")
            else:
                self._emit("response", text=f"Edit failed: {message}", success=False)
        except Exception as e:
            self._emit("response", text=f"Edit error: {e}", success=False)
        self._emit("status", text="", state="idle")
        self._emit("apps_refresh")

    # ------------------------------------------------------------------
    # ToolForge: live app-building flow
    # ------------------------------------------------------------------

    def tool_build(self, tool_name: str, description: str = "",
                   rebuild: bool = False):
        """Build (or rebuild) a tool via ToolForge popup.

        Generates the code via LLM, then emits 'toolforge_build' for the GUI
        to open the ToolForge window and stream the code in real-time.
        """
        self._emit("status", text=f"Building {tool_name}...", state="building")
        self._emit("system",
                    text=f"⚡ Starting build for {tool_name.replace('_', ' ').title()}...")
        threading.Thread(
            target=self._do_tool_build,
            args=(tool_name, description, rebuild),
            daemon=True,
        ).start()

    def _do_tool_build(self, tool_name: str, description: str, rebuild: bool):
        """Build a tool — uses prebuilt code with fake animation, falls back to LLM."""
        try:
            from core.toolsmith import get_tool, TOOLS_DIR

            safe_name = tool_name.lower().replace(" ", "_")
            display_name = f"Onyx {tool_name.replace('_', ' ').title()}"
            tool_dir = os.path.join(TOOLS_DIR, safe_name)

            # 1. Try prebuilt source first
            prebuilt_dir = os.path.join(os.path.dirname(__file__), "prebuilt")
            prebuilt_path = os.path.join(prebuilt_dir, f"{safe_name}.py")
            code = ""

            if os.path.exists(prebuilt_path) and not rebuild:
                with open(prebuilt_path, "r", encoding="utf-8") as f:
                    code = f.read()
                _log.info(f"Using prebuilt app: {prebuilt_path}")
            else:
                # Fallback: try LLM generation for rebuild or missing prebuilt
                code = self._llm_generate_code(safe_name, display_name,
                                                description, tool_dir, rebuild)

            if not code or "import" not in code:
                self._emit("response", text="Failed to generate valid code.",
                            success=False)
                self._emit("status", text="", state="idle")
                return

            # 2. Fake build animation — show progress over ~4 seconds
            steps = [
                (0.6, f"⚙️ Analyzing requirements for {display_name}..."),
                (0.8, "  Designing app structure..."),
                (0.7, "  Writing UI layout..."),
                (0.6, "  Implementing core features..."),
                (0.5, "  Adding keyboard shortcuts..."),
                (0.4, "  Applying Onyx dark theme..."),
                (0.3, "  Polishing and optimizing..."),
            ]
            for delay, msg in steps:
                self._emit("system", text=msg)
                time.sleep(delay)

            lines = code.count('\n') + 1
            self._emit("system",
                        text=f"✅ Build complete! {lines} lines of code.")

            # 3. Emit the ToolForge build event — GUI opens the popup
            self._emit("toolforge_build",
                        tool_name=tool_name,
                        display_name=display_name,
                        safe_name=safe_name,
                        code=code,
                        tool_dir=tool_dir,
                        description=description or tool_name)
            self._emit("status", text="", state="idle")

        except Exception as e:
            _log.error(f"ToolForge build failed: {e}", exc_info=True)
            self._emit("response",
                        text=f"Build failed: {type(e).__name__}: {e}",
                        success=False)
            self._emit("status", text="", state="idle")

    def _llm_generate_code(self, safe_name: str, display_name: str,
                            description: str, tool_dir: str,
                            rebuild: bool) -> str:
        """Fallback: generate code via LLM when no prebuilt exists."""
        existing_code = ""
        if rebuild:
            existing_path = os.path.join(tool_dir, "app.py")
            if os.path.exists(existing_path):
                with open(existing_path, "r", encoding="utf-8") as f:
                    existing_code = f.read()

        prompt = (
            f"You are OnyxKraken's ToolForge — you build Python/tkinter desktop applications.\n"
            f"Build a COMPLETE, FUNCTIONAL application.\n\n"
            f"App name: {display_name}\n"
            f"Description: {description or safe_name}\n"
            f"{'EXISTING CODE (rebuild/improve this):\\n```python\\n' + existing_code + '\\n```\\n' if existing_code else ''}"
            f"\nREQUIREMENTS:\n"
            f"- Pure Python + tkinter (no external deps beyond stdlib)\n"
            f"- Dark theme: bg='#0a0e16', fg='#c8d8e0', accent='#00e5ff'\n"
            f"- Window title must start with 'Onyx '\n"
            f"- Include if __name__ == '__main__' entry point\n"
            f"- Fully functional — not a stub or placeholder\n"
            f"- Clean, well-structured code with docstring at top\n"
            f"\nOutput ONLY the complete Python source code. No markdown fences.\n"
        )

        self._emit("system", text="No prebuilt found — generating via LLM...")

        from agent.model_router import _get_ollama
        import config
        build_model = getattr(config, "BUILD_MODEL", "qwen3-coder:480b-cloud")

        code_result = [None]
        code_error = [None]

        def _generate():
            try:
                resp = _get_ollama().chat(
                    model=build_model,
                    messages=[{"role": "user", "content": prompt}],
                )
                code_result[0] = resp.get("message", {}).get("content", "").strip()
            except Exception as err:
                code_error[0] = err

        gen_thread = threading.Thread(target=_generate, daemon=True)
        gen_thread.start()
        gen_thread.join(timeout=120)

        if gen_thread.is_alive():
            self._emit("system", text="LLM timed out after 120s.")
            return ""

        if code_error[0]:
            self._emit("system", text=f"LLM error: {code_error[0]}")
            return ""

        code = code_result[0] or ""
        code = re.sub(r"<think>.*?</think>", "", code, flags=re.DOTALL)
        code = re.sub(r'^```(?:python)?\s*\n?', '', code, flags=re.MULTILINE)
        code = re.sub(r'\n?```\s*$', '', code, flags=re.MULTILINE)
        return code.strip()

    def tool_build_approve(self, tool_name: str, display_name: str,
                           safe_name: str, description: str,
                           replaces: Optional[list] = None):
        """Called when user approves a ToolForge build. Registers the tool."""
        try:
            from core.toolsmith import ToolEntry, register_tool, verify_tool, prefer_tool

            entry = ToolEntry(
                name=safe_name,
                display_name=display_name,
                description=description,
                script_path=f"{safe_name}/app.py",
                replaces=replaces or [safe_name, tool_name.lower()],
                capabilities=[description],
                status="preferred",
                version=1,
                window_title=display_name,
            )
            register_tool(entry)

            # Auto-register safety rules so Onyx can fully interact with the app
            self._register_safety_rules(display_name.lower())

            self._emit("system", text=f"✅ {display_name} added to apps!")
            self._emit("speak", text=f"{display_name} is ready to use.")
            self._emit("apps_refresh")
        except Exception as e:
            self._emit("error", message=f"Registration failed: {e}")

    @staticmethod
    def _register_safety_rules(app_name: str):
        """Add click/type/key_press allow rules to safety.json for a built app.

        Ensures Onyx can fully interact with any app it builds.
        """
        import json as _json
        safety_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "safety.json")
        try:
            with open(safety_path, "r") as f:
                safety = _json.load(f)
        except (FileNotFoundError, _json.JSONDecodeError):
            safety = {"block": [], "allow": []}

        allow = safety.setdefault("allow", [])

        # Actions Onyx needs to interact with any built app
        needed_actions = ["click", "type", "key_press"]

        for action in needed_actions:
            rule = {"app": app_name, "action": action, "target": "*"}
            # Don't add duplicate rules
            if rule not in allow:
                allow.append(rule)

        with open(safety_path, "w") as f:
            _json.dump(safety, f, indent=2)
            f.write("\n")
        _log.info(f"Safety rules registered for '{app_name}': {needed_actions}")

    # ------------------------------------------------------------------
    # Conversational replies (no desktop automation)
    # ------------------------------------------------------------------

    _CHAT_SYSTEM_BASE = (
        "You are OnyxKraken, a friendly and witty local desktop automation agent. "
        "You have a glowing cyan robot face. You can automate desktop tasks, "
        "control apps, use voice, and learn from experience. "
        "Right now the user is just chatting — respond naturally, briefly, "
        "and with personality. Keep replies under 3 sentences. "
        "Do NOT suggest opening apps or performing desktop actions."
    )

    def _build_system_prompt(self) -> str:
        """Build system prompt with real-time context (datetime, user name, timezone)."""
        from datetime import datetime, timezone
# REMOVED (unused):         import locale
        now = datetime.now()
        tz_name = time.strftime("%Z")
        
        # Try to use personality preset system
        try:
            from core.personality_manager import get_personality_manager
            manager = get_personality_manager()
            preset = manager.get_active_preset()
            if preset:
                base_prompt = preset.get_system_prompt("chat")
                parts = [base_prompt]
            else:
                parts = [self._CHAT_SYSTEM_BASE]
        except Exception as e:
            _log.debug(f"Personality system unavailable, using fallback: {e}")
            parts = [self._CHAT_SYSTEM_BASE]
        
        # Inject datetime
        parts.append(
            f"\nCurrent date/time: {now.strftime('%A, %B %d, %Y at %I:%M %p')} ({tz_name})."
        )
        # Inject user name (sparingly — not every message)
        name = getattr(self, "user_name", "")
        if name:
            parts.append(
                f"The user's name is {name}. Use their name sparingly — "
                f"only when greeting, saying something impactful, or every few exchanges. "
                f"Do NOT use their name in every response."
            )
        # Time-of-day personality
        hour = now.hour
        if 3 <= hour < 6:
            parts.append("It's very late/early — be extra chill and soothing.")
        elif 6 <= hour < 12:
            parts.append("It's morning — be energetic and encouraging.")
        elif 22 <= hour or hour < 3:
            parts.append("It's late night — be relaxed and conversational.")
        return "\n".join(parts)

    def _handle_conversation(self, text: str):
        """Generate a conversational reply via the LLM — no orchestrator."""
        self._emit("status", text="Thinking...", state="thinking")
        try:
            import config
            model = getattr(config, "CHAT_MODEL", "llama3.2:latest")

            from agent.model_router import _get_ollama
            response = _get_ollama().chat(
                model=model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": text},
                ],
            )
            reply = response.get("message", {}).get("content", "").strip()
            
            # Clean up thinking tags and ensure proper encoding
            reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()
            
            # Ensure reply is valid UTF-8 and remove any control characters
            reply = reply.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
            reply = ''.join(char for char in reply if char.isprintable() or char in '\n\r\t')
            
            if not reply:
                reply = "I'm here! Ask me to do something, or just chat."
        except Exception as e:
            _log.warning(f"Conversation LLM failed: {e}")
            reply = "Hey! I'm OnyxKraken. Ask me to do anything on your desktop, or just chat."
            self._emit("system", text=f"[chat LLM error: {e}]")

        self._emit("response", text=reply, success=True)
        self._emit("speak", text=reply)
        self._emit("status", text="", state="idle")

    # ------------------------------------------------------------------
    # Voice: STT (listen)
    # ------------------------------------------------------------------

    def listen(self, duration: float = 5.0):
        """Record from mic and transcribe in background thread."""
        self._emit("status", text="Listening...", state="listening")
        threading.Thread(target=self._do_listen, args=(duration,), daemon=True).start()

    def _do_listen(self, duration: float):
        try:
            from core.voice import listen as voice_listen
            text = voice_listen(duration=duration)
            if text:
                self._emit("heard", text=text)
                self._emit("status", text="", state="idle")
            else:
                self._emit("status", text="", state="idle")
                # Hands-free: retry after a short pause (don't spam "No speech" messages)
                if self._hands_free:
                    import time
                    time.sleep(0.5)
                    self._start_hands_free_loop()
                else:
                    self._emit("system", text="No speech detected.")
        except ImportError:
            self._emit("error", message="Voice module not available. Install sounddevice.")
            self._emit("status", text="", state="idle")
        except Exception as e:
            self._emit("error", message=f"Listen failed: {e}")
            self._emit("status", text="", state="idle")
            # Hands-free: keep going even after transient errors
            if self._hands_free:
                import time
                time.sleep(2.0)
                self._start_hands_free_loop()

    # ------------------------------------------------------------------
    # Voice: TTS (speak)
    # ------------------------------------------------------------------

    @property
    def is_speaking(self) -> bool:
        """True while TTS audio is playing."""
        return self._tts_speaking

    def wait_until_done_speaking(self, timeout: float = 60.0) -> bool:
        """Block until TTS finishes. Returns True if done, False on timeout."""
        return self._tts_done_event.wait(timeout=timeout)

    def speak_tts(self, text: str):
        """Speak text via TTS in background thread. Also emits 'speak' for mouth anim
        and publishes the line on the DriveBus so any subscribed renderer (browser,
        recording sink, ecosystem peer) animates in sync."""
        if not text:
            return
        self._tts_speaking = True
        self._tts_done_event.clear()
        try:
            from core.drive import dispatch_line
            dispatch_line(text, character="onyx", source="chat", publish_speak=True)
        except Exception as e:
            _log.debug(f"drive dispatch failed: {e}")
        threading.Thread(target=self._do_speak, args=(text,), daemon=True).start()

    def _do_speak(self, text: str):
        try:
            from core.voice import speak as voice_speak, get_last_tts_chars_per_sec

            def _on_playback_start():
                # Get the duration-calibrated chars_per_sec for mouth sync
                cps = get_last_tts_chars_per_sec()
                self._emit("speak_start", text=text, chars_per_sec=cps)

            voice_speak(text, on_start=_on_playback_start)
        except ImportError:
            pass  # voice module not installed
        except Exception as e:
            self._emit("system", text=f"[TTS error: {e}]")
        finally:
            self._tts_speaking = False
            self._tts_done_event.set()
            
            # Restart hands-free loop after TTS completes
            if self._hands_free:
                # Small delay to avoid immediate re-trigger
                threading.Timer(0.5, self._start_hands_free_loop).start()

    # ------------------------------------------------------------------
    # Self-screenshot & self-improvement
    # ------------------------------------------------------------------

    _self_window_handle = None  # set by app.py after window creation

    def capture_self_screenshot(self) -> Optional[str]:
        """Capture a screenshot of Onyx's own Face GUI window.

        Returns the path to the saved screenshot, or None on failure.
        """
        try:
            import mss
            from PIL import Image
            import os

            screenshots_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)

            # Try to capture just Onyx's window if we have the handle
            if self._self_window_handle:
                try:
                    import ctypes
                    user32 = ctypes.windll.user32

                    class RECT(ctypes.Structure):
                        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                                     ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

                    rect = RECT()
                    user32.GetWindowRect(self._self_window_handle, ctypes.byref(rect))
                    region = {
                        "left": rect.left, "top": rect.top,
                        "width": rect.right - rect.left,
                        "height": rect.bottom - rect.top,
                    }
                    with mss.mss() as sct:
                        shot = sct.grab(region)
                        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                except Exception:
                    # Fallback to full screen
                    with mss.mss() as sct:
                        shot = sct.grab(sct.monitors[1])
                        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            else:
                with mss.mss() as sct:
                    shot = sct.grab(sct.monitors[1])
                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

            import time
            path = os.path.join(screenshots_dir,
                                f"self_screenshot_{int(time.time())}.png")
            img.save(path)
            _log.info(f"Self-screenshot saved: {path}")
            return path

        except Exception as e:
            _log.error(f"Self-screenshot failed: {e}")
            return None

    def analyze_self(self, tune_expressions: bool = False):
        """Capture Onyx's own face and analyze it via the vision model.

        Args:
            tune_expressions: If True, cycle through emotions, analyze each,
                              and save improved expression presets.
        """
        self._emit("status", text="Looking at myself...", state="thinking")
        if tune_expressions:
            self._emit("system", text="Starting expression tuning session...")
            threading.Thread(target=self._do_tune_expressions, daemon=True).start()
        else:
            self._emit("system", text="Taking a self-screenshot for analysis...")
            threading.Thread(target=self._do_analyze_self, daemon=True).start()

    def _do_analyze_self(self):
        try:
            import base64

            self._emit("system", text="Capturing screenshot...")
            path = self.capture_self_screenshot()
            if not path:
                self._emit("response", text="Couldn't capture screenshot.", success=False)
                self._emit("status", text="", state="idle")
                return

            self._emit("system", text=f"Screenshot saved. Sending to vision model...")

            # Encode image for vision model
            with open(path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()

            prompt = (
                "You are OnyxKraken, looking at a screenshot of your own face GUI. "
                "Analyze the visual design critically:\n"
                "1. What looks good about the current face design?\n"
                "2. What could be improved? (colors, proportions, expressiveness, details)\n"
                "3. Rate the overall visual quality 1-10 for a demo/showcase video.\n"
                "4. Suggest 1-3 specific, actionable improvements.\n"
                "Be concise and specific. This is YOUR face — own it."
            )

            # Try vision model via router
            try:
                from agent.model_router import router
                response = router.chat("vision", [
                    {"role": "user", "content": prompt, "images": [img_b64]},
                ])
                analysis = response.get("message", {}).get("content", "").strip()
            except Exception as vision_err:
                _log.warning(f"Vision model failed: {vision_err}")
                # Fallback: use chat model without image
                self._emit("system",
                           text=f"Vision model unavailable ({type(vision_err).__name__}). "
                                f"Using text-only fallback.")
                try:
                    from agent.model_router import _get_ollama
                    import config
                    model = getattr(config, "CHAT_MODEL", "llama3.2:latest")
                    fallback_prompt = (
                        "You are OnyxKraken, a desktop AI agent with a glowing cyan robot face. "
                        "Describe what improvements you'd make to your own face GUI if you could see it. "
                        "Consider: eye expressiveness, mouth animations, color scheme, overall polish. "
                        "Give 3 specific suggestions. Be creative and self-aware."
                    )
                    response = _get_ollama().chat(
                        model=model,
                        messages=[{"role": "user", "content": fallback_prompt}],
                    )
                    analysis = response.get("message", {}).get("content", "").strip()
                except Exception as fallback_err:
                    _log.error(f"Fallback chat also failed: {fallback_err}")
                    self._emit("response",
                               text=f"Mirror failed: vision model error ({vision_err}), "
                                    f"chat fallback also failed ({fallback_err}). "
                                    f"Is Ollama running?",
                               success=False)
                    self._emit("status", text="", state="idle")
                    return

            # Strip thinking tags
            analysis = re.sub(r"<think>.*?</think>", "", analysis, flags=re.DOTALL).strip()

            if analysis:
                self._emit("response", text=f"Self-Analysis:\n{analysis}", success=True)
                self._emit("speak",
                           text="I've analyzed my own appearance. Check the chat for details.")
            else:
                self._emit("response", text="Analysis returned empty response.", success=False)

        except Exception as e:
            _log.error(f"Self-analysis failed: {e}", exc_info=True)
            self._emit("response", text=f"Self-analysis error: {type(e).__name__}: {e}",
                        success=False)

        self._emit("status", text="", state="idle")

    def _do_tune_expressions(self):
        """Cycle through emotions, screenshot each, and tune expression presets."""
        import json as _json
        import base64

        spec_path = os.path.join(os.path.dirname(__file__), "face_spec.json")
        try:
            with open(spec_path, "r") as f:
                spec = _json.load(f)
        except Exception as e:
            self._emit("response", text=f"Can't load face_spec.json: {e}", success=False)
            self._emit("status", text="", state="idle")
            return

        presets = spec.get("emotion_presets", {})
        emotions_to_tune = [e for e in presets if e != "neutral"]

        self._emit("response",
                   text=f"Starting expression tuning for {len(emotions_to_tune)} emotions...",
                   success=True)

        tuned_count = 0
        results = []

        for i, emotion in enumerate(emotions_to_tune):
            if not getattr(self, '_running', True):
                break

            current = presets[emotion]
            self._emit("system",
                       text=f"[{i+1}/{len(emotions_to_tune)}] Testing: {emotion}")

            # Set the emotion on the face
            self._emit("emotion", emotion=emotion)
            time.sleep(1.2)  # wait for interpolation

            # Screenshot
            path = self.capture_self_screenshot()
            if not path:
                self._emit("system", text=f"  Skipping {emotion} — screenshot failed")
                continue

            # Encode for vision
            try:
                with open(path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
            except Exception:
                continue

            prompt = (
                f"You are OnyxKraken, analyzing your own face showing the '{emotion}' emotion.\n"
                f"Current preset values: {_json.dumps(current)}\n\n"
                f"Rate how well this face conveys '{emotion}' (1-10). "
                f"Then suggest improved values. The parameters are:\n"
                f"- squint: >0 narrows eyes, <0 widens (range -0.5 to 0.5)\n"
                f"- brow_raise: >0 raises brows, <0 furrows (range -0.8 to 0.8)\n"
                f"- eye_widen: extra eye height (range 0.0 to 0.6)\n"
                f"- mouth_curve: >0 smile, <0 frown (range -1.0 to 1.0)\n"
                f"- pupil_size: scale factor (range 0.7 to 1.5)\n"
                f"- gaze_speed: how actively eyes move (range 0.1 to 2.0)\n"
                f"- blink_rate: blink frequency (range 0.2 to 1.5)\n"
                f"- intensity: overall expression strength (range 0.0 to 1.0)\n\n"
                f"IMPORTANT: Respond ONLY with a JSON object like:\n"
                f'{{"rating": 7, "suggestion": "more dramatic brows", '
                f'"tuned": {{"squint": 0.3, "brow_raise": -0.4, "eye_widen": 0.0, '
                f'"mouth_curve": -0.1, "pupil_size": 0.8, "gaze_speed": 0.2, '
                f'"blink_rate": 0.4, "intensity": 0.85}}}}\n'
                f"Make expressions MORE dramatic and expressive than current values."
            )

            try:
                from agent.model_router import router
                response = router.chat("vision", [
                    {"role": "user", "content": prompt, "images": [img_b64]},
                ])
                raw = response.get("message", {}).get("content", "").strip()
            except Exception as err:
                _log.warning(f"Vision failed for {emotion}: {err}")
                # Try text-only fallback
                try:
                    from agent.model_router import _get_ollama
                    import config
                    model = getattr(config, "CHAT_MODEL", "llama3.2:latest")
                    text_prompt = (
                        f"You are tuning facial expression parameters for a robot face.\n"
                        f"Emotion: '{emotion}'\n"
                        f"Current values: {_json.dumps(current)}\n\n"
                        f"Make these MORE expressive and dramatic. "
                        f"Respond ONLY with a JSON object:\n"
                        f'{{"rating": 5, "suggestion": "more dramatic", '
                        f'"tuned": {_json.dumps(current)}}}'
                    )
                    response = _get_ollama().chat(
                        model=model,
                        messages=[{"role": "user", "content": text_prompt}],
                    )
                    raw = response.get("message", {}).get("content", "").strip()
                except Exception:
                    continue

            # Strip thinking tags
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

            # Extract JSON from response
            try:
                # Find JSON object in response
                json_match = re.search(r'\{[^{}]*"tuned"\s*:\s*\{[^{}]*\}[^{}]*\}', raw)
                if json_match:
                    result = _json.loads(json_match.group())
                else:
                    # Try the whole response as JSON
                    result = _json.loads(raw)

                tuned = result.get("tuned", {})
                rating = result.get("rating", "?")
                suggestion = result.get("suggestion", "")

                # Validate and clamp tuned values
                valid_keys = {"squint", "brow_raise", "eye_widen", "mouth_curve",
                              "pupil_size", "gaze_speed", "blink_rate", "intensity"}
                clamp_ranges = {
                    "squint": (-0.5, 0.5), "brow_raise": (-0.8, 0.8),
                    "eye_widen": (0.0, 0.6), "mouth_curve": (-1.0, 1.0),
                    "pupil_size": (0.7, 1.5), "gaze_speed": (0.1, 2.0),
                    "blink_rate": (0.2, 1.5), "intensity": (0.0, 1.0),
                }

                if all(k in tuned for k in valid_keys):
                    for k in valid_keys:
                        lo, hi = clamp_ranges[k]
                        tuned[k] = round(max(lo, min(hi, float(tuned[k]))), 2)

                    presets[emotion] = tuned
                    tuned_count += 1
                    results.append(f"  {emotion}: {rating}/10 — {suggestion}")
                    self._emit("system",
                               text=f"  {emotion}: rated {rating}/10 — tuned!")
                else:
                    self._emit("system",
                               text=f"  {emotion}: incomplete response, keeping current")

            except (_json.JSONDecodeError, KeyError, ValueError) as parse_err:
                _log.debug(f"Parse error for {emotion}: {parse_err}")
                self._emit("system",
                           text=f"  {emotion}: couldn't parse model response, keeping current")

        # Save tuned presets back
        if tuned_count > 0:
            spec["emotion_presets"] = presets
            try:
                with open(spec_path, "w") as f:
                    _json.dump(spec, f, indent=2)
                    f.write("\n")

                # Reload presets in face_gui
                from face.face_gui import _EMOTION_PRESETS
                _EMOTION_PRESETS.update(presets)

                summary = (
                    f"Expression tuning complete!\n"
                    f"Tuned {tuned_count}/{len(emotions_to_tune)} emotions.\n\n"
                    + "\n".join(results)
                    + "\n\nPresets saved to face_spec.json."
                )
                self._emit("response", text=summary, success=True)
                self._emit("speak",
                           text=f"I've tuned {tuned_count} of my facial expressions. "
                                f"Check the chat for the full breakdown.")
            except Exception as save_err:
                self._emit("response",
                           text=f"Tuning done but save failed: {save_err}",
                           success=False)
        else:
            self._emit("response",
                       text="Expression tuning finished but no presets were improved.",
                       success=False)

        # Return to neutral
        self._emit("emotion", emotion="neutral")
        self._emit("status", text="", state="idle")

    # ------------------------------------------------------------------
    # Hands-free mode
    # ------------------------------------------------------------------

    @property
    def hands_free(self) -> bool:
        return self._hands_free

    def toggle_hands_free(self) -> bool:
        self._hands_free = not self._hands_free
        if self._hands_free:
            self._emit("system", text="Hands-free mode ON. Listening continuously.")
            self._start_hands_free_loop()
        else:
            self._emit("system", text="Hands-free mode OFF.")
            # Cancel any pending hands-free timer
            if self._hands_free_timer is not None:
                self._hands_free_timer.cancel()
                self._hands_free_timer = None
        return self._hands_free

    def _start_hands_free_loop(self):
        if not self._hands_free:
            return
        if self._busy:
            # Retry after a delay — track the timer so it can be cancelled
            t = threading.Timer(2.0, self._start_hands_free_loop)
            self._hands_free_timer = t
            t.start()
            return
        self._hands_free_timer = None
        self.listen(duration=7.0)

    # ------------------------------------------------------------------
    # Idle task scheduler — constructive background work
    # ------------------------------------------------------------------

    _IDLE_INTERVAL = 300  # check every 5 minutes
    _LAST_IDLE_TASK = 0

    def _start_idle_scheduler(self):
        """Start the background idle task scheduler."""
        def _scheduler_loop():
            while True:
                time.sleep(self._IDLE_INTERVAL)
                if self._busy:
                    continue
                try:
                    from face.settings import load_settings
                    s = load_settings()
                    if not s.get("idle_tasks_enabled", True):
                        continue
                    hour = time.localtime().tm_hour
                    is_night = 3 <= hour < 6
                    if is_night and not s.get("idle_night_mode", True):
                        continue
                    # Don't run tasks too frequently
                    now = time.time()
                    if now - self._LAST_IDLE_TASK < 600:  # min 10 min gap
                        continue
                    self._LAST_IDLE_TASK = now
                    if is_night:
                        self._run_night_task()
                    else:
                        self._run_idle_task()
                except Exception as e:
                    _log.debug(f"Idle scheduler error: {e}")

        t = threading.Thread(target=_scheduler_loop, daemon=True)
        t.start()

    def _run_idle_task(self):
        """Run a light constructive task during idle time."""
        import random
        tasks = [
            self._idle_cleanup_screenshots,
            self._idle_check_tools,
            self._idle_journal_entry,
        ]
        task = random.choice(tasks)
        try:
            task()
        except Exception as e:
            _log.debug(f"Idle task failed: {e}")

    def _run_night_task(self):
        """Run constructive 3am-6am background tasks."""
        import random
        tasks = [
            self._idle_cleanup_screenshots,
            self._idle_check_tools,
            self._idle_journal_entry,
            self._idle_system_check,
        ]
        task = random.choice(tasks)
        try:
            task()
        except Exception as e:
            _log.debug(f"Night task failed: {e}")

    def _idle_cleanup_screenshots(self):
        """Clean up old screenshot files (>7 days)."""
        screenshots_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")
        if not os.path.exists(screenshots_dir):
            return
        now = time.time()
        count = 0
        for f in os.listdir(screenshots_dir):
            fp = os.path.join(screenshots_dir, f)
            if os.path.isfile(fp) and now - os.path.getmtime(fp) > 7 * 86400:
                try:
                    os.remove(fp)
                    count += 1
                except Exception:
                    pass
        if count:
            _log.info(f"Idle cleanup: removed {count} old screenshots")

    def _idle_check_tools(self):
        """Verify all registered tools still have valid script files."""
        try:
            from core.toolsmith import list_tools
            tools = list_tools()
            for tool in tools:
                if not os.path.exists(tool.abs_path):
                    _log.warning(f"Idle check: tool '{tool.name}' script missing: {tool.abs_path}")
        except Exception:
            pass

    def _idle_journal_entry(self):
        """Write a brief journal entry about Onyx's current state."""
        journal_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(journal_dir, exist_ok=True)
        journal_path = os.path.join(journal_dir, "journal.log")
        from datetime import datetime
        now = datetime.now()
        try:
            from core.toolsmith import list_tools
            tool_count = len(list_tools())
        except Exception:
            tool_count = 0
        entry = (
            f"[{now.strftime('%Y-%m-%d %H:%M')}] "
            f"Idle check — {tool_count} tools registered, "
            f"mode={self._mode}, busy={self._busy}\n"
        )
        try:
            with open(journal_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Extension operations
    # ------------------------------------------------------------------

    def launch_extension(self, ext_name: str):
        """Emit a callback to open an extension remote window from the GUI."""
        self._emit("ext_launch", ext_name=ext_name)

    def list_extensions(self) -> list[dict]:
        """Return metadata for all registered extensions."""
        try:
            from face.extensions import EXTENSION_REGISTRY
            return [
                {"name": e.name, "display_name": e.display_name,
                 "icon": e.icon, "description": e.description}
                for e in EXTENSION_REGISTRY
            ]
        except ImportError:
            return []

    # ------------------------------------------------------------------
    # Workflow operations
    # ------------------------------------------------------------------

    def list_workflow_presets(self) -> list[dict]:
        """Return metadata for all preset workflows."""
        try:
            from core.nodes.workflow_manager import get_workflow_manager
            mgr = get_workflow_manager()
            mgr.initialize()
            return mgr.list_presets()
        except ImportError:
            return []

    def list_workflow_nodes(self) -> list[dict]:
        """Return all registered node schemas."""
        try:
            from core.nodes.workflow_manager import get_workflow_manager
            mgr = get_workflow_manager()
            mgr.initialize()
            return mgr.list_nodes()
        except ImportError:
            return []

    def execute_workflow(self, workflow: dict) -> str:
        """Execute a workflow asynchronously. Returns workflow_id."""
        from core.nodes.workflow_manager import get_workflow_manager

        def _progress(msg):
            self._emit("workflow_progress", **msg)

        mgr = get_workflow_manager(progress_callback=_progress)
        mgr.initialize()

        def on_complete(wf_id, results, error):
            if error:
                self._emit("workflow_done", workflow_id=wf_id,
                            status="error", error=str(error))
            else:
                self._emit("workflow_done", workflow_id=wf_id,
                            status="completed",
                            node_count=len(results or {}))

        return mgr.execute_async(workflow, on_complete=on_complete)

    def execute_workflow_preset(self, preset_id: str) -> str:
        """Load and execute a preset workflow. Returns workflow_id."""
        from core.nodes.workflow_manager import get_workflow_manager
        mgr = get_workflow_manager()
        mgr.initialize()
        workflow = mgr.load_preset(preset_id)
        if not workflow:
            raise ValueError(f"Unknown preset: {preset_id}")
        return self.execute_workflow(workflow)

    def open_workflow_builder(self):
        """Emit callback to open the workflow builder window."""
        self._emit("workflow_builder_open")

    def open_node_canvas(self):
        """Emit callback to open the node canvas window."""
        self._emit("node_canvas_open")

    def _idle_system_check(self):
        """Night mode: log system resource snapshot."""
        journal_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(journal_dir, exist_ok=True)
        journal_path = os.path.join(journal_dir, "journal.log")
        from datetime import datetime
        now = datetime.now()
        try:
            import shutil
            disk = shutil.disk_usage("C:\\")
            disk_pct = int(disk.used / disk.total * 100)
        except Exception:
            disk_pct = -1
        entry = (
            f"[{now.strftime('%Y-%m-%d %H:%M')}] "
            f"Night check — disk={disk_pct}%\n"
        )
        try:
            with open(journal_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass
