"""OnyxKraken — Local Desktop Automation Agent entry point."""

import sys
import config
from log import setup_logging

setup_logging(config.LOG_LEVEL)


# ---------------------------------------------------------------------------
# Lazy imports — pywinauto / ollama / orchestrator init can hang if services
# are unavailable.  Only pull them in when actually needed.
# ---------------------------------------------------------------------------

def _lazy_agent():
    """Import heavy agent modules on demand."""
    from agent.orchestrator import run
    from agent.conversation import (
        ConversationState, ConversationTurn, Intent,
        classify_intent, resolve_goal, format_status_response,
    )
    try:
        from desktop.controller import list_desktop_items
    except (ImportError, RuntimeError):
        def list_desktop_items(): return []
    from apps.registry import discover_modules, list_modules
    from memory.store import MemoryStore
    return {
        "run": run,
        "ConversationState": ConversationState,
        "ConversationTurn": ConversationTurn,
        "Intent": Intent,
        "classify_intent": classify_intent,
        "resolve_goal": resolve_goal,
        "format_status_response": format_status_response,
        "list_desktop_items": list_desktop_items,
        "discover_modules": discover_modules,
        "list_modules": list_modules,
        "MemoryStore": MemoryStore,
    }


def print_banner():
    from memory.store import MemoryStore
    from core.license import get_license_type, get_demo_tracker
    
    memory = MemoryStore()
    task_count = len(memory.get_all().get("task_history", []))
    license_type = get_license_type()
    
    # Check for updates (async, non-blocking)
    try:
        from core.updates import check_for_updates
        update_info = check_for_updates()
        if update_info:
            print(f"\n🎉 Update available: {update_info['current_version']} → {update_info['latest_version']}")
            print(f"   Download: {update_info['release_url']}\n")
    except Exception:
        pass  # Silently fail if update check fails

    print(r"""
   ____              _  __          _              
  / __ \            | |/ /         | |             
 | |  | |_ __  _   _| ' / _ __ __ _| | _____ _ __  
 | |  | | '_ \| | | |  < | '__/ _` | |/ / _ \ '_ \ 
 | |__| | | | | |_| | . \| | | (_| |   <  __/ | | |
  \____/|_| |_|\__, |_|\_\_|  \__,_|_|\_\___|_| |_|
                __/ |                               
               |___/   Local Desktop Automation Agent
    """)
    
    # Show trial/license status via hardened security system
    try:
        from core.security import get_trial_manager
        trial = get_trial_manager()
        info = trial.trial_info()
        if info["status"] == "activated":
            print(f"  License:       ✅ Full Version (Activated)")
        elif info["status"] == "trial":
            days = info["days_remaining"]
            print(f"  License:       ⏳ Trial ({days:.0f} days remaining)")
            print(f"                 Purchase: $149 one-time → python main.py activate <KEY>")
        elif info["status"] == "expired":
            print(f"  License:       ❌ Trial Expired")
            print(f"                 Purchase OnyxCore ($149) to continue using all features.")
        else:
            print(f"  License:       ⚠️  Unknown state")
    except Exception:
        # Fallback to legacy license check
        if license_type == "full":
            print(f"  License:       ✅ Full Version")
        else:
            tracker = get_demo_tracker()
            remaining = tracker.get_remaining_tasks()
            print(f"  License:       ⚠️  Demo Mode ({remaining} tasks remaining)")
            print(f"                 Activate license for unlimited tasks")
    
    print(f"  Autonomy mode: {config.AUTONOMY_MODE}")
    print(f"  Vision model:  {config.VISION_MODEL}")
    print(f"  Planner model: {config.PLANNER_MODEL}")
    if task_count > 0:
        print(f"  Memory:        {task_count} past tasks remembered")
    print()


def _infer_app_name(text: str) -> str:
    """Try to infer app name from text using registered modules and desktop items."""
    from apps.registry import list_modules
    for mod_name in list_modules():
        if mod_name.lower() in text.lower():
            return mod_name

    try:
        from desktop.controller import list_desktop_items
        for item in list_desktop_items():
            name_no_ext = item["name"].rsplit(".", 1)[0].lower()
            if name_no_ext in text.lower():
                return name_no_ext
    except (ImportError, RuntimeError):
        pass  # Desktop automation not available

    return "unknown"


def interactive_mode():
    """Run in interactive mode with multi-turn conversation support."""
    a = _lazy_agent()
    run = a["run"]
    ConversationState = a["ConversationState"]
    ConversationTurn = a["ConversationTurn"]
    Intent = a["Intent"]
    classify_intent = a["classify_intent"]
    resolve_goal = a["resolve_goal"]
    format_status_response = a["format_status_response"]
    list_desktop_items = a["list_desktop_items"]
    discover_modules = a["discover_modules"]

    print_banner()
    discover_modules()

    items = list_desktop_items()
    if items:
        print("Desktop items found:")
        for item in items:
            print(f"  - {item['name']}")
        print()

    print("Type a goal and press Enter. Follow-ups like 'now save that' work too.")
    print("Type 'quit' to exit.\n")

    state = ConversationState()

    while True:
        try:
            user_input = input("Onyx> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Exiting.")
            break

        # Classify intent
        intent = classify_intent(user_input, state)
        print(f"  [intent: {intent}]")

        # Handle status queries without running a task
        if intent == Intent.STATUS_QUERY:
            print(format_status_response(state))
            continue

        # Handle conversational messages without running the orchestrator
        if intent == Intent.CONVERSATION:
            try:
                import ollama
                resp = ollama.chat(
                    model=config.PLANNER_MODEL_FALLBACK,
                    messages=[
                        {"role": "system", "content": (
                            "You are OnyxKraken, a friendly and witty local desktop automation agent. "
                            "Right now the user is just chatting — respond naturally, briefly, "
                            "and with personality. Keep replies under 3 sentences."
                        )},
                        {"role": "user", "content": user_input},
                    ],
                )
                import re
                reply = resp.get("message", {}).get("content", "").strip()
                reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()
                print(f"  {reply or 'Hey! Ask me to do something on your desktop.'}")
            except Exception:
                print("  Hey! I'm OnyxKraken. Ask me to do anything on your desktop.")
            continue

        # Resolve the goal based on intent + conversation context
        resolved_goal, app_name = resolve_goal(user_input, intent, state)

        # If resolver didn't find an app, try inference on resolved goal
        if app_name == "unknown":
            app_name = _infer_app_name(resolved_goal)

        print(f"  [resolved: \"{resolved_goal[:80]}\"]")
        if app_name != "unknown":
            print(f"  [app: {app_name}]")

        # Execute
        result = run(goal=resolved_goal, app_name=app_name)

        # Build result summary from history
        result_summary = ""
        if result and result.history:
            for entry in reversed(result.history):
                if entry["role"] == "user" and "read" in entry.get("content", "").lower():
                    result_summary = entry["content"][:500]
                    break
            if not result_summary and result.final_window_title:
                result_summary = f"Final window: {result.final_window_title}"

        # Record to conversation state
        success = result is not None and not result.aborted and result.steps_completed == result.steps_planned
        state.turns.append(ConversationTurn(
            user_input=user_input,
            resolved_goal=resolved_goal,
            app_name=app_name,
            result_summary=result_summary,
            success=success,
        ))


def cmd_serve(args):
    """Start the FastAPI server."""
    try:
        import uvicorn  # noqa: F811
    except ImportError:
        print("Error: 'uvicorn' not installed. Run: pip install onyxkraken[server]")
        return
    host = "0.0.0.0"
    port = 8420
    for i, arg in enumerate(args):
        if arg in ("--host",) and i + 1 < len(args):
            host = args[i + 1]
        if arg in ("--port",) and i + 1 < len(args):
            port = int(args[i + 1])
    print(f"[Server] Starting OnyxKraken API on {host}:{port}...")
    uvicorn.run("server:app", host=host, port=port, reload=False)


def cmd_improve():
    """Run a self-improvement cycle."""
    from core.license import has_feature, get_feature_gate_message
    if not has_feature("self_improvement"):
        print(get_feature_gate_message("self_improvement"))
        return
    from core.self_improvement import get_improvement_engine
    engine = get_improvement_engine()
    summary = engine.run_improvement_cycle()
    print(f"\nSummary: {summary}")
    stats = engine.get_stats()
    print(f"Stats: {stats}")


def cmd_daemon(args):
    """Start the autonomy daemon interactively."""
    from core.license import has_feature, get_feature_gate_message
    if not has_feature("daemon"):
        print(get_feature_gate_message("daemon"))
        return
    from core.autonomy import get_daemon
    daemon = get_daemon()
    daemon.start()
    print("Autonomy daemon running. Commands: queue <goal>, stats, pause, resume, stop")
    while True:
        try:
            cmd = input("daemon> ").strip()
        except (EOFError, KeyboardInterrupt):
            daemon.stop()
            break
        if not cmd:
            continue
        if cmd.lower() in ("stop", "quit", "exit"):
            daemon.stop()
            break
        elif cmd.lower() == "stats":
            print(daemon.get_stats())
        elif cmd.lower() == "pause":
            daemon.pause()
        elif cmd.lower() == "resume":
            daemon.resume()
        elif cmd.lower().startswith("queue "):
            goal = cmd[6:].strip()
            if goal:
                daemon.queue_goal(goal)
        else:
            print("Unknown command. Try: queue <goal>, stats, pause, resume, stop")


def cmd_voice():
    """Voice input mode — speak goals instead of typing."""
    from core.license import has_feature, get_feature_gate_message
    if not has_feature("voice"):
        print(get_feature_gate_message("voice"))
        return
    a = _lazy_agent()
    run = a["run"]
    ConversationState = a["ConversationState"]
    ConversationTurn = a["ConversationTurn"]
    Intent = a["Intent"]
    classify_intent = a["classify_intent"]
    resolve_goal = a["resolve_goal"]
    format_status_response = a["format_status_response"]
    discover_modules = a["discover_modules"]

    print_banner()
    discover_modules()
    print("Voice mode: speak your goal after the prompt. Say 'quit' to exit.\n")

    state = ConversationState()
    from core.voice import listen, speak

    while True:
        print("Listening... (speak now)")
        text = listen(duration=7)
        if text is None:
            print("  No speech detected. Try again.")
            continue

        print(f"  Heard: \"{text}\"")
        if text.lower().strip() in ("quit", "exit", "stop"):
            speak("Goodbye.")
            break

        intent = classify_intent(text, state)
        if intent == Intent.STATUS_QUERY:
            response = format_status_response(state)
            print(response)
            speak(response[:200])
            continue

        resolved_goal, app_name = resolve_goal(text, intent, state)
        if app_name == "unknown":
            app_name = _infer_app_name(resolved_goal)

        speak(f"Working on: {resolved_goal[:60]}")
        result = run(goal=resolved_goal, app_name=app_name)

        success = result is not None and not result.aborted and result.steps_completed == result.steps_planned
        if success:
            speak("Done.")
        else:
            speak("That didn't work out.")

        state.turns.append(ConversationTurn(
            user_input=text,
            resolved_goal=resolved_goal,
            app_name=app_name,
            result_summary="",
            success=success,
        ))


def cmd_tools(args):
    """Manage Onyx's self-built tools ecosystem."""
    from core.toolsmith import list_tools, verify_tool, prefer_tool, launch_tool, get_tool

    if not args or args[0] == "list":
        tools = list_tools()
        if not tools:
            print("No self-built tools yet.")
            return
        print(f"\nOnyx's Self-Built Tools ({len(tools)}):")
        for t in tools:
            icon = {"draft": "🔨", "verified": "✅", "preferred": "⭐"}.get(t.status, "?")
            print(f"  {icon} {t.display_name} [{t.status}]")
            print(f"     {t.description}")
            print(f"     Replaces: {', '.join(t.replaces)}")
            print(f"     Path: {t.abs_path}")
        print()

    elif args[0] == "verify" and len(args) > 1:
        name = args[1]
        if verify_tool(name):
            print(f"✅ Tool '{name}' marked as verified. Onyx will now use it.")
            # Auto-prefer after verification
            prefer_tool(name)
            print(f"⭐ Tool '{name}' set as preferred over external apps.")
        else:
            print(f"Tool '{name}' not found. Use 'tools list' to see available tools.")

    elif args[0] == "launch" and len(args) > 1:
        name = args[1]
        tool = get_tool(name)
        if tool is None:
            print(f"Tool '{name}' not found.")
            return
        proc = launch_tool(name)
        if proc:
            print(f"Launched {tool.display_name} (PID={proc.pid})")
        else:
            print(f"Failed to launch {name}.")

    elif args[0] == "test" and len(args) > 1:
        name = args[1]
        tool = get_tool(name)
        if tool is None:
            print(f"Tool '{name}' not found.")
            return
        print(f"Launching {tool.display_name} for testing...")
        proc = launch_tool(name)
        if proc:
            print(f"Tool running (PID={proc.pid}). Test it, then use 'tools verify {name}' to approve.")
        else:
            print(f"Failed to launch {name}.")

    else:
        print("Usage: python main.py tools [list|verify <name>|launch <name>|test <name>]")


def cmd_demo(args):
    """Launch Face GUI and immediately start a self-demo sequence."""
    from face.demo_runner import list_demos, DEMO_SEQUENCES
    from face.app import OnyxKrakenApp

    # Show-based demos (fullscreen episode mode via ShowEngine)
    SHOW_DEMOS = set(OnyxKrakenApp._SHOW_DEMOS.keys())
    all_valid = set(DEMO_SEQUENCES.keys()) | SHOW_DEMOS

    if args and args[0] == "--list":
        demos = list_demos()
        print("\nAvailable demo sequences:\n")
        for d in demos:
            est = d["estimated_time"]
            t = f"{est // 60}m {est % 60}s" if est >= 60 else f"{est}s"
            print(f"  {d['id']:15s}  {d['title']:25s}  ~{t:8s}  {d['steps']} steps")
            print(f"  {'':15s}  {d['description']}")
            print()
        if SHOW_DEMOS:
            print("  Fullscreen episode demos (ShowEngine):")
            for sid in sorted(SHOW_DEMOS):
                print(f"    {sid:15s}  (fullscreen stage with panels + animations)")
            print()
        return

    # Parse flags
    record = "--record" in args or "-r" in args
    use_obs = "--obs" in args
    auto_exit = "--auto-exit" in args
    positional = [a for a in args if not a.startswith("-")]
    seq_id = positional[0] if positional else "full"

    if seq_id not in all_valid:
        print(f"Unknown demo: {seq_id}")
        print(f"Available: {', '.join(sorted(all_valid))}")
        return

    if record:
        print(f"Recording enabled {'(OBS)' if use_obs else '(built-in)'}")

    # Auto-start Discord + API
    _start_discord_if_configured()

    # Launch face with auto-demo
    from face.app import OnyxKrakenApp
    app = OnyxKrakenApp()

    # Schedule demo start after UI is ready
    def _auto_start():
        import time
        time.sleep(2.0)  # let the UI settle
        app._start_demo(seq_id, record=record, auto_exit=auto_exit)

    import threading
    threading.Thread(target=_auto_start, daemon=True).start()

    app.root.mainloop()


def cmd_mirror(args):
    """Launch Face GUI and run the mirror tool (analyze or tune expressions)."""
    tune = "--tune" in args or "-t" in args

    _start_discord_if_configured()

    from face.app import OnyxKrakenApp
    app = OnyxKrakenApp()

    def _auto_mirror():
        import time
        time.sleep(2.5)  # let UI settle
        app.backend.analyze_self(tune_expressions=tune)

    import threading
    threading.Thread(target=_auto_mirror, daemon=True).start()

    app.root.mainloop()


def cmd_companion(args):
    """Launch Onyx in companion mode with Xyno.

    Flags:
        --demo              Record a 10-20 exchange demo
        --at HH:MM          Schedule demo at a specific time (e.g. --at 02:00)
        --exchanges N       Number of exchanges (default 15)
        --improve           Use self-improvement topics
        --topic "..."       Set a specific conversation topic
    """
    from core.license import has_feature, get_feature_gate_message
    if not has_feature("companion"):
        print(get_feature_gate_message("companion"))
        return
    is_demo = "--demo" in args
    is_improve = "--improve" in args

    # Parse --at HH:MM
    target_time = None
    if "--at" in args:
        idx = args.index("--at")
        if idx + 1 < len(args):
            try:
                parts = args[idx + 1].split(":")
                target_time = (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
            except (ValueError, IndexError):
                print("Invalid --at format. Use HH:MM (e.g. 02:00)")
                return

    # Parse --exchanges N
    max_ex = 15
    if "--exchanges" in args:
        idx = args.index("--exchanges")
        if idx + 1 < len(args):
            try:
                max_ex = int(args[idx + 1])
            except ValueError:
                pass

    # Parse --topic "..."
    topic = None
    if "--topic" in args:
        idx = args.index("--topic")
        if idx + 1 < len(args):
            topic = args[idx + 1]

    _start_discord_if_configured()

    from face.app import OnyxKrakenApp
    app = OnyxKrakenApp()

    if target_time:
        # Scheduled demo — wait until target time then auto-launch
        from face.companion_mode import schedule_companion_demo
        schedule_companion_demo(
            app,
            target_hour=target_time[0],
            target_minute=target_time[1],
            max_exchanges=max_ex,
            self_improve=is_improve,
        )
    elif is_demo:
        # Immediate recorded demo
        def _start_demo():
            from face.companion_mode import launch_companion_demo
            launch_companion_demo(
                app,
                max_exchanges=max_ex,
                topic=topic,
                self_improve=is_improve,
                record=True,
            )
        app.root.after(2500, _start_demo)
    else:
        # Interactive companion mode (no limit, no recording)
        def _start_companion():
            from face.companion_mode import launch_companion_mode
            launch_companion_mode(app, topic=topic, self_improve=is_improve)
        app.root.after(2500, _start_companion)

    app.run()


def cmd_conversation(args):
    """Launch stage-based multi-character conversation.
    
    Full-body characters on stage, camera cuts to whoever is speaking,
    TTS-driven timing with organic pauses.
    
    Usage:
        python main.py conversation
        python main.py conversation --characters onyx,xyno,volt
        python main.py conversation --topic "AI ethics" --record
    """
    from face.stage.shows.conversation_show import run_conversation_cli
    run_conversation_cli(args)


def cmd_homebuilder(args):
    """Smart HomeBuilder Bot — AI interior design with Home Builder 5."""
    from addons.blender.home_builder_bot import run_homebuilder_cli
    run_homebuilder_cli(args)


def cmd_blender_voice(args):
    """Voice-controlled Blender session with conversational workflow."""
    if args and args[0] in ("--help", "-h"):
        print("Usage: python main.py blender-voice")
        print()
        print("Start a conversational voice-controlled Blender session.")
        print()
        print("Workflow:")
        print("  1. Opens Blender and asks 'What are we working on today?'")
        print("  2. You give commands: 'create a wooden chair'")
        print("  3. Bot executes and replies: 'I've created a wooden chair. Anything else?'")
        print("  4. Continue with commands or say 'done' to save and close")
        print()
        print("Features:")
        print("  • Auto-grouping: chair pieces → chair collection")
        print("  • Context-aware deletion: click object → 'delete this chair' → deletes whole group")
        print("  • Natural language commands for creation, modification, deletion")
        print("  • Persistent session state across commands")
        return

    from addons.blender.voice_control import VoiceBlenderSession
    
    print("=" * 60)
    print("VOICE-CONTROLLED BLENDER SESSION")
    print("=" * 60)
    
    session = VoiceBlenderSession()
    
    if not session.start():
        print("\nFailed to start Blender session.")
        return
    
    print("\nSession active. Enter commands (or 'done' to finish):")
    print("Examples:")
    print("  • create a wooden chair")
    print("  • make a red cube")
    print("  • list assets")
    print("  • import WoodenChair")
    print("  • delete this chair")
    print("  • done")
    print()
    
    try:
        while session.is_active:
            try:
                cmd = input("> ").strip()
                if not cmd:
                    continue
                
                result = session.execute_command(cmd)
                
                if not session.is_active:
                    break
                    
                if not result["success"]:
                    print(f"Error: {result.get('error', 'Unknown error')}")
                    
            except KeyboardInterrupt:
                print("\n\nInterrupted. Closing session...")
                session.close()
                break
            except EOFError:
                print("\n\nEOF. Closing session...")
                session.close()
                break
    finally:
        if session.is_active:
            session.close()
    
    print(f"\nSession complete. Blend file: {session.blend_file}")


def cmd_generate(args):
    """LLM-driven generative Blender build from a natural language prompt."""
    if not args or args[0] in ("--help", "-h"):
        print("Usage: python main.py generate <prompt> [--no-qc]")
        print("  <prompt>   Description of what to build (quote it)")
        print("  --no-qc    Disable vision quality checking")
        print()
        print("Examples:")
        print('  python main.py generate "a cozy log cabin in the woods"')
        print('  python main.py generate "a modern office building with glass facade"')
        print('  python main.py generate "a medieval castle with towers and moat"')
        return

    enable_qc = "--no-qc" not in args
    prompt_parts = [a for a in args if not a.startswith("--")]
    prompt = " ".join(prompt_parts)

    if not prompt:
        print("Error: provide a build description")
        return

    from addons.blender.generative import run_generative_build
    run_generative_build(prompt, enable_vision_qc=enable_qc)


def cmd_demolog(args):
    """Show demo history / log."""
    from face.demo_log import get_demo_log
    log = get_demo_log()

    if args and args[0] == "--json":
        import json
        print(json.dumps(log.get_all(), indent=2))
        return

    print(log.summary())


def cmd_record(args):
    """Standalone screen recording (no GUI required)."""
    from core.license import has_feature, get_feature_gate_message
    if not has_feature("screen_recording"):
        print(get_feature_gate_message("screen_recording"))
        return
    from core.screen_recorder import ScreenRecorder

    name = args[0] if args else "onyx_recording"
    quality = "high"
    fps = 20

    for i, a in enumerate(args):
        if a == "--quality" and i + 1 < len(args):
            quality = args[i + 1]
        if a == "--fps" and i + 1 < len(args):
            fps = int(args[i + 1])

    rec = ScreenRecorder(fps=fps, quality=quality)
    path = rec.start(name)
    print(f"Recording → {path}")
    print("Press Enter to stop...")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass
    info = rec.stop()
    if info:
        mb = info.size_bytes / (1024 * 1024)
        print(f"Saved: {info.path} ({mb:.1f} MB, {info.duration:.0f}s, {info.fps}fps)")


def cmd_episode(args):
    """Launch the Face GUI, open stage, and run an episode (optionally recorded).

    Usage:
        python main.py episode 1                     # Play Episode 1 on stage
        python main.py episode 1 --record            # Record Episode 1
        python main.py episode 1 --record --auto-exit  # Record + exit when done
    """
    import threading

    positional = [a for a in args if not a.startswith("-")]
    episode_num = int(positional[0]) if positional else 1
    record = "--record" in args or "-r" in args
    auto_exit = "--auto-exit" in args

    _start_discord_if_configured()

    from face.app import OnyxKrakenApp
    app = OnyxKrakenApp()
    recorder_ref = [None]  # mutable holder for the ScreenRecorder

    def _on_episode_done():
        """Called when the ShowEngine finishes the episode."""
        # Stop recording via module singleton
        if recorder_ref[0]:
            try:
                from core.screen_recorder import stop_recording
                info = stop_recording()
                if info:
                    mb = info.size_bytes / (1024 * 1024)
                    print(f"[Episode] Recording saved: {info.path} ({mb:.1f} MB, {info.duration:.0f}s)")
            except Exception as exc:
                print(f"[Episode] Recording stop error: {exc}")
            recorder_ref[0] = None

        # Close stage after a brief delay
        def _cleanup():
            app._close_stage()
            if auto_exit:
                app.root.after(2000, app.root.destroy)
        app.root.after(1000, _cleanup)

    def _auto_start():
        import time
        time.sleep(2.5)  # let UI settle

        # Start recording before opening stage — use the module singleton
        # so the stage's _music_start can find it via is_recording()/get_recorder()
        if record:
            try:
                from core.screen_recorder import start_recording, get_recorder
                start_recording(f"episode_{episode_num}",
                                fps=20, quality="high", capture_audio=True)
                recorder_ref[0] = get_recorder()
                print(f"[Episode] Recording started")
            except Exception as exc:
                print(f"[Episode] Recording failed: {exc}")

        # Open stage + run episode on the main thread
        def _launch():
            from face.stage.stage_manager import StageManager
            from face.stage.show_engine import ShowEngine
            from face.stage.shows.daily_episode import build_daily_episode

            if app._stage_manager and app._stage_manager.is_open:
                return

            app._stage_manager = StageManager(app.root, app.face)
            app._stage_manager.open(on_close=app._on_stage_closed)
            print(f"[Episode] Stage opened")

            def _start_show():
                app._show_engine = ShowEngine(app._stage_manager)
                app._show_engine.on_show_end = _on_episode_done
                app._show_engine.play(build_daily_episode(episode_num))
                print(f"[Episode] Now playing: Episode {episode_num}")
            app.root.after(1000, _start_show)

        app.root.after(0, _launch)

    threading.Thread(target=_auto_start, daemon=True, name="EpisodeStarter").start()
    app.run()


def cmd_face():
    """Launch the Face GUI with chat panel and voice integration."""
    # Auto-start Discord bot + API server if token is configured
    _start_discord_if_configured()

    from face.app import main as face_main
    face_main()


def _start_discord_if_configured():
    """Start API server + Discord bot as daemon threads if token exists.

    Everything runs in a background thread so heavy imports (discord lib,
    ollama, etc.) never block the Face GUI from appearing.
    """
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        return  # no token → skip silently

    import threading

    def _boot_services():
        """Background thread: start API server + Discord bot."""
        import time, socket

        # 1. Start the API server so the Discord bot has an endpoint
        try:
            import uvicorn

            _port_free = True
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as _s:
                    _s.bind(("127.0.0.1", 8420))
            except OSError:
                _port_free = False

            if _port_free:
                def _run_server():
                    try:
                        uvicorn.run("server:app", host="127.0.0.1", port=8420,
                                    reload=False, log_level="warning")
                    except OSError:
                        pass
                threading.Thread(target=_run_server, daemon=True, name="APIServer").start()
                time.sleep(1.5)
                print("[Face] API server started on port 8420 (for Discord bot)")
            else:
                print("[Face] API server already running on port 8420")
        except ImportError:
            print("[Face] uvicorn not installed — Discord bot needs it.")
            return
        except Exception as e:
            print(f"[Face] Could not start API server: {e}")
            return

        # 2. Start the Discord bot (heavy import — discord library)
        try:
            from core.discord_bot import start_discord_bot
            bot = start_discord_bot(api_url="http://127.0.0.1:8420")
            if bot:
                bot.run_async()
                print("[Face] Discord bot started in background")
        except Exception as e:
            print(f"[Face] Discord bot failed to start: {e}")

    threading.Thread(target=_boot_services, daemon=True, name="DiscordBoot").start()


def cmd_reddit(args):
    """Reddit engagement — navigate, browse, post, or run a custom task.

    Usage:
        python main.py reddit browse <subreddit>       Browse and learn a subreddit
        python main.py reddit post <subreddit> <type>   Create a post (intro, showcase, discussion)
        python main.py reddit <free-form task>          Any Reddit task described in plain English
    """
    if not args:
        print("Usage: python main.py reddit <task>")
        print()
        print("Examples:")
        print("  reddit browse LocalLLaMA                Browse r/LocalLLaMA, read posts")
        print("  reddit post LocalLLaMA intro             Post an intro to r/LocalLLaMA")
        print("  reddit post LocalLLaMA showcase           Showcase OnyxKraken in r/LocalLLaMA")
        print("  reddit Navigate to r/Python and read the top 5 posts")
        print()
        print("Target subreddits: LocalLLaMA, blender, artificial, SideProject, Python")
        return

    from apps.modules.reddit_strategy import (
        PERSONA, SUBREDDITS, get_strategy_briefing, get_post_draft, POST_TEMPLATES,
    )

    a = _lazy_agent()
    a["discover_modules"]()

    # Get the Reddit module and set target subreddit
    from apps.registry import get_module
    reddit_mod = get_module("reddit")

    sub_cmd = args[0].lower()

    if sub_cmd == "browse":
        subreddit = args[1] if len(args) > 1 else "LocalLLaMA"
        if reddit_mod:
            reddit_mod.set_target_subreddit(subreddit)
        goal = (
            f"Open Reddit and navigate to r/{subreddit}. "
            f"Read the subreddit description and rules in the sidebar. "
            f"Then scroll through the first 10 posts, reading their titles and "
            f"noting what kinds of content get upvoted. "
            f"When done, report a summary of what you learned about this community."
        )
        print(f"[Reddit] Browsing r/{subreddit} to learn the community...")

    elif sub_cmd == "post":
        subreddit = args[1] if len(args) > 1 else "LocalLLaMA"
        post_type = args[2] if len(args) > 2 else "intro"
        if reddit_mod:
            reddit_mod.set_target_subreddit(subreddit)

        # Get the post draft guidance
        draft_guidance = get_post_draft(post_type, subreddit)
        persona = PERSONA

        if post_type == "intro":
            goal = (
                f"Open Reddit and navigate to r/{subreddit}. "
                f"First, read the subreddit rules and browse a few posts to understand the culture. "
                f"Then create a new text post introducing yourself.\n\n"
                f"You are posting as {persona['name']}, {persona['role']}.\n"
                f"Background: {persona['background']}\n\n"
                f"Write an authentic introduction post. The tone should be: {persona['voice']}\n\n"
                f"The post should:\n"
                f"- Start with a casual greeting and say who you are (Mark, solo dev)\n"
                f"- Explain what brought you to this community and what you are interested in\n"
                f"- Briefly describe OnyxKraken — what it is, why you built it, "
                f"how it uses local models like llama3.2-vision and deepseek-r1\n"
                f"- Connect your work to this community's interests\n"
                f"- End with a genuine question to invite discussion\n"
                f"- Optionally include the GitHub link: {persona['project_url']}\n\n"
                f"Keep it conversational and genuine. Short paragraphs. "
                f"Do NOT use marketing buzzwords. Do NOT oversell. "
                f"Write like a real person excited about what they built.\n\n"
                f"Title suggestion: something like 'Hey r/{subreddit} — built a local "
                f"desktop AI agent, wanted to share and say hi'\n\n"
                f"After writing the post, review it once, then submit it."
            )
            print(f"[Reddit] Posting intro to r/{subreddit} as {persona['name']}...")
        elif post_type == "showcase":
            goal = (
                f"Open Reddit and navigate to r/{subreddit}. "
                f"First, read the subreddit rules. "
                f"Then create a new text post showcasing OnyxKraken.\n\n"
                f"You are {persona['name']}, {persona['role']}.\n"
                f"Background: {persona['background']}\n\n"
                f"{draft_guidance}\n\n"
                f"GitHub: {persona['project_url']}\n"
                f"Write it, review it, then submit."
            )
            print(f"[Reddit] Posting showcase to r/{subreddit}...")
        elif post_type == "discussion":
            topic = " ".join(args[3:]) if len(args) > 3 else "local AI agents for desktop automation"
            goal = (
                f"Open Reddit and navigate to r/{subreddit}. "
                f"Create a discussion post about: {topic}\n\n"
                f"You are {persona['name']}, {persona['role']}.\n"
                f"{draft_guidance}\n\n"
                f"Start a genuine discussion. Share your perspective, ask the community."
            )
            print(f"[Reddit] Starting discussion in r/{subreddit}...")
        else:
            print(f"Unknown post type '{post_type}'. Use: intro, showcase, discussion")
            return
    else:
        # Free-form task — pass everything as the goal
        full_task = " ".join(args)
        # Try to detect subreddit from the text
        subreddit = None
        for sub_name in SUBREDDITS:
            if sub_name.lower() in full_task.lower():
                subreddit = sub_name
                break
        if reddit_mod and subreddit:
            reddit_mod.set_target_subreddit(subreddit)

        goal = f"Open Reddit and do the following: {full_task}"
        print(f"[Reddit] Task: {full_task}")

    a["run"](goal=goal, app_name="reddit")


def cmd_discord(args):
    """Start the Discord bot (requires server running separately or --serve flag)."""
    serve_too = "--serve" in args
    api_url = "http://127.0.0.1:8420"
    for i, arg in enumerate(args):
        if arg == "--api" and i + 1 < len(args):
            api_url = args[i + 1]

    if serve_too:
        try:
            import uvicorn  # noqa: F811
        except ImportError:
            print("Error: 'uvicorn' not installed. Run: pip install onyxkraken[server]")
            return
        import threading
        def _run_server():
            uvicorn.run("server:app", host="0.0.0.0", port=8420, reload=False, log_level="warning")
        threading.Thread(target=_run_server, daemon=True).start()
        import time; time.sleep(2)
        print("[Server] API started on port 8420")

    from core.discord_bot import start_discord_bot
    bot = start_discord_bot(api_url=api_url)
    if bot:
        bot.run()  # blocking


def cmd_activate(args):
    """Activate a license key."""
    from core.license import activate, deactivate, get_license, get_tier_display

    if not args:
        # Show current license status via hardened trial system
        try:
            from core.security import get_trial_manager
            trial = get_trial_manager()
            info = trial.trial_info()
            print(f"\n  Status: {info['message']}")
            if info["status"] == "trial":
                print(f"  Days remaining: {info['days_remaining']:.1f}")
                print(f"  Sessions used:  {info.get('sessions', '?')}")
            print(f"\n  To activate: python main.py activate YOUR-LICENSE-KEY")
            print(f"  Purchase ($149): https://markvizion.gumroad.com/l/onyxkraken")
        except Exception:
            lic = get_license()
            print(f"\n  Current license: {get_tier_display()}")
            if lic.key:
                print(f"  Key: {lic.key[:9]}...{lic.key[-4:]}")
            else:
                print(f"  No license key activated.")
                print(f"\n  To activate: python main.py activate ONYX-XXXX-XXXX-XXXX-XXXX")
                print(f"  Purchase at: https://markvizion.gumroad.com/l/onyxkraken")
        print()
        return

    if args[0].lower() == "remove":
        try:
            from core.security import get_trial_manager
            get_trial_manager().deactivate()
        except Exception:
            pass
        ok, msg = deactivate()
        print(f"\n  {msg}\n")
        return

    key = args[0]
    # Use hardened trial system for activation
    try:
        from core.security import get_trial_manager
        trial = get_trial_manager()
        ok, msg = trial.activate(key)
    except Exception:
        ok, msg = activate(key)
    print(f"\n  {msg}\n")


def print_help():
    print("Usage: python main.py [command] [args]")
    print()
    print("Commands:")
    print("  (no args)          Face GUI with chat panel + voice (default)")
    print("  cli                Interactive text mode")
    print("  <goal text>        Execute a single goal")
    print("  activate [key]     Activate a license key (or show current license)")
    print("  serve [--port N]   Start the FastAPI server (default port 8420)")
    print("  improve            Run a self-improvement cycle")
    print("  daemon             Start the autonomy daemon (interactive)")
    print("  voice              Voice input mode")
    print("  discord [--serve]  Start Discord bot (--serve auto-starts API)")
    print("  tools [list|verify|launch|test]  Manage self-built tools")
    print("  demo [name|--list] Autonomous self-demo (--record, --obs)")
    print("  generate <prompt>  LLM-driven generative Blender build (--no-qc)")
    print("  homebuilder <desc> Smart HomeBuilder Bot (--preset <name>, --list-presets)")
    print("  blender-voice      Voice-controlled Blender session (conversational workflow)")
    print("  mirror [--tune]    Mirror tool: analyze self or tune expressions")
    print("  demolog            Show demo history (--json for raw data)")
    print("  reddit <task>      Reddit engagement (navigate, post, browse)")
    print("  companion          Launch companion mode (--demo, --at HH:MM, --improve)")
    print("  record [name]      Record screen to MP4 (--quality, --fps)")
    print("  flywheel           Run flywheel experiment (--baseline, --report, --schedule N)")
    print("  studio             Launch 2.5D Animation Studio")
    print("  battle-arena       Launch Beat Battle Arena (standalone desktop app)")
    print("  battle-replay      Replay a saved battle visualization (--list, --test, <id>)")
    print("  help               Show this help")


def main():
    if len(sys.argv) <= 1:
        cmd_face()
        return

    cmd = sys.argv[1].lower()
    if cmd == "cli":
        interactive_mode()
    elif cmd == "activate":
        cmd_activate(sys.argv[2:])
    elif cmd == "serve":
        cmd_serve(sys.argv[2:])
    elif cmd == "improve":
        cmd_improve()
    elif cmd == "daemon":
        cmd_daemon(sys.argv[2:])
    elif cmd == "voice":
        cmd_voice()
    elif cmd == "discord":
        cmd_discord(sys.argv[2:])
    elif cmd == "tools":
        cmd_tools(sys.argv[2:])
    elif cmd == "demo":
        cmd_demo(sys.argv[2:])
    elif cmd == "record":
        cmd_record(sys.argv[2:])
    elif cmd == "mirror":
        cmd_mirror(sys.argv[2:])
    elif cmd == "demolog":
        cmd_demolog(sys.argv[2:])
    elif cmd == "reddit":
        cmd_reddit(sys.argv[2:])
    elif cmd == "companion":
        cmd_companion(sys.argv[2:])
    elif cmd == "conversation":
        from face.stage.shows.conversation_show import run_conversation_cli
        run_conversation_cli(sys.argv[2:])
    elif cmd == "generate":
        cmd_generate(sys.argv[2:])
    elif cmd == "homebuilder":
        cmd_homebuilder(sys.argv[2:])
    elif cmd == "blender-voice":
        cmd_blender_voice(sys.argv[2:])
    elif cmd == "flywheel":
        from eval.flywheel_experiment import main as flywheel_main
        sys.argv = [sys.argv[0]] + sys.argv[2:]  # strip 'flywheel' for argparse
        flywheel_main()
    elif cmd == "episode":
        cmd_episode(sys.argv[2:])
    elif cmd == "studio":
        from face.stage.animation_studio import launch_animation_studio
        launch_animation_studio()
    elif cmd in ("battle-arena", "battle", "beat-battle"):
        from face.beat_battle_app import launch
        launch()
    elif cmd == "battle-replay":
        from face.battle_stage import main as battle_stage_main
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        battle_stage_main()
    elif cmd == "face":
        cmd_face()
    elif cmd == "export-character":
        from face.stage.character_exporter import cmd_export_character
        cmd_export_character(sys.argv[2:])
    elif cmd in ("help", "--help", "-h"):
        print_help()
    else:
        # Treat all args as a goal
        a = _lazy_agent()
        goal = " ".join(sys.argv[1:])
        a["discover_modules"]()
        app_name = _infer_app_name(goal)
        a["run"](goal=goal, app_name=app_name)


def _check_trial_gate() -> bool:
    """Check if the trial is valid. Returns True if execution should proceed."""
    try:
        from core.security import get_trial_manager
        trial = get_trial_manager()

        if trial.is_valid():
            return True

        # Trial expired — only allow 'activate' and 'help' commands
        info = trial.trial_info()
        print("\n" + "=" * 60)
        print("  OnyxKraken — Trial Expired")
        print("=" * 60)
        print(f"  {info['message']}")
        print()
        print("  To continue using OnyxKraken:")
        print("    1. Purchase at https://markvizion.gumroad.com/l/onyxkraken")
        print("    2. Activate:  python main.py activate YOUR-LICENSE-KEY")
        print("=" * 60 + "\n")
        return False
    except Exception:
        # If security module fails, allow execution (graceful degradation)
        return True


def _register_shutdown():
    """Register security shutdown hook to persist trial elapsed time."""
    import atexit
    try:
        from core.security import get_trial_manager
        trial = get_trial_manager()
        atexit.register(trial.on_shutdown)
    except Exception:
        pass


if __name__ == "__main__":
    # Register security shutdown hook
    _register_shutdown()

    # Check if this is first run and show onboarding
    from face.onboarding import should_show_onboarding, OnboardingWizard, mark_onboarding_complete
    
    if should_show_onboarding():
        print("First run detected. Starting onboarding wizard...")
        wizard = OnboardingWizard()
        wizard.run()
        mark_onboarding_complete()
        print("\nOnboarding complete! Starting OnyxKraken...\n")

    # Trial gate — allow 'activate' and 'help' even when expired
    cmd_arg = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if cmd_arg not in ("activate", "help", "--help", "-h"):
        if not _check_trial_gate():
            sys.exit(1)

    main()

