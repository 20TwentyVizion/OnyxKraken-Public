"""Test auto-generation by opening Calculator (no module exists for it).

Run directly:  python tests/test_autogen.py
"""

import os


def test_autogen():
    """Run the autogen integration test (requires Ollama + desktop)."""
    import config
    from log import setup_logging
    setup_logging(config.LOG_LEVEL)
    config.AUTONOMY_MODE = "auto"

    from agent.orchestrator import run

    result = run(goal="Open Calculator and type 5 + 3", app_name="unknown")
    print(f"\nResult: steps={result.steps_completed}/{result.steps_planned}, "
          f"actions={result.total_actions}, aborted={result.aborted}")

    gen_dir = os.path.join("apps", "generated")
    if os.path.isdir(gen_dir):
        files = os.listdir(gen_dir)
        print(f"\nGenerated modules: {files}")
        for f in files:
            path = os.path.join(gen_dir, f)
            with open(path) as fh:
                print(f"\n--- {f} ---")
                print(fh.read()[:500])
    else:
        print("\nNo generated modules directory yet.")


if __name__ == "__main__":
    test_autogen()
