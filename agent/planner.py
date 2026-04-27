"""Goal Planner — decomposes high-level goals into typed execution steps.

Extracted from orchestrator.py to keep each module focused.
"""

import json
import re
from typing import Optional

import config
from log import get_logger

_log = get_logger("planner")
from agent.model_router import router
try:
    from desktop.controller import list_desktop_items
except (ImportError, RuntimeError):
    def list_desktop_items(): return []
from memory.store import MemoryStore


def _call_planner(prompt: str) -> str:
    """Call the planner model with smart cloud→local fallback via ModelRouter."""
    return router.get_content("planner", [{"role": "user", "content": prompt}])


def decompose_goal(goal: str, memory: Optional[MemoryStore] = None) -> list[dict]:
    """Use the planner model to break a high-level goal into typed steps.

    Returns a list of dicts, each with:
        description: Human-readable step description.
        type: One of 'launch', 'interact', 'chat_wait'.
    """
    prompt = (
        "You are a Windows desktop automation planner. "
        "Break the following goal into a SHORT numbered list of high-level steps.\n\n"
        "AVAILABLE CAPABILITIES:\n"
        "- Desktop: open apps, click, type, scroll, press keys\n"
        "- Filesystem: read_file, write_file, search_files (direct — no app needed)\n"
        "- Terminal: run_command (execute shell commands directly)\n"
        "- Python: run_python (execute Python code directly — for math, computation, data processing)\n"
        "- Blender 3D: blender_python (build 3D models, scenes, render — has onyx_bpy toolkit)\n"
        "- Vision: read screenshots to understand what's on screen\n"
        "- BlakVision: blakvision_generate, blakvision_img2img, blakvision_inpaint, blakvision_upscale "
        "(AI image generation — SDXL-Lightning on RTX 3090, ~2.7s/image)\n"
        "- EVERA: evera_generate, evera_create_artist, evera_album, evera_cover, evera_stems "
        "(AI music generation — full tracks, albums, stems, covers)\n"
        "- GameKree8r: gamekree8r_new_game, gamekree8r_games, gamekree8r_metrics "
        "(autonomous AI game factory — generates playable HTML5 games)\n"
        "- WorldBuild: worldbuild_outline, worldbuild_chapter, worldbuild_book, worldbuild_world, "
        "worldbuild_character, worldbuild_script, worldbuild_article, worldbuild_copy "
        "(AI writing engine — books, scripts, worldbuilding, articles, marketing copy)\n"
        "- JustEdit: justedit_* (video editing — multi-track timeline, effects, export)\n\n"
        "IMPORTANT RULES:\n"
        "- Keep the list as short as possible. 1-4 steps.\n"
        "- For 3D MODELING tasks (build a chair, create a house, model furniture): "
        "use blender_python DIRECTLY. Just one step: 'Build the <object> using blender_python'.\n"
        "- For FILE operations (create, read, write, save text to file): use write_file or read_file DIRECTLY. "
        "Do NOT open Notepad or any app. Just one step: 'Write the file directly'.\n"
        "- For COMPUTATION tasks (calculate, math, factorial, data processing): use run_python DIRECTLY. "
        "Do NOT open Grok or any chat app. Just one step: 'Calculate using Python'.\n"
        "- For SYSTEM tasks (list files, check disk, run scripts): use run_command DIRECTLY. One step.\n"
        "- 'Open <app>' is always ONE step. Never break opening an app into sub-steps.\n"
        "- 'Type <text>' is always ONE step.\n"
        "- Do NOT include saving, closing, or cleanup steps unless the user explicitly asked.\n"
        "- For CHAT APPS (Grok, ChatGPT, Claude, etc.):\n"
        "  * After sending a message, ALWAYS add a step: 'Wait for the response and read it'\n"
        "  * If the user wants to reply, add: 'Compose and send a reply based on the response'\n"
        "  * Example for 'Open Grok and ask what is life':\n"
        "    1. Open Grok\n"
        "    2. Type the question and press Enter\n"
        "    3. Wait for Grok's response and read it\n"
        "- Return ONLY the numbered list, nothing else.\n\n"
    )

    # Inject memory context if available
    if memory:
        similar = memory.recall_similar_tasks(goal, limit=3)
        if similar:
            prompt += "PAST EXPERIENCE with similar tasks:\n"
            for t in similar:
                status = "succeeded" if t["success"] else "FAILED"
                prompt += f"  - \"{t['goal']}\" → {status}"
                if t.get("notes"):
                    prompt += f" ({t['notes']})"
                prompt += "\n"
            prompt += "Learn from these past results. Avoid approaches that failed.\n\n"

        failures = memory.recall_failures(limit=5)
        if failures:
            prompt += "KNOWN FAILURES to avoid:\n"
            for f in failures:
                prompt += f"  - {f['action']} on {f['target']} in {f['app']}: {f['error']}\n"
            prompt += "\n"

    # Inject knowledge store context if available
    try:
        from core.knowledge import get_knowledge_store
        knowledge = get_knowledge_store()
        relevant = knowledge.search(goal, limit=3)
        if relevant:
            prompt += "LEARNED KNOWLEDGE (from past experience):\n"
            for entry in relevant:
                prompt += f"  - {entry['content'][:150]}\n"
            prompt += "\n"
    except Exception as e:
        _log.debug(f"Could not inject knowledge context: {e}")

    # Inject self-improvement planning advice (closes the learning loop)
    try:
        from core.self_improvement import get_improvement_engine
        engine = get_improvement_engine()
        advice_modules = [
            m for m in engine._store.data.get("generated_modules", [])
            if m.get("name") == "planning_advice"
        ]
        if advice_modules:
            prompt += "PLANNING STRATEGIES (from self-improvement):\n"
            for mod in advice_modules[-3:]:
                try:
                    advice = json.loads(mod["code"])
                    if advice.get("strategy"):
                        prompt += f"  - Strategy: {advice['strategy'][:120]}\n"
                    for pitfall in advice.get("common_pitfalls", [])[:2]:
                        prompt += f"  - Pitfall to avoid: {pitfall[:80]}\n"
                    for tip in advice.get("tips", [])[:2]:
                        prompt += f"  - Tip: {tip[:80]}\n"
                except (json.JSONDecodeError, KeyError):
                    pass  # malformed planning advice entry — skip
            prompt += "\n"
    except Exception as e:
        _log.debug(f"Could not inject self-improvement advice: {e}")

    # Inject mind identity context
    try:
        from core.mind import get_mind
        mind = get_mind()
        identity_ctx = mind.get_identity_prompt()
        if identity_ctx:
            prompt = identity_ctx + "\n" + prompt
    except Exception as e:
        _log.debug(f"Could not inject mind identity context: {e}")

    # Inject toolsmith context (self-built tools ecosystem)
    try:
        from core.toolsmith import get_toolsmith_context, get_ecosystem_goal
        toolsmith_ctx = get_toolsmith_context()
        if toolsmith_ctx:
            prompt += toolsmith_ctx + "\n"
        ecosystem = get_ecosystem_goal()
        if ecosystem:
            prompt += ecosystem + "\n\n"
    except Exception as e:
        _log.debug(f"Could not inject toolsmith context: {e}")

    prompt += f"Goal: {goal}\n\n"
    prompt += "Available desktop items:\n"

    items = list_desktop_items()
    for item in items:
        prompt += f"  - {item['name']}\n"

    raw = _call_planner(prompt)
    # Parse numbered lines
    raw_steps = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit():
            parts = line.split(".", 1)
            if len(parts) == 2:
                raw_steps.append(parts[1].strip())
            else:
                raw_steps.append(line)
    if not raw_steps:
        raw_steps = [goal]

    # Tag each step with a type based on its content
    return [classify_step(s) for s in raw_steps]


def classify_step(description: str) -> dict:
    """Classify a planner step description into a typed step dict."""
    desc_lower = description.lower()

    # Filesystem / scripting: check BEFORE launch to prevent blender_python being
    # misclassified as "launch" when the step starts with "Run the blender_python..."
    fs_phrases = ("write the file", "create a file", "read the file", "save to file",
                  "write file", "read file", "search files", "run command",
                  "execute command", "list files", "write directly", "file directly",
                  "create file", "create a text", "save text",
                  "write text", "run the command", "terminal command", "print '",
                  'print "', "echo ", "dir ", "using a command",
                  "calculate", "compute", "run python", "python script",
                  "run a script", "execute python", "math ",
                  "blender_python", "blender_query", "onyx_bpy", "bpy script",
                  "bpy action", "toolkit",
                  "build a ", "create a ", "model a ", "make a ",
                  "build the ", "create the ", "model the ", "make the ",
                  "3d model", "in blender", "blender scene",
                  # Onyx Ecosystem — direct execution actions
                  "blakvision_", "blakvision ", "generate image", "generate an image",
                  "gamekree8r_", "gamekree8r ", "create a game", "generate a game",
                  "worldbuild_", "worldbuild ", "write a book", "write a chapter",
                  "write a script", "write an article", "generate outline",
                  "evera_", "evera ", "generate music", "generate a track",
                  "create a song", "create an album",
                  "justedit_", "justedit ", "edit video", "edit the video")
    if any(phrase in desc_lower for phrase in fs_phrases):
        return {"description": description, "type": "filesystem"}

    # Launch: step is specifically about opening/launching an app
    launch_verbs = ("open ", "launch ", "start ", "run ")
    if any(desc_lower.startswith(v) for v in launch_verbs):
        return {"description": description, "type": "launch"}

    # Filesystem: step mentions file extensions or absolute paths
    if re.search(r'\.(txt|csv|json|xml|log|md|py|bat|ps1)\b', desc_lower):
        return {"description": description, "type": "filesystem"}
    if re.search(r'[a-z]:\\', desc_lower) or '%userprofile%' in desc_lower:
        return {"description": description, "type": "filesystem"}

    # Chat wait: step is about waiting for / reading a chat AI response
    # (placed AFTER filesystem to avoid misclassifying computation results)
    chat_phrases = ("wait for", "read the response", "read it",
                    "wait for the response", "evaluate the response")
    if any(phrase in desc_lower for phrase in chat_phrases):
        return {"description": description, "type": "chat_wait"}

    # Default: general interaction step (type, click, etc.)
    return {"description": description, "type": "interact"}
