"""OnyxCore — Slim entry point for compiled distribution.

Only imports what the core component needs:
- Face GUI (Tkinter animated face)
- Chat / conversation
- Memory store
- Personality engine
- Security / trial system

Heavy optional deps (torch, scipy, pandas, pywinauto, etc.)
are excluded from this entry point.
"""

import sys
import os

# ---------------------------------------------------------------------------
# Security gate — must pass before anything else loads
# ---------------------------------------------------------------------------

def _check_security():
    """Run trial/license check. Blocks if expired."""
    try:
        from core.security import check_startup_security, get_trial_manager

        status = check_startup_security()

        if status["debugger"]:
            print("WARNING: Debugger detected.")

        if not status["trial_valid"]:
            trial = get_trial_manager()
            info = trial.trial_info()
            print("\n" + "=" * 60)
            print("  OnyxKraken — Trial Expired")
            print("=" * 60)
            print(f"  {info['message']}")
            print()
            print("  To continue using OnyxKraken:")
            print("    1. Purchase at https://markvizion.gumroad.com/l/onyxkraken")
            print("    2. Activate:  OnyxCore.exe activate YOUR-LICENSE-KEY")
            print("=" * 60 + "\n")

            # Allow 'activate' subcommand even when expired
            if len(sys.argv) > 1 and sys.argv[1].lower() == "activate":
                return True
            return False

        if not status["integrity_ok"]:
            print("ERROR: Integrity check failed. Application may be tampered.")
            return False

        return True

    except Exception as e:
        # Graceful degradation if security module fails
        print(f"WARNING: Security check skipped ({e})")
        return True


def _register_shutdown():
    """Persist trial elapsed time on exit."""
    import atexit
    try:
        from core.security import get_trial_manager
        atexit.register(get_trial_manager().on_shutdown)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Activation command
# ---------------------------------------------------------------------------

def cmd_activate(args):
    """Activate a license key."""
    try:
        from core.security import get_trial_manager
        trial = get_trial_manager()

        if not args:
            info = trial.trial_info()
            print(f"\n  Status: {info['message']}")
            if info["status"] == "trial":
                print(f"  Days remaining: {info['days_remaining']:.1f}")
            print(f"\n  To activate: OnyxCore activate YOUR-LICENSE-KEY")
            print(f"  Purchase ($149): https://markvizion.gumroad.com/l/onyxkraken\n")
            return

        if args[0].lower() == "remove":
            ok, msg = trial.deactivate()
            print(f"\n  {msg}\n")
            return

        ok, msg = trial.activate(args[0])
        print(f"\n  {msg}\n")

    except Exception as e:
        print(f"  License error: {e}")


# ---------------------------------------------------------------------------
# Main — Launch face GUI
# ---------------------------------------------------------------------------

def main():
    _register_shutdown()

    # Handle subcommands
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "activate":
            cmd_activate(sys.argv[2:])
            return
        if cmd in ("help", "--help", "-h"):
            print("Usage: OnyxCore [command]")
            print()
            print("  (no args)        Launch face GUI (default)")
            print("  activate [KEY]   Activate a license key")
            print("  help             Show this help")
            return

    # EULA acceptance (first launch only)
    try:
        from core.eula import check_eula_accepted, show_eula_dialog
        if not check_eula_accepted():
            if not show_eula_dialog():
                print("  License agreement declined. Exiting.")
                sys.exit(0)
    except Exception:
        pass  # Graceful degradation if EULA module unavailable

    # Security gate
    if not _check_security():
        sys.exit(1)

    # Show trial status
    try:
        from core.security import get_trial_manager
        trial = get_trial_manager()
        info = trial.trial_info()
        if info["status"] == "trial":
            print(f"  Trial: {info['days_remaining']:.0f} days remaining")
        elif info["status"] == "activated":
            print("  License: Activated")
    except Exception:
        pass

    # Launch face GUI
    try:
        from face.app import OnyxKrakenApp
        app = OnyxKrakenApp()
        app.run()
    except ImportError as e:
        print(f"ERROR: Could not load face GUI: {e}")
        print("Falling back to CLI mode...")
        _cli_fallback()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


def _cli_fallback():
    """Minimal CLI if GUI fails."""
    print("\nOnyxKraken Core — CLI Mode")
    print("Type 'quit' to exit.\n")
    while True:
        try:
            text = input("Onyx> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in ("quit", "exit", "q"):
            break
        print("  (GUI unavailable — core CLI is limited)")


if __name__ == "__main__":
    main()
