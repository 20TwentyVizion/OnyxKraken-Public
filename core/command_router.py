"""Command Router — fast-path dispatcher for known commands.

Intercepts user input BEFORE the LLM planning chain. Pattern-matched
commands execute instantly (~0ms) instead of going through the full
orchestrator (~5-15s).

Returns (handled: bool, response: str | None). If handled is True,
the caller should NOT send the input to the orchestrator.

Usage:
    from core.command_router import route_command

    handled, response = route_command(text, emit_fn)
    if handled:
        return  # done — no LLM needed
    # else fall through to orchestrator
"""

import logging
import os
import re
from typing import Callable, Optional

_log = logging.getLogger("core.command_router")

# ---------------------------------------------------------------------------
# Route result
# ---------------------------------------------------------------------------

class RouteResult:
    """Result of a command route attempt."""
    __slots__ = ("handled", "response", "speak")

    def __init__(self, handled: bool = False, response: str = "",
                 speak: str = ""):
        self.handled = handled
        self.response = response
        self.speak = speak

    @staticmethod
    def miss():
        return RouteResult(handled=False)

    @staticmethod
    def hit(response: str, speak: str = ""):
        return RouteResult(handled=True, response=response,
                           speak=speak or response)


# ---------------------------------------------------------------------------
# Tool / App launch commands
# ---------------------------------------------------------------------------

_TOOL_PATTERNS = [
    # "open calculator", "launch notepad", "start my calculator"
    re.compile(
        r"^(?:open|launch|start|run|use)\s+"
        r"(?:the\s+|my\s+|onyx\s+|onyx's\s+)?"
        r"(?P<tool>.+)$",
        re.IGNORECASE,
    ),
]

def _route_tool_launch(text: str) -> RouteResult:
    """Try to match a tool/app launch command."""
    for pat in _TOOL_PATTERNS:
        m = pat.match(text.strip())
        if not m:
            continue
        tool_name = m.group("tool").strip().lower()

        # Try internal tools first (ToolForge)
        try:
            from core.toolsmith import find_internal_replacement, launch_tool, get_tool
            # Direct name match
            tool = get_tool(tool_name)
            if tool and tool.is_verified:
                proc = launch_tool(tool_name)
                if proc:
                    return RouteResult.hit(
                        f"Opened {tool.display_name}.",
                        f"Opening {tool.display_name}.",
                    )

            # Check replacements (e.g., "calc" → calculator)
            replacement = find_internal_replacement(tool_name)
            if replacement:
                proc = launch_tool(replacement.name)
                if proc:
                    return RouteResult.hit(
                        f"Opened {replacement.display_name}.",
                        f"Opening {replacement.display_name}.",
                    )
        except Exception as e:
            _log.debug("Toolsmith lookup failed: %s", e)

        # Fall through — let the orchestrator handle external app launches
        return RouteResult.miss()

    return RouteResult.miss()


# ---------------------------------------------------------------------------
# Blender build commands
# ---------------------------------------------------------------------------

_BUILD_PATTERNS = [
    # "build a modern office", "create a house", "generate a spaceship"
    re.compile(
        r"^(?:build|create|generate|make|construct|design)\s+"
        r"(?:me\s+)?(?:a\s+|an\s+|the\s+)?"
        r"(?P<prompt>.+?)(?:\s+in\s+blender)?$",
        re.IGNORECASE,
    ),
]

# Keywords that indicate a Blender 3D build (vs. generic "build me a plan")
_3D_KEYWORDS = {
    "house", "building", "cabin", "castle", "room", "office", "kitchen",
    "bedroom", "bathroom", "scene", "interior", "exterior", "landscape",
    "city", "street", "tower", "bridge", "ship", "spaceship", "car",
    "vehicle", "robot", "character", "furniture", "table", "chair",
    "sofa", "couch", "lamp", "tree", "garden", "park", "station",
    "warehouse", "factory", "church", "temple", "mosque", "school",
    "hospital", "restaurant", "cafe", "bar", "shop", "store", "mall",
    "apartment", "mansion", "cottage", "hut", "tent", "pyramid",
    "monument", "statue", "fountain", "pool", "garage", "barn",
    "playground", "stadium", "arena", "theater", "cinema", "museum",
    "library", "laboratory", "bunker", "dungeon", "throne",
}


def _route_blender_build(text: str) -> RouteResult:
    """Try to match a Blender generative build command."""
    for pat in _BUILD_PATTERNS:
        m = pat.match(text.strip())
        if not m:
            continue
        prompt = m.group("prompt").strip()
        words = set(prompt.lower().split())

        # Only route to Blender if the prompt contains 3D-related keywords
        # or explicitly mentions "in blender" or "3d"
        is_3d = bool(words & _3D_KEYWORDS) or "blender" in text.lower() or "3d" in text.lower()
        if not is_3d:
            return RouteResult.miss()

        # Route to generative builder
        return RouteResult.hit(
            f"Starting Blender build: {prompt}",
            f"Building {prompt} in Blender.",
        )

    return RouteResult.miss()


# ---------------------------------------------------------------------------
# Camera / viewport commands (for gesture or voice control in Blender)
# ---------------------------------------------------------------------------

_CAMERA_PATTERNS = [
    re.compile(r"^(?:show\s+me|look\s+at|zoom\s+(?:in|out)|pan|orbit|rotate\s+(?:the\s+)?(?:view|camera))", re.IGNORECASE),
    re.compile(r"^(?:reset\s+(?:the\s+)?(?:view|camera))", re.IGNORECASE),
]


def _route_camera(text: str) -> RouteResult:
    """Match viewport camera commands."""
    for pat in _CAMERA_PATTERNS:
        if pat.match(text.strip()):
            return RouteResult.hit(
                f"Camera command: {text}",
                "",  # no speech for camera commands
            )
    return RouteResult.miss()


# ---------------------------------------------------------------------------
# Quick system commands
# ---------------------------------------------------------------------------

_SYSTEM_COMMANDS = {
    # Screenshot / vision
    "take a screenshot": ("screenshot", "Taking a screenshot."),
    "screenshot": ("screenshot", "Taking a screenshot."),
    "what's on my screen": ("describe_screen", "Let me look at your screen."),
    "what do you see": ("describe_screen", "Let me look."),
    "describe my screen": ("describe_screen", "Looking at your screen."),

    # Memory
    "what do you remember": ("recall_all", "Let me check my memory."),

    # Mode switching
    "work mode": ("mode_work", "Switching to work mode."),
    "chat mode": ("mode_companion", "Switching to chat mode."),
    "companion mode": ("mode_companion", "Switching to companion mode."),

    # System
    "undo": ("undo", "Undoing."),
    "save": ("save", "Saving."),
    "stop": ("stop", "Stopping."),
    "cancel": ("cancel", "Cancelling."),

    # Music
    "play some music": ("music_play", "Playing music."),
    "stop music": ("music_stop", "Stopping music."),
    "pause music": ("music_pause", "Pausing music."),
    "next track": ("music_next", "Next track."),
}


def _route_system(text: str) -> RouteResult:
    """Match exact system commands."""
    normalized = text.strip().lower().rstrip(".!?")
    if normalized in _SYSTEM_COMMANDS:
        cmd_id, speak = _SYSTEM_COMMANDS[normalized]
        return RouteResult.hit(
            f"[system:{cmd_id}] {speak}",
            speak,
        )
    return RouteResult.miss()


# ---------------------------------------------------------------------------
# "Remember" commands
# ---------------------------------------------------------------------------

_REMEMBER_PATTERN = re.compile(
    r"^(?:remember|note|save|store)\s+(?:that\s+)?(?P<fact>.+)$",
    re.IGNORECASE,
)


def _route_remember(text: str) -> RouteResult:
    """Match memory storage commands."""
    m = _REMEMBER_PATTERN.match(text.strip())
    if m:
        fact = m.group("fact").strip()
        try:
            from memory.store import save_knowledge
            save_knowledge(fact)
            return RouteResult.hit(
                f"Got it. I'll remember: {fact}",
                "Got it. Saved to memory.",
            )
        except Exception as e:
            _log.debug("Memory save failed: %s", e)
            return RouteResult.hit(
                f"I'll remember that: {fact}",
                "Noted.",
            )
    return RouteResult.miss()


# ---------------------------------------------------------------------------
# Music commands
# ---------------------------------------------------------------------------

_MUSIC_PATTERNS = [
    # "make me a trap beat", "create a jazz track", "generate rock music"
    re.compile(
        r"^(?:make|create|produce|generate)\s+"
        r"(?:me\s+)?(?:a\s+|some\s+)?"
        r"(?P<genre>\w+)\s+(?:music|track|beat|song)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:play|start)\s+(?:a\s+)?(?:beat\s+)?battle",
        re.IGNORECASE,
    ),
    # Vague music requests → MusicProducer handles gathering
    # "make me a song", "make me a beat", "create a track", "generate music"
    re.compile(
        r"^(?:make|create|produce|generate)\s+(?:me\s+)?(?:a\s+|some\s+)?"
        r"(?:music|track|beat|song|tune|jam|banger)",
        re.IGNORECASE,
    ),
    # "I want some music", "I want a beat", "give me a track"
    re.compile(
        r"^(?:i\s+want|i\s+need|give\s+me|let'?s?\s+(?:make|create))\s+"
        r"(?:a\s+|some\s+|to\s+(?:make|create)\s+(?:a\s+|some\s+)?)?"
        r"(?:(?P<genre>\w+)\s+)?(?:music|track|beat|song|tune)",
        re.IGNORECASE,
    ),
    # "can you make music", "make some tunes"
    re.compile(
        r"^(?:can\s+you\s+)?(?:make|create|produce|generate)\s+"
        r"(?:me\s+)?(?:some\s+)?(?:(?P<genre>\w+)\s+)?(?:music|tunes?|beats?|songs?|tracks?)",
        re.IGNORECASE,
    ),
]

# DJ Mode patterns
_DJ_PATTERNS = [
    # "do a 15 minute dj set", "start a dj set", "dj mode"
    re.compile(
        r"^(?:do|start|run|play|begin)\s+(?:a\s+|an\s+)?"
        r"(?:(?P<duration>\d+)\s*(?:minute|min|m)\s+)?"
        r"(?:dj\s+set|dj\s+session|dj\s+mode)",
        re.IGNORECASE,
    ),
    # "make me 5 trap beats", "generate 3 jazz tracks"
    re.compile(
        r"^(?:make|create|produce|generate|give)\s+(?:me\s+)?"
        r"(?P<count>\d+)\s+"
        r"(?P<genre>[\w\-]+)\s+(?:beats?|tracks?|songs?)",
        re.IGNORECASE,
    ),
    # "dj set in jazz", "dj set genre trap"
    re.compile(
        r"^dj\s+(?:set|session|mode)"
        r"(?:\s+(?:in|genre|style)\s+(?P<genre>[\w\-]+))?",
        re.IGNORECASE,
    ),
]

# Battle patterns
_BATTLE_PATTERNS = [
    re.compile(
        r"^(?:start|run|play|do)\s+(?:a\s+|the\s+)?"
        r"(?:beat\s+)?battle"
        r"(?:\s+(?:with|vs|against|versus)\s+(?P<opponent>.+))?",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:rematch|battle\s+rematch)"
        r"(?:\s+(?:with|vs|against)\s+(?P<opponent>.+))?",
        re.IGNORECASE,
    ),
    # "battle history", "battle record"
    re.compile(
        r"^(?:battle|dj)\s+(?:history|record|stats|score)",
        re.IGNORECASE,
    ),
]

# User-upload battle patterns
_USER_BATTLE_PATTERNS = [
    # "judge my beats", "judge these tracks", "judge my beats vs AI"
    re.compile(
        r"^(?:judge|rate|score|compare)\s+(?:my|these|the|some)\s+"
        r"(?:beats?|tracks?|songs?)"
        r"(?:\s+(?:vs|against|versus)\s+(?:ai|onyx|the\s+ai))?",
        re.IGNORECASE,
    ),
    # "battle my beats vs AI", "pit my tracks against onyx"
    re.compile(
        r"^(?:battle|pit|put)\s+(?:my|these)\s+(?:beats?|tracks?|songs?)"
        r"\s+(?:vs|against|versus)\s+(?P<opponent>.+)",
        re.IGNORECASE,
    ),
    # "user vs ai battle", "user battle"
    re.compile(
        r"^(?:user|human|upload)\s+(?:vs?\s+)?(?:ai\s+)?battle",
        re.IGNORECASE,
    ),
]


def _route_music(text: str) -> RouteResult:
    """Match music generation, DJ mode, and battle commands."""
    clean = text.strip()

    # --- DJ Mode ---
    for pat in _DJ_PATTERNS:
        m = pat.match(clean)
        if m:
            groups = m.groupdict()
            genre = groups.get("genre", "hip-hop") or "hip-hop"
            count = int(groups.get("count", 0) or 0)
            duration_min = int(groups.get("duration", 0) or 0)

            # Calculate tracks from duration (each track ~60s)
            if duration_min > 0 and count == 0:
                count = max(1, duration_min)  # 1 track per minute

            info_parts = [f"genre={genre}"]
            if count:
                info_parts.append(f"tracks={count}")
            if duration_min:
                info_parts.append(f"duration={duration_min}min")

            return RouteResult.hit(
                f"[dj_mode:{','.join(info_parts)}] Starting DJ session.",
                f"DJ Onyx in the building. Let me cook up some {genre}.",
            )

    # --- User-Upload Battle ---
    for pat in _USER_BATTLE_PATTERNS:
        m = pat.match(clean)
        if m:
            groups = m.groupdict()
            opponent = groups.get("opponent", "ai") or "ai"
            # If opponent mentions "ai" or "onyx", it's user_vs_ai
            if any(w in opponent.lower() for w in ("ai", "onyx", "the ai")):
                return RouteResult.hit(
                    f"[beat_battle:mode=user_vs_ai] User vs AI battle requested.",
                    "Upload your beats and I'll pit them against my AI producer.",
                )
            # Otherwise treat as user_vs_user
            return RouteResult.hit(
                f"[beat_battle:mode=user_vs_user] User vs User battle requested.",
                "Upload beats for both sides and I'll judge them.",
            )

    # --- Beat Battle ---
    for pat in _BATTLE_PATTERNS:
        m = pat.match(clean)
        if m:
            groups = m.groupdict()
            opponent = groups.get("opponent", "phantom") or "phantom"

            # Check for history request
            if any(w in clean.lower() for w in ("history", "record", "stats", "score")):
                try:
                    from apps.battle_memory import get_battle_summary
                    summary = get_battle_summary()
                    return RouteResult.hit(
                        f"Battle history: {summary}",
                        f"My battle record: {summary}",
                    )
                except ImportError:
                    return RouteResult.hit(
                        "No battle history module available.",
                        "I don't have battle records loaded right now.",
                    )

            # Check for rivalry context
            rivalry_note = ""
            try:
                from apps.battle_memory import get_rivalry_record, needs_rematch
                record = get_rivalry_record(opponent.lower().replace("dj ", ""))
                if record:
                    rivalry_note = f" Record: {record}."
                if needs_rematch(opponent.lower().replace("dj ", "")):
                    rivalry_note += " This is a rematch!"
            except ImportError:
                pass

            return RouteResult.hit(
                f"[beat_battle:opponent={opponent}] Starting beat battle.{rivalry_note}",
                f"Let's go! Beat battle vs {opponent}.{rivalry_note}",
            )

    # --- Music generation (routed to MusicProducer) ---
    for pat in _MUSIC_PATTERNS:
        m = pat.match(clean)
        if m:
            return RouteResult.hit(
                f"[music_producer:start] {text}",
                "Let me help you make a track.",
            )
    return RouteResult.miss()


# ---------------------------------------------------------------------------
# JustEdit video editing commands
# ---------------------------------------------------------------------------

_JUSTEDIT_PATTERNS = [
    # "open justedit", "launch justedit", "start video editor"
    re.compile(
        r"^(?:open|launch|start)\s+(?:the\s+)?(?:justedit|video\s+editor)",
        re.IGNORECASE,
    ),
    # "edit video", "make a music video", "create a demo video"
    re.compile(
        r"^(?:edit|make|create|build)\s+(?:a\s+|the\s+)?"
        r"(?P<vtype>music\s+video|demo\s+video|highlight\s+reel|video)",
        re.IGNORECASE,
    ),
    # "import recordings into justedit"
    re.compile(
        r"^import\s+(?:my\s+)?recordings?\s+(?:into\s+)?(?:justedit|video\s+editor)",
        re.IGNORECASE,
    ),
]


def _route_justedit(text: str) -> RouteResult:
    """Match JustEdit / video editing commands."""
    clean = text.strip()

    for pat in _JUSTEDIT_PATTERNS:
        m = pat.match(clean)
        if m:
            groups = m.groupdict()
            vtype = groups.get("vtype", "").lower().strip()

            if "music video" in vtype:
                return RouteResult.hit(
                    "[justedit:music_video] Creating a music video project.",
                    "Let me set up a music video project in JustEdit.",
                )
            elif "demo video" in vtype:
                return RouteResult.hit(
                    "[justedit:demo_video] Creating a demo video project.",
                    "Setting up a demo video from your recordings.",
                )
            elif "highlight" in vtype:
                return RouteResult.hit(
                    "[justedit:highlight_reel] Building a highlight reel.",
                    "Let me pull together a highlight reel from your demos.",
                )
            elif "import" in clean.lower():
                return RouteResult.hit(
                    "[justedit:import] Importing recordings into JustEdit.",
                    "Importing your recordings into a JustEdit project.",
                )
            else:
                return RouteResult.hit(
                    "[justedit:open] Opening JustEdit video editor.",
                    "Opening JustEdit. Let's edit some video.",
                )

    return RouteResult.miss()


# ---------------------------------------------------------------------------
# Chain workflow commands
# ---------------------------------------------------------------------------

_CHAIN_PATTERNS = [
    # "full production", "run full production pipeline"
    re.compile(
        r"^(?:run\s+)?(?:the\s+)?full\s+production(?:\s+pipeline)?",
        re.IGNORECASE,
    ),
    # "record and produce", "record, make music, and edit"
    re.compile(
        r"^record\s+(?:and\s+)?(?:produce|make\s+music|edit)",
        re.IGNORECASE,
    ),
    # "beat battle recap", "make a battle recap video"
    re.compile(
        r"^(?:make\s+(?:a\s+)?)?(?:beat\s+)?battle\s+recap(?:\s+video)?",
        re.IGNORECASE,
    ),
    # "make a music video", "music video pipeline" — longer form triggers chain
    re.compile(
        r"^(?:run\s+)?(?:the\s+)?music\s+video\s+pipeline",
        re.IGNORECASE,
    ),
    # "highlight reel", "make a highlight reel", "showreel"
    re.compile(
        r"^(?:make\s+(?:a\s+)?|create\s+(?:a\s+)?|build\s+(?:a\s+)?)?(?:demo\s+)?(?:highlight\s+reel|showreel)",
        re.IGNORECASE,
    ),
    # "3d showcase", "blender showcase video"
    re.compile(
        r"^(?:make\s+(?:a\s+)?|run\s+(?:the\s+)?)?(?:3d|blender)\s+showcase(?:\s+video)?",
        re.IGNORECASE,
    ),
    # "chain workflow [name]", "run workflow [name]"
    re.compile(
        r"^(?:run\s+|chain\s+)?workflow\s+(?P<wf_id>\w+)",
        re.IGNORECASE,
    ),
    # "list workflows", "show chain workflows"
    re.compile(
        r"^(?:list|show)\s+(?:chain\s+)?workflows?",
        re.IGNORECASE,
    ),
]


def _route_chain_workflow(text: str) -> RouteResult:
    """Match chain workflow commands."""
    clean = text.strip()
    low = clean.lower()

    for pat in _CHAIN_PATTERNS:
        m = pat.match(clean)
        if not m:
            continue

        groups = m.groupdict()

        # Explicit workflow ID
        if "wf_id" in groups and groups["wf_id"]:
            wf_id = groups["wf_id"].lower()
            return RouteResult.hit(
                f"[chain:{wf_id}] Running chain workflow.",
                f"Starting the {wf_id.replace('_', ' ')} workflow.",
            )

        # List workflows
        if "list" in low or "show" in low:
            try:
                from core.chain_workflow import list_workflows
                wfs = list_workflows()
                lines = []
                for wf in wfs:
                    steps = " → ".join(wf["step_names"])
                    lines.append(f"  • {wf['id']} — {wf['title']} (~{wf['estimated_minutes']}min)\n    {steps}")
                summary = "\n".join(lines)
                return RouteResult.hit(
                    f"Available chain workflows:\n{summary}",
                    "Here are my chain workflows.",
                )
            except Exception:
                return RouteResult.hit(
                    "Chain workflow module not available.",
                    "Chain workflows aren't loaded yet.",
                )

        # Pattern-matched workflows
        if "full production" in low or "record" in low and "produce" in low:
            return RouteResult.hit(
                "[chain:full_production] Full production pipeline: Record → Music → Edit → Export.",
                "Full production mode. I'll record, generate music, and produce the final video.",
            )
        if "battle" in low and "recap" in low:
            return RouteResult.hit(
                "[chain:beat_battle_recap] Beat battle recap video.",
                "Making a beat battle recap video with round highlights.",
            )
        if "music video" in low and "pipeline" in low:
            return RouteResult.hit(
                "[chain:music_video] Music video pipeline: Song → Visuals → Edit → Export.",
                "Running the full music video pipeline.",
            )
        if "highlight" in low or "showreel" in low:
            return RouteResult.hit(
                "[chain:highlight_reel] Demo highlight reel from existing recordings.",
                "Building a highlight reel from my demo recordings.",
            )
        if "3d" in low or "blender" in low and "showcase" in low:
            return RouteResult.hit(
                "[chain:3d_showcase] 3D showcase: Build → Record → Music → Edit → Export.",
                "3D showcase production starting. Blender build, music, and video.",
            )

    return RouteResult.miss()


# ---------------------------------------------------------------------------
# Microdrama production commands
# ---------------------------------------------------------------------------

_MICRODRAMA_PATTERNS = [
    # "make a microdrama", "produce a microdrama", "create a micro drama"
    re.compile(
        r"^(?:make|create|produce|generate|write|start)\s+(?:a\s+|an\s+)?"
        r"(?:illustrated\s+)?micro[- ]?drama",
        re.IGNORECASE,
    ),
    # "microdrama from secret_billionaire template"
    re.compile(
        r"^micro[- ]?drama\s+(?:from|using|with)\s+(?:the\s+)?(?P<template>\w+)\s*(?:template)?",
        re.IGNORECASE,
    ),
    # "list actors", "show my actors"
    re.compile(
        r"^(?:list|show)\s+(?:my\s+|all\s+)?actors?",
        re.IGNORECASE,
    ),
    # "create actor [name]"
    re.compile(
        r"^(?:create|add|new)\s+(?:an?\s+)?actor\s+(?P<name>.+)",
        re.IGNORECASE,
    ),
    # "list productions", "show microdrama productions"
    re.compile(
        r"^(?:list|show)\s+(?:my\s+|all\s+)?(?:microdrama\s+)?productions?",
        re.IGNORECASE,
    ),
]


def _route_microdrama(text: str) -> RouteResult:
    """Match microdrama production commands."""
    clean = text.strip()
    low = clean.lower()

    for pat in _MICRODRAMA_PATTERNS:
        m = pat.match(clean)
        if not m:
            continue

        groups = m.groupdict()

        # List actors
        if "list" in low and "actor" in low or "show" in low and "actor" in low:
            try:
                from apps.microdrama.actor_registry import ActorRegistry
                registry = ActorRegistry()
                actors = registry.list_actors()
                if not actors:
                    return RouteResult.hit(
                        "No actors registered yet. Create one with: create actor [Name]",
                        "No actors in the registry yet.",
                    )
                lines = []
                for a in actors:
                    styles = ", ".join(v.style for v in a.style_variants) or "no faces"
                    castings = len(a.casting_history)
                    lines.append(f"  - {a.name} ({a.gender}, {a.age_range}) — {styles} — {castings} castings")
                summary = "\n".join(lines)
                return RouteResult.hit(
                    f"Registered actors ({len(actors)}):\n{summary}",
                    f"I have {len(actors)} actors in the registry.",
                )
            except Exception as e:
                return RouteResult.hit(f"Error listing actors: {e}", "Actor registry error.")

        # List productions
        if "production" in low and ("list" in low or "show" in low):
            try:
                from apps.microdrama.producer import MicroDramaProducer
                producer = MicroDramaProducer()
                prods = producer.list_productions()
                if not prods:
                    return RouteResult.hit(
                        "No microdrama productions yet.",
                        "Haven't produced any microdramas yet.",
                    )
                lines = []
                for p in prods:
                    lines.append(f"  - {p['title']} ({p['status']}) — {p['chapters']}ch, {p['images']} imgs")
                return RouteResult.hit(
                    f"Productions ({len(prods)}):\n" + "\n".join(lines),
                    f"I have {len(prods)} microdrama productions.",
                )
            except Exception as e:
                return RouteResult.hit(f"Error: {e}", "Production listing error.")

        # Create actor
        if "name" in groups and groups["name"]:
            actor_name = groups["name"].strip()
            return RouteResult.hit(
                f"[microdrama:create_actor:{actor_name}] Creating new digital actor.",
                f"Creating a new actor profile for '{actor_name}'.",
            )

        # Produce microdrama (with optional template)
        template = groups.get("template", "")
        if template:
            return RouteResult.hit(
                f"[microdrama:produce:{template}] Starting illustrated microdrama production.",
                f"Starting microdrama production with the {template} template.",
            )
        else:
            return RouteResult.hit(
                "[microdrama:produce] Starting illustrated microdrama production.",
                "Starting microdrama production. I'll generate a story and illustrate it.",
            )

    return RouteResult.miss()


# ---------------------------------------------------------------------------
# Hands (autonomous task) commands
# ---------------------------------------------------------------------------

_HANDS_PATTERNS = [
    # "activate hand [name]", "enable [name] hand"
    re.compile(
        r"^(?:activate|enable|start)\s+(?:the\s+)?(?P<hand>\w+)\s+hand",
        re.IGNORECASE,
    ),
    # "activate hand [name]" (reversed order)
    re.compile(
        r"^(?:activate|enable|start)\s+hand\s+(?P<hand>\w+)",
        re.IGNORECASE,
    ),
    # "deactivate hand [name]", "disable [name] hand"
    re.compile(
        r"^(?:deactivate|disable|stop|pause)\s+(?:the\s+)?(?P<hand>\w+)\s+hand",
        re.IGNORECASE,
    ),
    # "run [name] hand now", "run hand [name]"
    re.compile(
        r"^run\s+(?:the\s+)?(?:hand\s+)?(?P<hand>\w+)(?:\s+hand)?(?:\s+now)?",
        re.IGNORECASE,
    ),
    # "hands dashboard", "show hands", "list hands"
    re.compile(
        r"^(?:show|list|view)\s+(?:the\s+)?(?:hands|autonomous\s+tasks)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^hands?\s+(?:dashboard|status|info)",
        re.IGNORECASE,
    ),
    # "system health", "check health"
    re.compile(
        r"^(?:check|show|system)\s+health",
        re.IGNORECASE,
    ),
    # "telemetry stats", "show telemetry"
    re.compile(
        r"^(?:show|check|view)?\s*(?:telemetry|action)\s*(?:stats|summary|report)?",
        re.IGNORECASE,
    ),
]

_KNOWN_HANDS = {"content", "practice", "monitor", "dj", "maintenance"}


def _route_hands(text: str) -> RouteResult:
    """Match Hands, health, and telemetry commands."""
    clean = text.strip()
    low = clean.lower()

    for pat in _HANDS_PATTERNS:
        m = pat.match(clean)
        if not m:
            continue

        groups = m.groupdict()
        hand_id = groups.get("hand", "").lower()

        # System health
        if "health" in low:
            try:
                from core.system_health import health
                summary = health.get_summary(force=True)
                return RouteResult.hit(summary, "Here's the system health report.")
            except Exception:
                return RouteResult.hit(
                    "System health module not available.",
                    "Health module isn't loaded yet.",
                )

        # Telemetry
        if "telemetry" in low or "action" in low and "stats" in low:
            try:
                from core.telemetry import telemetry
                summary = telemetry.get_stats_summary()
                return RouteResult.hit(summary, "Here are the telemetry stats.")
            except Exception:
                return RouteResult.hit(
                    "Telemetry module not available.",
                    "Telemetry isn't loaded yet.",
                )

        # List/dashboard
        if "show" in low or "list" in low or "dashboard" in low or "status" in low:
            try:
                from core.hands.scheduler import HandScheduler
                from core.hands.builtin import create_all_hands
                sched = HandScheduler()
                for h in create_all_hands():
                    sched.register(h)
                summary = sched.dashboard_summary()
                return RouteResult.hit(summary, "Here's the Hands dashboard.")
            except Exception:
                return RouteResult.hit(
                    "Hands system not available.",
                    "Hands aren't loaded yet.",
                )

        # Activate
        if any(w in low for w in ("activate", "enable", "start")) and hand_id:
            if hand_id not in _KNOWN_HANDS:
                return RouteResult.hit(
                    f"Unknown hand '{hand_id}'. Available: {', '.join(sorted(_KNOWN_HANDS))}",
                    f"I don't have a {hand_id} hand.",
                )
            return RouteResult.hit(
                f"[hand:activate:{hand_id}] Activating {hand_id} hand.",
                f"Activating the {hand_id} hand. It'll start working on its schedule.",
            )

        # Deactivate
        if any(w in low for w in ("deactivate", "disable", "stop", "pause")) and hand_id:
            return RouteResult.hit(
                f"[hand:deactivate:{hand_id}] Deactivating {hand_id} hand.",
                f"Deactivating the {hand_id} hand.",
            )

        # Run now
        if "run" in low and hand_id and hand_id in _KNOWN_HANDS:
            return RouteResult.hit(
                f"[hand:run:{hand_id}] Running {hand_id} hand now.",
                f"Running the {hand_id} hand right now.",
            )

    return RouteResult.miss()


# ---------------------------------------------------------------------------
# Face customization commands
# ---------------------------------------------------------------------------

_FACE_THEME_PATTERN = re.compile(
    r"^(?:switch|change|set)\s+(?:my\s+|the\s+|onyx'?s?\s+)?"
    r"(?:face\s+)?(?:theme|color|look)\s+(?:to\s+)?(?P<theme>\w+)$",
    re.IGNORECASE,
)

_FACE_EYE_PATTERN = re.compile(
    r"^(?:switch|change|set)\s+(?:my\s+|the\s+|onyx'?s?\s+)?"
    r"(?:eye|eyes)\s+(?:style\s+)?(?:to\s+)?(?P<style>\w+)$",
    re.IGNORECASE,
)

_FACE_LIST_PATTERN = re.compile(
    r"^(?:list|show|what)\s+(?:are\s+)?(?:the\s+)?(?:available\s+)?"
    r"(?:face\s+)?(?:themes?|colors?|looks?|eye\s+styles?|faces?)$",
    re.IGNORECASE,
)

# Valid theme and style keys (from face_spec.json)
_VALID_THEMES = {
    "cyan", "emerald", "violet", "amber", "rose",
    "crimson", "sunset", "ice", "pink",
}
_VALID_EYE_STYLES = {"default", "round", "angular", "narrow", "wide"}
_VALID_FACE_SHAPES = {"default", "rounded", "angular", "slim"}


def _route_face_customization(text: str) -> RouteResult:
    """Match face theme/style switching commands."""
    clean = text.strip()

    # List available options
    m = _FACE_LIST_PATTERN.match(clean)
    if m:
        themes = ", ".join(sorted(_VALID_THEMES))
        eyes = ", ".join(sorted(_VALID_EYE_STYLES))
        return RouteResult.hit(
            f"Available themes: {themes}\nEye styles: {eyes}",
            f"Available themes are: {themes}. Eye styles are: {eyes}.",
        )

    # Theme switch
    m = _FACE_THEME_PATTERN.match(clean)
    if m:
        theme = m.group("theme").lower()
        if theme not in _VALID_THEMES:
            return RouteResult.hit(
                f"Unknown theme '{theme}'. Available: {', '.join(sorted(_VALID_THEMES))}",
                f"I don't have a {theme} theme.",
            )
        try:
            from face.settings import load_settings, save_settings
            s = load_settings()
            s["face_theme"] = theme
            save_settings(s)
        except Exception:
            pass
        return RouteResult.hit(
            f"[face:theme:{theme}] Switched face theme to {theme}.",
            f"Switched to {theme} theme.",
        )

    # Eye style switch
    m = _FACE_EYE_PATTERN.match(clean)
    if m:
        style = m.group("style").lower()
        if style not in _VALID_EYE_STYLES:
            return RouteResult.hit(
                f"Unknown eye style '{style}'. Available: {', '.join(sorted(_VALID_EYE_STYLES))}",
                f"I don't have a {style} eye style.",
            )
        try:
            from face.settings import load_settings, save_settings
            s = load_settings()
            s["eye_style"] = style
            save_settings(s)
        except Exception:
            pass
        return RouteResult.hit(
            f"[face:eye_style:{style}] Switched eye style to {style}.",
            f"Switched to {style} eyes.",
        )

    return RouteResult.miss()


# ---------------------------------------------------------------------------
# Voice-Controlled Blender commands
# ---------------------------------------------------------------------------

_VOICE_BLENDER_PATTERNS = [
    re.compile(r"^open\s+blender\b", re.IGNORECASE),
    re.compile(r"^launch\s+blender\b", re.IGNORECASE),
    re.compile(r"^start\s+blender\b", re.IGNORECASE),
    re.compile(r"^blender\s+voice\s+(?:mode|control|session)\b", re.IGNORECASE),
]


def _route_voice_blender(text: str) -> RouteResult:
    """Match voice-controlled Blender session commands."""
    clean = text.strip()
    
    for pat in _VOICE_BLENDER_PATTERNS:
        if pat.match(clean):
            return RouteResult.hit(
                "[blender:voice] Starting voice-controlled Blender session.",
                "Opening Blender. What are we working on today?",
            )
    
    return RouteResult.miss()


# ---------------------------------------------------------------------------
# Home Builder Bot commands
# ---------------------------------------------------------------------------

_HOMEBUILDER_PATTERNS = [
    re.compile(
        r"^(?:design|build|create|make)\s+(?:a\s+|an\s+|me\s+a\s+)?"
        r"(?P<room>kitchen|bathroom|master\s*bath|bedroom|closet|walk[- ]?in\s*closet|"
        r"laundry|laundry\s*room|living\s*room|room)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:home\s*builder|hb5?)\s+(?:preset\s+)?(?P<preset>\w+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:design|build|create)\s+(?:a\s+|an\s+)?(?:interior|home|house|room|space)\b",
        re.IGNORECASE,
    ),
]

_PRESET_MAP = {
    "kitchen": "kitchen",
    "bathroom": "bathroom",
    "bath": "bathroom",
    "masterbath": "master_bath",
    "master bath": "master_bath",
    "bedroom": "bedroom",
    "closet": "walk_in_closet",
    "walk-in closet": "walk_in_closet",
    "walkin closet": "walk_in_closet",
    "laundry": "laundry",
    "laundry room": "laundry",
    "living room": "living_room",
    "livingroom": "living_room",
}


def _route_homebuilder(text: str) -> RouteResult:
    """Match Home Builder 5 interior design commands."""
    clean = text.strip()
    low = clean.lower()

    # Check for explicit homebuilder prefix
    for pat in _HOMEBUILDER_PATTERNS:
        m = pat.match(clean)
        if not m:
            continue

        groups = m.groupdict()

        # Direct room type match
        room = groups.get("room", "").lower().strip()
        if room:
            preset = _PRESET_MAP.get(room)
            if preset:
                return RouteResult.hit(
                    f"[homebuilder:preset:{preset}] Designing {room} with Home Builder 5.",
                    f"Starting Home Builder. Designing a {room}.",
                )
            return RouteResult.hit(
                f"[homebuilder:custom:{clean}] Custom interior design with Home Builder 5.",
                f"Starting Home Builder for a custom room design.",
            )

        # Explicit preset
        preset = groups.get("preset", "").lower().strip()
        if preset in _PRESET_MAP:
            return RouteResult.hit(
                f"[homebuilder:preset:{_PRESET_MAP[preset]}] Designing {preset} with Home Builder 5.",
                f"Starting Home Builder. Designing a {preset}.",
            )

        # Generic interior design request
        return RouteResult.hit(
            f"[homebuilder:custom:{clean}] Custom interior design with Home Builder 5.",
            f"Starting Home Builder for interior design.",
        )

    return RouteResult.miss()


# ---------------------------------------------------------------------------
# Unity commands
# ---------------------------------------------------------------------------

_UNITY_PATTERNS = [
    re.compile(r"(?:open|launch|start)\s+unity", re.I),
    re.compile(r"(?:create|new|make)\s+(?:a\s+)?unity\s+(?:project|scene|game)", re.I),
    re.compile(r"unity\s+(?:build|spawn|create|generate|setup|add|make|import)", re.I),
    re.compile(r"(?:build|create|make)\s+(?:a\s+)?(?:game|unity\s+scene|unity\s+project)", re.I),
    re.compile(r"(?:spawn|place|add)\s+(?:a\s+)?(?:cube|sphere|cylinder|capsule|plane|quad)\s+(?:in\s+)?unity", re.I),
    re.compile(r"(?:generate|write|create)\s+(?:a\s+)?(?:c#|csharp|unity)\s+script", re.I),
    re.compile(r"unity\s+(?:play|stop|pause|undo|redo|screenshot|save)", re.I),
    re.compile(r"(?:setup|apply)\s+(?:a\s+)?(?:forest|desert|snow|night|sunset)\s+(?:environment|scene)", re.I),
]


def _route_unity(text: str) -> RouteResult:
    """Match Unity Engine commands."""
    clean = text.strip()
    low = clean.lower()

    for pat in _UNITY_PATTERNS:
        if pat.match(clean):
            return RouteResult.hit(
                f"[unity:{clean}] Unity Engine command.",
                f"Routing to Unity Engine toolkit.",
            )

    # Keyword fallback for explicit "in unity" suffix
    if low.endswith("in unity") or low.startswith("unity "):
        return RouteResult.hit(
            f"[unity:{clean}] Unity Engine command.",
            f"Routing to Unity Engine toolkit.",
        )

    return RouteResult.miss()


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

# Ordered list of routers — first match wins
_ROUTERS = [
    ("system", _route_system),
    ("face", _route_face_customization),
    ("tool_launch", _route_tool_launch),
    ("remember", _route_remember),
    ("voice_blender", _route_voice_blender),
    ("homebuilder", _route_homebuilder),
    ("unity", _route_unity),
    ("blender_build", _route_blender_build),
    ("camera", _route_camera),
    ("music", _route_music),
    ("justedit", _route_justedit),
    ("chain", _route_chain_workflow),
    ("microdrama", _route_microdrama),
    ("hands", _route_hands),
]


def route_command(text: str) -> RouteResult:
    """Attempt to fast-path a user command.

    Returns a RouteResult. If .handled is True, the command was dispatched
    and the caller should NOT send it to the orchestrator.
    """
    if not text or not text.strip():
        return RouteResult.miss()

    clean = text.strip()

    # Skip routing for very short inputs (likely conversational)
    if len(clean) < 3:
        return RouteResult.miss()

    # Skip routing for questions (usually conversational)
    if clean.endswith("?") and not any(
        clean.lower().startswith(q)
        for q in ("what's on my screen", "what do you see", "what do you remember")
    ):
        return RouteResult.miss()

    for router_name, router_fn in _ROUTERS:
        result = router_fn(clean)
        if result.handled:
            _log.info("[router] %s matched: %r → %s", router_name,
                      clean[:50], result.response[:60])
            return result

    return RouteResult.miss()


def get_router_info() -> str:
    """Return a summary of fast-path commands for debugging/help."""
    return (
        "Fast-path commands (no LLM needed):\n"
        "  • open/launch [tool] — launch internal tools\n"
        "  • build/create [thing] — start Blender generative build\n"
        "  • show me/zoom/pan/orbit — viewport camera control\n"
        "  • take a screenshot — capture screen\n"
        "  • what's on my screen — describe screen\n"
        "  • remember [fact] — save to memory\n"
        "  • work mode / chat mode — switch modes\n"
        "  • switch theme to [name] — change face color theme\n"
        "  • switch eyes to [style] — change eye style\n"
        "  • list themes — show available face themes\n"
        "  Music Producer (conversational track creation):\n"
        "  • make me a song / beat / track — start music session\n"
        "  • make [genre] music/track — generate with genre\n"
        "  • generate a 4-min jazz instrumental — detailed request\n"
        "  • (after generating) play / score / cover / repaint / add layer / stems\n"
        "  DJ Mode:\n"
        "  • do a [N] minute dj set — DJ mode with N tracks\n"
        "  • make me 5 trap beats — DJ mode (specific count + genre)\n"
        "  • dj set in jazz — DJ session in a genre\n"
        "  • start battle vs Phantom — beat battle\n"
        "  • rematch — rematch last opponent\n"
        "  • battle history — show win/loss records\n"
        "  • open justedit — launch the video editor\n"
        "  • make a music video — create music video project\n"
        "  • make a demo video — assemble demo from recordings\n"
        "  • import recordings into justedit — import screen recordings\n"
        "  Chain Workflows (multi-step pipelines):\n"
        "  • full production — record → music → edit → export\n"
        "  • battle recap — beat battle recap video\n"
        "  • music video pipeline — song → visuals → edit\n"
        "  • highlight reel / showreel — compile demo recordings\n"
        "  • 3d showcase — Blender build → music → edit\n"
        "  • list workflows — show all chain workflows\n"
        "  • run workflow [name] — run a specific workflow\n"
        "  Hands (autonomous agents):\n"
        "  • show hands — dashboard of all autonomous Hands\n"
        "  • activate [name] hand — enable a scheduled Hand\n"
        "  • deactivate [name] hand — disable a Hand\n"
        "  • run [name] hand now — execute immediately\n"
        "  • check health — system health report\n"
        "  • telemetry stats — action analytics\n"
        "  Voice Blender (conversational 3D modeling):\n"
        "  • open blender — start voice-controlled session\n"
        "  • create a [object] — build 3D object with auto-grouping\n"
        "  • delete this [object] — context-aware group deletion\n"
        "  • done — save and close session\n"
        "  Home Builder (interior design with HB5):\n"
        "  • design a kitchen — build room from preset\n"
        "  • build a bathroom — build room from preset\n"
        "  • design a bedroom / closet / laundry — other presets\n"
        "  • homebuilder <preset> — explicit preset name\n"
        "  Microdrama Production:\n"
        "  • make a microdrama — produce illustrated story\n"
        "  • microdrama from [template] — use specific template\n"
        "  • list actors — show digital actor registry\n"
        "  • create actor [Name] — create new digital actor\n"
        "  • list productions — show past microdrama runs\n"
    )
