"""OnyxKraken MCP Server — Expose capabilities via Model Context Protocol.

Allows any MCP-compatible client (Windsurf, Claude Desktop, Cursor, etc.)
to discover and invoke OnyxKraken's tools: goal execution, mind state,
knowledge search, voice synthesis, ecosystem dispatch, and more.

Usage:
  python mcp_server.py                  # stdio transport (default)
  python mcp_server.py --sse            # SSE transport on port 8421
  python mcp_server.py --streamable     # Streamable HTTP on port 8421

Add to MCP client config (e.g. mcp_config.json):
  {
    "mcpServers": {
      "onyxkraken": {
        "command": "python",
        "args": ["path/to/OnyxKraken/mcp_server.py"]
      }
    }
  }
"""

import logging
import os
import sys
import threading
import time
from typing import Optional

from fastmcp import FastMCP

_log = logging.getLogger("mcp_server")

# ---------------------------------------------------------------------------
# MCP Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "OnyxKraken",
    instructions=(
        "Autonomous desktop agent with 6-service ecosystem. "
        "Execute goals, query mind state, search knowledge, "
        "synthesize speech, dispatch ecosystem services, and more."
    ),
)


# ---------------------------------------------------------------------------
# Tool: Agent — Goal Execution
# ---------------------------------------------------------------------------

def _submit_goal(goal: str, app_name: str = "unknown") -> dict:
    from routes._state import state, run_task_sync
    if state.running:
        return {"error": f"Agent is busy with: {state.current_goal}", "status": "busy"}
    result = run_task_sync(goal)
    return result


def _get_agent_status() -> dict:
    from routes._state import state
    return state.to_dict()


def _get_task_history(limit: int = 20) -> dict:
    from memory.store import MemoryStore
    memory = MemoryStore()
    tasks = memory.get_all().get("task_history", [])
    return {"total": len(tasks), "tasks": tasks[-limit:]}


def _get_agent_skills() -> dict:
    from agent.action_dispatch import get_registered_actions
    actions = get_registered_actions()
    return {
        "skills": [
            {"name": a, "description": f"Execute '{a}' action on the desktop"}
            for a in sorted(actions)
        ]
    }


@mcp.tool()
def submit_goal(goal: str, app_name: str = "unknown") -> dict:
    """Submit a goal for OnyxKraken to execute autonomously.

    The agent decomposes the goal into steps and executes them
    using desktop automation (mouse, keyboard, Blender, Edge, etc.).

    Args:
        goal: High-level goal description (e.g. "Create a 3D scene in Blender with a red cube").
        app_name: Target application hint (e.g. "blender", "edge"). Default "unknown".

    Returns:
        Execution result with steps completed, time, and success status.
    """
    return _submit_goal(goal, app_name)


@mcp.tool()
def get_agent_status() -> dict:
    """Get the current status of the OnyxKraken agent.

    Returns whether the agent is running, the current goal,
    current step, and the last execution result.
    """
    return _get_agent_status()


@mcp.tool()
def get_task_history(limit: int = 20) -> dict:
    """Get the agent's task execution history.

    Args:
        limit: Maximum number of recent tasks to return. Default 20.

    Returns:
        List of past task executions with success/failure, timing, and details.
    """
    return _get_task_history(limit)


@mcp.tool()
def get_agent_skills() -> dict:
    """List all registered agent capabilities/actions.

    Returns the set of desktop automation actions OnyxKraken can perform
    (click, type, screenshot, run_blender_script, etc.).
    """
    return _get_agent_skills()


# ---------------------------------------------------------------------------
# Tool: Mind — Mood, Reflection, Identity
# ---------------------------------------------------------------------------

def _get_mind_state() -> dict:
    from core.mind import get_mind
    mind = get_mind()
    return mind.get_stats()


def _trigger_reflection() -> dict:
    from core.mind import get_mind
    mind = get_mind()
    def _run():
        try:
            mind.reflect()
        except Exception as e:
            _log.warning("Reflection failed: %s", e)
    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started", "message": "Reflection cycle initiated."}


def _generate_proactive_goal() -> dict:
    from core.mind import get_mind
    mind = get_mind()
    goal = mind.generate_proactive_goal()
    if goal:
        return {"goal": goal, "status": "generated"}
    return {"goal": None, "status": "rest", "message": "Mind decided to rest."}


@mcp.tool()
def get_mind_state() -> dict:
    """Get OnyxKraken's current mental state.

    Returns identity, mood, focus area, strengths, weaknesses,
    and recent reflection insights. The mood affects voice synthesis
    (Fish Audio S2 inline emotional tags).
    """
    return _get_mind_state()


@mcp.tool()
def trigger_reflection() -> dict:
    """Trigger a mind reflection cycle.

    OnyxKraken analyzes its recent task performance,
    updates mood/focus/strengths/weaknesses, and generates insights.
    Runs asynchronously in background.
    """
    return _trigger_reflection()


@mcp.tool()
def generate_proactive_goal() -> dict:
    """Ask the Mind to generate a proactive self-improvement goal.

    OnyxKraken examines its weaknesses and generates a goal
    to practice and improve. May return 'rest' if no goal is needed.
    """
    return _generate_proactive_goal()


# ---------------------------------------------------------------------------
# Tool: Knowledge — RAG Store
# ---------------------------------------------------------------------------

def _search_knowledge(query: str, category: Optional[str] = None, limit: int = 10) -> dict:
    from core.knowledge import get_knowledge_store
    store = get_knowledge_store()
    results = store.search(query, category=category, limit=limit)
    return {"results": results, "count": len(results)}


def _add_knowledge(content: str, category: str = "general", tags: Optional[list[str]] = None, source: str = "") -> dict:
    from core.knowledge import get_knowledge_store
    store = get_knowledge_store()
    entry_id = store.add(content, category=category, tags=tags or [], source=source)
    return {"id": entry_id, "status": "added"}


def _get_knowledge_stats() -> dict:
    from core.knowledge import get_knowledge_store
    store = get_knowledge_store()
    return store.get_stats()


@mcp.tool()
def search_knowledge(query: str, category: Optional[str] = None, limit: int = 10) -> dict:
    """Search OnyxKraken's knowledge base using semantic similarity.

    Args:
        query: Natural language search query.
        category: Optional category filter (e.g. "blender", "general").
        limit: Maximum results to return. Default 10.
    """
    return _search_knowledge(query, category, limit)


@mcp.tool()
def add_knowledge(content: str, category: str = "general", tags: Optional[list[str]] = None, source: str = "") -> dict:
    """Add a new entry to OnyxKraken's knowledge base.

    Args:
        content: The knowledge content to store.
        category: Category for organization (e.g. "blender", "python", "general").
        tags: Optional list of tags for filtering.
        source: Where this knowledge came from.
    """
    return _add_knowledge(content, category, tags, source)


@mcp.tool()
def get_knowledge_stats() -> dict:
    """Get statistics about the knowledge store."""
    return _get_knowledge_stats()


# ---------------------------------------------------------------------------
# Tool: Voice — TTS with mood-aware emotional tags
# ---------------------------------------------------------------------------

def _speak(text: str, mood: str = "ready") -> dict:
    from core.voice import speak_with_mood
    threading.Thread(target=speak_with_mood, args=(text,), kwargs={"mood": mood}, daemon=True).start()
    return {"status": "speaking", "text": text[:100], "mood": mood}


def _synthesize_to_file(text: str, character: str = "onyx", mood: str = "ready") -> dict:
    from core.voice import synthesize_to_file as _synth
    path = _synth(text, character=character, mood=mood)
    if path:
        return {"path": path, "status": "ok"}
    return {"path": None, "status": "failed", "message": "No TTS backend available."}


@mcp.tool()
def speak(text: str, mood: str = "ready") -> dict:
    """Synthesize and play speech through OnyxKraken's voice system.

    Args:
        text: Text to speak aloud.
        mood: Emotional mood for voice modulation (ready, confident, curious, etc.).
    """
    return _speak(text, mood)


@mcp.tool()
def synthesize_to_file(text: str, character: str = "onyx", mood: str = "ready") -> dict:
    """Synthesize speech to a file without playing it.

    Args:
        text: Text to synthesize.
        character: Voice character (onyx, xyno, volt, nova, sage, blaze, frost, ember).
        mood: Emotional mood for Fish Audio S2 inline tags.
    """
    return _synthesize_to_file(text, character, mood)


# ---------------------------------------------------------------------------
# Tool: Ecosystem — Service dispatch and workflows
# ---------------------------------------------------------------------------

def _ecosystem_health(force: bool = False) -> dict:
    from apps.onyx_ecosystem import get_ecosystem
    eco = get_ecosystem()
    return eco.dashboard(force=force)


def _ecosystem_dispatch(service: str, action: str, params: Optional[dict] = None) -> dict:
    from apps.onyx_ecosystem import get_ecosystem
    eco = get_ecosystem()
    return eco.dispatch(service, action, params or {})


def _list_ecosystem_services() -> dict:
    from apps.onyx_ecosystem import get_ecosystem
    eco = get_ecosystem()
    services = {}
    for name, info in eco.services.items():
        services[name] = {
            "name": info.name, "description": info.description,
            "category": info.category, "capabilities": info.capabilities,
            "port": info.port,
        }
    return {"services": services, "count": len(services)}


def _list_workflows() -> dict:
    from apps.workflows import get_workflows
    workflows = get_workflows()
    return {
        "workflows": [
            {"id": w.id, "name": w.name, "description": w.description, "steps": len(w.steps)}
            for w in workflows
        ]
    }


def _run_workflow(workflow_id: str, params: Optional[dict] = None, context: Optional[dict] = None) -> dict:
    from apps.onyx_ecosystem import get_ecosystem
    eco = get_ecosystem()
    return eco.run_workflow(workflow_id, params=params or {}, context=context or {})


@mcp.tool()
def ecosystem_health(force: bool = False) -> dict:
    """Get the full ecosystem health dashboard.

    Args:
        force: If True, re-probe all services (slower but fresh data).
    """
    return _ecosystem_health(force)


@mcp.tool()
def ecosystem_dispatch(service: str, action: str, params: Optional[dict] = None) -> dict:
    """Dispatch an action to a specific ecosystem service.

    Args:
        service: Target service (blakvision, evera, gamekree8r, worldbuild, justedit, blender, socialbot).
        action: Action identifier (e.g. 'blakvision_generate').
        params: Action-specific parameters dict.
    """
    return _ecosystem_dispatch(service, action, params)


@mcp.tool()
def list_ecosystem_services() -> dict:
    """List all registered ecosystem services and their capabilities."""
    return _list_ecosystem_services()


@mcp.tool()
def list_workflows() -> dict:
    """List available ecosystem workflow templates."""
    return _list_workflows()


@mcp.tool()
def run_workflow(workflow_id: str, params: Optional[dict] = None, context: Optional[dict] = None) -> dict:
    """Execute an ecosystem workflow.

    Args:
        workflow_id: Workflow template ID (e.g. 'game_with_assets', 'music_video').
        params: Workflow-specific parameters.
        context: Initial context variables for interpolation.
    """
    return _run_workflow(workflow_id, params, context)


# ---------------------------------------------------------------------------
# Tool: Memory — Agent memory and learning
# ---------------------------------------------------------------------------

def _get_memory() -> dict:
    from memory.store import MemoryStore
    memory = MemoryStore()
    return memory.get_all()


def _get_improvement_stats() -> dict:
    from core.self_improvement import get_self_improvement
    si = get_self_improvement()
    return si.get_stats()


@mcp.tool()
def get_memory() -> dict:
    """Get the full contents of the agent's memory store."""
    return _get_memory()


@mcp.tool()
def get_improvement_stats() -> dict:
    """Get self-improvement statistics."""
    return _get_improvement_stats()


# ---------------------------------------------------------------------------
# Tool: Drive — Animation, pose, and emotion control for Onyx characters
# ---------------------------------------------------------------------------

def _drive_publish(kind: str, character: str, **payload) -> dict:
    from core.drive import DriveEvent, get_bus
    event = DriveEvent(kind=kind, character=character, payload=payload, source="mcp")
    get_bus().publish(event)
    return {"ok": True, "event": event.to_dict()}


@mcp.tool()
def drive_emotion(emotion: str = "neutral", character: str = "onyx",
                  intensity: float = 1.0, hold_ms: int = 0,
                  mix: dict | None = None) -> dict:
    """Drive a character's face emotion.

    Args:
        emotion: One of neutral, thinking, curious, satisfied, confused,
                 determined, amused, surprised, listening, working, focused,
                 happy, sad, excited, skeptical, proud, sleep.
        character: Character id (default 'onyx'). See list_drive_catalog().
        intensity: 0..1 emotional intensity multiplier.
        hold_ms: Optional ms to hold before allowing a new emotion.
        mix: Optional weighted blend, e.g. {"curious": 0.7, "amused": 0.3}.
             When provided, overrides `emotion` (the dominant key becomes
             the announced emotion name).
    """
    from core.animation import get_catalog
    catalog = get_catalog()
    payload: dict = {"emotion": emotion, "intensity": intensity, "hold_ms": hold_ms}
    if mix:
        unknown = [e for e in mix if catalog.emotion(e) is None]
        if unknown:
            return {"error": f"Unknown emotion(s) in mix: {unknown}"}
        clean = {k: float(v) for k, v in mix.items() if v > 0}
        if not clean:
            return {"error": "mix must have at least one positive weight"}
        payload["mix"] = clean
        payload["emotion"] = max(clean, key=clean.get)
    elif catalog.emotion(emotion) is None:
        return {"error": f"Unknown emotion: {emotion!r}"}
    return _drive_publish("emotion", character.lower(), **payload)


@mcp.tool()
def drive_pose(pose: str, character: str = "onyx", transition_ms: int = 300) -> dict:
    """Drive a character's body pose.

    Args:
        pose: Pose id (e.g. confident, thinking, wave, point, dj, crossed).
        character: Character id (default 'onyx').
        transition_ms: Tween duration to the new pose.
    """
    from core.animation import get_catalog
    if get_catalog().pose(pose) is None:
        return {"error": f"Unknown pose: {pose!r}"}
    return _drive_publish("pose", character.lower(), pose=pose,
                          transition_ms=transition_ms)


@mcp.tool()
def drive_animation(animation: str, character: str = "onyx", loop: bool = False) -> dict:
    """Play a named body animation on a character.

    Args:
        animation: Animation id (e.g. wave, nod, celebrate, idle_breathe,
                   talk_gesture, dj_groove, point_gesture, shrug_anim).
        character: Character id (default 'onyx').
        loop: If True, play continuously until stopped.
    """
    from core.animation import get_catalog
    if get_catalog().body_anim(animation) is None:
        return {"error": f"Unknown animation: {animation!r}"}
    return _drive_publish("body_anim", character.lower(),
                          animation=animation, loop=loop)


@mcp.tool()
def drive_speak(text: str, character: str = "onyx", mood: str = "ready",
                auto_pose: bool = True) -> dict:
    """Speak text through a character with auto face/body dispatch.

    Pipes text through the intent classifier so *action* tags trigger the
    matching face emotion + body pose + animation. Other clients (the
    desktop GUI, browser canvas via WebSocket) will receive the events
    and animate in sync with TTS.

    Args:
        text: What to say (may contain *action* roleplay tags).
        character: Character id (default 'onyx').
        mood: Voice mood for TTS (ready, confident, curious, etc.).
        auto_pose: If True, dispatch pose+anim from the emotion link.
    """
    from core.intent import classify
    from core.animation import get_catalog

    cid = character.lower()
    result = classify(text)
    _drive_publish("speak", cid, text=result.clean_text, mood=mood, original=text)

    catalog = get_catalog()
    primary = result.primary_emotion
    if primary:
        _drive_publish("emotion", cid, emotion=primary, intensity=1.0)
        if auto_pose:
            link_pose, link_anim = catalog.link_for(primary)
            if link_pose and not result.poses:
                result.poses.append(link_pose)
            if link_anim and not result.body_anims:
                result.body_anims.append(link_anim)
    for p in result.poses:
        if catalog.pose(p):
            _drive_publish("pose", cid, pose=p, transition_ms=300)
    for a in result.body_anims:
        if catalog.body_anim(a):
            _drive_publish("body_anim", cid, animation=a, loop=False)

    return {
        "ok": True,
        "clean_text": result.clean_text,
        "emotions": result.emotions,
        "poses": result.poses,
        "body_anims": result.body_anims,
    }


@mcp.tool()
def list_drive_catalog() -> dict:
    """List every emotion, pose, body animation, and character available
    to the drive_* tools."""
    from core.animation import get_catalog
    from core.characters import get_registry
    cat = get_catalog().to_dict()
    return {
        "emotions": [e["id"] for e in cat["emotions"]],
        "poses": [p["id"] for p in cat["poses"]],
        "body_anims": [b["id"] for b in cat["body_anims"]],
        "characters": [c.id for c in get_registry().all()],
        "emotion_links": cat["emotion_links"],
    }


@mcp.tool()
def play_episode(episode_id: str, vars: Optional[dict] = None) -> dict:
    """Play a scripted episode by id.

    Episodes are YAML files in data/episodes/ describing a sequence of
    beats (dialogue, pose, emotion, body animation, branching choices).

    Args:
        episode_id: Filename stem (e.g. 'demo_intro' for data/episodes/demo_intro.yaml).
        vars: Optional template variables for substitution into beat text.
    """
    try:
        from core.episode.player import play_episode as _play
    except Exception as e:
        return {"error": f"Episode player unavailable: {e}"}
    return _play(episode_id, vars=vars or {})


# ---------------------------------------------------------------------------
# Resources: Static info
# ---------------------------------------------------------------------------

@mcp.resource("onyx://identity")
def get_identity() -> str:
    """OnyxKraken's core identity and personality."""
    from core.mind import get_mind
    mind = get_mind()
    stats = mind.get_stats()
    return (
        f"Name: {stats.get('identity', 'OnyxKraken')}\n"
        f"Mood: {stats.get('mood', 'ready')}\n"
        f"Focus: {stats.get('focus', 'none')}\n"
        f"Strengths: {', '.join(stats.get('strengths', []))}\n"
        f"Weaknesses: {', '.join(stats.get('weaknesses', []))}\n"
    )


@mcp.resource("onyx://capabilities")
def get_capabilities() -> str:
    """Summary of all OnyxKraken capabilities."""
    return (
        "OnyxKraken — Autonomous Desktop Agent\n"
        "======================================\n\n"
        "Core Capabilities:\n"
        "- Goal execution: Decompose goals into steps, execute via desktop automation\n"
        "- Mind system: Mood tracking, reflection, proactive goal generation\n"
        "- Knowledge base: Semantic RAG store with learned patterns\n"
        "- Voice I/O: Fish Audio S2 (emotional TTS), ElevenLabs, Edge TTS, Whisper STT\n"
        "- Self-improvement: Failure analysis, capability gap detection, strategy learning\n\n"
        "Ecosystem Services:\n"
        "- BlakVision: AI image generation (SDXL-Lightning, ComfyUI)\n"
        "- EVERA: AI music generation (ACE-Step, full tracks/albums)\n"
        "- GameKree8r: AI game factory (HTML5 browser games)\n"
        "- WorldBuild: AI writing engine (books, scripts, worldbuilding)\n"
        "- JustEdit: Video editing (multi-track timeline, effects, export)\n"
        "- Blender: 3D modeling, rendering, animation (bpy scripting)\n"
        "- SocialBot: Autonomous Bluesky social presence\n\n"
        "Workflows:\n"
        "- game_with_assets: Conceive + generate game + art + music\n"
        "- music_video: Generate track + visuals + assemble video\n"
        "- marketing_bundle: Copy + visuals + audio for campaigns\n"
        "- concept_to_game: Full pipeline from idea to published game\n"
        "- album_release: Multi-track album + cover art + press kit\n"
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    transport = "stdio"
    port = int(os.environ.get("MCP_PORT", "8421"))

    if "--sse" in sys.argv:
        transport = "sse"
    elif "--streamable" in sys.argv:
        transport = "streamable-http"

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "sse":
        mcp.run(transport="sse", host="127.0.0.1", port=port)
    else:
        mcp.run(transport="streamable-http", host="127.0.0.1", port=port)
