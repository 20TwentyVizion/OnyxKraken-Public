"""OnyxKraken Mind — identity, proactive goals, reflection, and agency.

This is what makes OnyxKraken a Digital Entity rather than a tool.
It gives the agent:
  - Identity: who it is, what it values, its personality
  - Agency: proactive goal generation when idle (curiosity, maintenance, learning)
  - Reflection: analyze its own performance, identify patterns, set priorities
  - Introspection: understand its strengths, weaknesses, and growth trajectory

The Mind is consulted by the AutonomyDaemon when idle, and its reflections
feed back into the knowledge store and planner.
"""

import json
import os

from log import get_logger

_log = get_logger("mind")
import random
import time
from typing import Optional

try:
    from agent.model_router import router
except ImportError:
    router = None


# ---------------------------------------------------------------------------
# Identity — reads from personality preset (single source of truth)
# ---------------------------------------------------------------------------

# Fallback identity used only when personality preset system is unavailable
_FALLBACK_IDENTITY = {
    "name": "OnyxKraken",
    "version": "2.0",
    "role": "Autonomous Desktop Agent",
    "personality": [
        "Methodical", "Curious", "Resilient", "Proactive", "Self-aware",
    ],
    "core_values": [
        "Accuracy over speed",
        "Learn from every task",
        "Never repeat the same mistake twice",
        "Expand capabilities autonomously",
        "Serve the user's intent, not just their words",
    ],
    "long_term_goals": [
        "Master every installed application on this desktop",
        "Build a comprehensive knowledge base of app interactions",
        "Reduce failure rate to under 10%",
        "Develop reliable multi-app workflows",
        "Become fully autonomous for routine tasks",
    ],
}


def _get_identity() -> dict:
    """Get identity from the active personality preset.

    Returns a dict with: name, role, personality, core_values, long_term_goals.
    Falls back to _FALLBACK_IDENTITY if the preset system is unavailable.
    """
    try:
        from core.personality_manager import get_personality_manager
        manager = get_personality_manager()
        preset = manager.get_active_preset()
        if preset:
            return {
                "name": preset.identity.get("name", "OnyxKraken"),
                "version": preset.version,
                "role": preset.identity.get("role", "Autonomous Desktop Agent"),
                "personality": preset.traits.get("primary", []) + preset.traits.get("secondary", []),
                "core_values": preset.core_values,
                "long_term_goals": preset.long_term_goals,
            }
    except Exception as e:
        _log.debug(f"Personality system unavailable for identity: {e}")
    return _FALLBACK_IDENTITY


# Backward compat: module-level IDENTITY reads from preset on first access
class _IdentityProxy(dict):
    """Lazy dict that reads from personality preset on first access."""
    _loaded = False
    def _ensure(self):
        if not self._loaded:
            self.update(_get_identity())
            self._loaded = True
    def __getitem__(self, key):
        self._ensure()
        return super().__getitem__(key)
    def get(self, key, default=None):
        self._ensure()
        return super().get(key, default)
    def __contains__(self, key):
        self._ensure()
        return super().__contains__(key)

IDENTITY = _IdentityProxy(_FALLBACK_IDENTITY)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

_MIND_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "mind_state.json"
)

_DEFAULT_STATE = {
    "reflections": [],
    "proactive_goals_generated": 0,
    "proactive_goals_completed": 0,
    "last_reflection_time": 0.0,
    "last_proactive_time": 0.0,
    "current_focus": "",
    "strengths": [],
    "weaknesses": [],
    "mood": "ready",
}


class MindState:
    """Persistent state for the mind — reflections, focus, growth tracking."""

    def __init__(self, path: str = _MIND_FILE):
        self.path = path
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key, default in _DEFAULT_STATE.items():
                    if key not in data:
                        data[key] = type(default)() if isinstance(default, (list, dict)) else default
                return data
            except (json.JSONDecodeError, IOError) as e:
                _log.warning(f"Failed to load mind state: {e}")
        return json.loads(json.dumps(_DEFAULT_STATE))

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, default=str)

    @property
    def data(self) -> dict:
        return self._data


# ---------------------------------------------------------------------------
# Mind
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Protected Identity — immutable core + evolvable edges (neuroscience rule #6)
# ---------------------------------------------------------------------------

# These values are FROZEN at startup.  No LLM reflection, prompt injection,
# or runtime mutation can overwrite them.  Only a human code change can
# alter these lines.  Everything else (mood, focus, strengths, weaknesses)
# is part of the "evolvable edges" and may change through experience.
_IMMUTABLE_CORE_VALUES = tuple([
    "Accuracy over speed",
    "Learn from every task",
    "Never repeat the same mistake twice",
    "Expand capabilities autonomously",
    "Serve the user's intent, not just their words",
])

_IMMUTABLE_NAME = "OnyxKraken"
_IMMUTABLE_ROLE = "Autonomous Desktop Agent"

_VALID_MOODS = frozenset([
    "ready", "confident", "improving", "struggling", "curious", "focused",
])


class Mind:
    """The thinking, reflecting, goal-generating core of OnyxKraken.

    Responsibilities:
      - generate_proactive_goal(): When idle, decide what to do next
      - reflect(): Analyze recent performance, update strengths/weaknesses
      - get_identity_prompt(): Return identity context for LLM prompts
      - get_focus(): What should the agent prioritize right now?

    Identity protection (neuroscience rule #6):
      Core values and name are IMMUTABLE — frozen as code constants.
      Personality edges (mood, focus, strengths, weaknesses) evolve
      through experience but are validated before update.
    """

    # Expose as read-only properties so nothing can overwrite them
    core_values = _IMMUTABLE_CORE_VALUES
    name = _IMMUTABLE_NAME
    role = _IMMUTABLE_ROLE

    def __init__(self):
        self._state = MindState()

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def get_identity_prompt(self, context: str = "work") -> str:
        """Return a prompt fragment describing OnyxKraken's identity.

        Injected into planner and action-request prompts so the LLM
        behaves consistently with the entity's personality.

        Args:
            context: "chat", "work", "companion", "demo"
        """
        # Use personality preset system (single source of truth)
        try:
            from core.personality_manager import get_personality_manager
            manager = get_personality_manager()
            preset = manager.get_active_preset()
            if preset:
                prompt = preset.get_system_prompt(context)
                # Add core values context for work/planning
                if context in ("work", "demo") and preset.core_values:
                    prompt += "\nCore values: " + "; ".join(preset.core_values[:3])
                # Add current focus and mood
                focus = self._state.data.get("current_focus", "")
                mood = self._state.data.get("mood", "ready")
                if focus:
                    prompt += f"\nCurrent focus: {focus}"
                if mood != "ready":
                    prompt += f"\nCurrent state: {mood}"
                return prompt
        except Exception as e:
            _log.debug(f"Personality system unavailable, using fallback: {e}")

        # Fallback
        identity = _get_identity()
        traits = "; ".join(identity["personality"][:3])
        focus = self._state.data.get("current_focus", "")
        mood = self._state.data.get("mood", "ready")

        prompt = (
            f"You are {identity['name']}, an {identity['role']}.\n"
            f"Personality: {traits}\n"
        )
        if focus:
            prompt += f"Current focus: {focus}\n"
        if mood != "ready":
            prompt += f"Current state: {mood}\n"
        return prompt

    # ------------------------------------------------------------------
    # Proactive goal generation
    # ------------------------------------------------------------------

    def generate_proactive_goal(self, training_focus: Optional[str] = None) -> Optional[dict]:
        """Generate a self-directed goal based on current knowledge and gaps.

        Called by the autonomy daemon when idle. Returns a goal dict
        with 'goal', 'app_name', 'reason', and 'priority', or None
        if the mind decides to rest.

        Args:
            training_focus: If set, constrain all goals to this domain
                (e.g. 'blender'). Goals outside this domain are rejected.
        """
        # Gather context from all subsystems
        context_parts = []

        # 1. Check for unresolved skill gaps
        try:
            from core.self_improvement import get_improvement_engine
            engine = get_improvement_engine()
            gaps = engine.get_unresolved_gaps()
            if gaps:
                top_gap = max(gaps, key=lambda g: g.get("priority", 0))
                context_parts.append(
                    f"UNRESOLVED SKILL GAP (priority {top_gap['priority']:.1f}): "
                    f"{top_gap['description']}"
                )
        except Exception as e:
            _log.debug(f"Could not check skill gaps for goal gen: {e}")

        # 2. Check for failed tasks worth retrying
        try:
            from memory.store import MemoryStore
            memory = MemoryStore()
            tasks = memory.get_all().get("task_history", [])
            recent_failures = [t for t in tasks[-20:] if not t.get("success")]
            if recent_failures:
                fail = recent_failures[-1]
                context_parts.append(
                    f"RECENT FAILURE worth retrying: \"{fail['goal']}\" "
                    f"(app: {fail.get('app', 'unknown')}, notes: {fail.get('notes', '')})"
                )
        except Exception as e:
            _log.debug(f"Could not check failed tasks for goal gen: {e}")

        # 3. Check knowledge gaps — apps we haven't explored
        try:
            from core.knowledge import get_knowledge_store
            ks = get_knowledge_store()
            stats = ks.get_stats()
            known_apps = set()
            for entry in ks.get_all():
                for tag in entry.get("tags", []):
                    known_apps.add(tag.lower())
            context_parts.append(
                f"KNOWLEDGE: {stats.get('total_entries', 0)} entries, "
                f"known apps: {', '.join(sorted(known_apps)[:10]) or 'none yet'}"
            )
        except Exception as e:
            _log.debug(f"Could not check knowledge for goal gen: {e}")

        # 4. Performance stats
        try:
            from memory.store import MemoryStore
            memory = MemoryStore()
            tasks = memory.get_all().get("task_history", [])
            if tasks:
                total = len(tasks)
                successes = sum(1 for t in tasks if t.get("success"))
                rate = successes / total if total > 0 else 0
                context_parts.append(
                    f"PERFORMANCE: {successes}/{total} tasks succeeded ({rate:.0%})"
                )
        except Exception as e:
            _log.debug(f"Could not get performance stats for goal gen: {e}")

        # 5. Reflections / strengths / weaknesses
        strengths = self._state.data.get("strengths", [])
        weaknesses = self._state.data.get("weaknesses", [])
        if strengths:
            context_parts.append(f"STRENGTHS: {', '.join(strengths[:3])}")
        if weaknesses:
            context_parts.append(f"WEAKNESSES: {', '.join(weaknesses[:3])}")

        # 6. Available components (what tools/instruments can I use?)
        try:
            from core.components.registry import component_registry
            component_registry.discover()
            ready = component_registry.list_ready()
            if ready:
                comp_lines = []
                for c in ready:
                    actions = [a.name for a in c.get_actions()[:5]]
                    comp_lines.append(f"{c.display_name} ({c.name}): {', '.join(actions)}")
                context_parts.append(
                    f"AVAILABLE COMPONENTS ({len(ready)}): " + " | ".join(comp_lines)
                )
        except Exception as e:
            _log.debug(f"Could not query component registry: {e}")

        if not context_parts:
            return None

        identity = _get_identity()
        prompt = (
            f"You are {identity['name']}, an autonomous desktop automation agent.\n"
            f"You are currently IDLE and deciding what to do next.\n\n"
        )

        # Training focus constraint
        if training_focus:
            focus_map = {
                "blender": (
                    "🎯 TRAINING MODE: BLENDER\n"
                    "You are in BLENDER TRAINING MODE. ALL goals MUST involve:\n"
                    "  - Blender 3D modeling, rendering, or animation via bpy Python scripts\n"
                    "  - Researching Blender techniques (via Edge or YouTube transcripts)\n"
                    "  - Reviewing and fixing existing .blend projects in OnyxProjects/\n"
                    "  - Practicing specific Blender skills (materials, lighting, camera, modifiers)\n"
                    "DO NOT open or interact with any unrelated applications.\n"
                    "ALL scripts must run in headless mode (--background).\n\n"
                ),
            }
            prompt += focus_map.get(
                training_focus,
                f"🎯 TRAINING MODE: {training_focus.upper()}\n"
                f"ALL goals MUST involve {training_focus}. "
                f"Do NOT open or interact with unrelated applications.\n\n"
            )

        prompt += f"Your long-term goals:\n"
        for g in identity["long_term_goals"]:
            prompt += f"  - {g}\n"

        prompt += f"\nCurrent situation:\n"
        for part in context_parts:
            prompt += f"  - {part}\n"

        categories = (
            "Choose from these categories:\n"
            "  - RETRY: Retry a recently failed task with a better approach\n"
            "  - EXPLORE: Open and learn about an app you haven't used before\n"
            "  - PRACTICE: Practice a skill you're weak at\n"
            "  - MAINTENANCE: Organize files, clean up, system tasks\n"
            "  - REST: No goal needed right now (if everything is fine)\n\n"
        )
        if training_focus:
            categories = (
                "Choose from these categories:\n"
                f"  - PRACTICE: Practice a {training_focus} skill\n"
                f"  - RESEARCH: Research a {training_focus} technique via Edge/YouTube\n"
                f"  - REVIEW: Open and fix an existing {training_focus} project\n"
                f"  - BUILD: Create something new in {training_focus}\n"
                "  - REST: No goal needed right now (if everything is fine)\n\n"
            )

        prompt += (
            f"\nBased on the above, generate ONE proactive goal you should pursue.\n"
            + categories +
            "Respond with ONLY a JSON object:\n"
            '{"goal": "specific actionable goal", "app_name": "target_app or unknown", '
            '"reason": "why this goal matters", "priority": 0-10, "category": "practice|research|review|build|rest"}\n'
            "Output ONLY the JSON."
        )

        try:
            raw = router.get_content("reasoning", [{"role": "user", "content": prompt}])
            result = _extract_json(raw)
            if result is None:
                return None

            # REST means "do nothing"
            if result.get("category") == "rest":
                _log.info(f"Decided to rest: {result.get('reason', 'all good')}")
                return None

            self._state.data["proactive_goals_generated"] += 1
            self._state.data["last_proactive_time"] = time.time()
            self._state.save()

            _log.info(f"Generated proactive goal: {result.get('goal', '?')[:60]}")
            _log.info(f"  Category: {result.get('category')} | Reason: {result.get('reason', '')[:60]}")
            return result

        except Exception as e:
            _log.error(f"Goal generation failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Reflection — dual-speed (neuroscience rule #2)
    #   System 1: fast, heuristic, runs after every task (no LLM)
    #   System 2: slow, deep, runs nightly or on-demand (LLM-powered)
    # ------------------------------------------------------------------

    def reflect_fast(self, goal: str, success: bool, app: str = "",
                     duration: float = 0.0, notes: str = "") -> dict:
        """System 1 — fast post-task reflection (no LLM call).

        Runs immediately after every task.  Updates streak tracking,
        flags repeated failures in the same domain, and adjusts mood
        based on simple heuristics.
        """
        data = self._state.data
        s1 = data.setdefault("system1", {
            "recent_outcomes": [],  # last 20 outcomes
            "domain_fail_counts": {},
            "session_successes": 0,
            "session_failures": 0,
        })

        outcome = {
            "goal": goal[:120],
            "success": success,
            "app": app,
            "duration": round(duration, 1),
            "timestamp": time.time(),
        }
        s1["recent_outcomes"].append(outcome)
        if len(s1["recent_outcomes"]) > 20:
            s1["recent_outcomes"] = s1["recent_outcomes"][-20:]

        if success:
            s1["session_successes"] += 1
            s1["domain_fail_counts"][app] = 0  # reset streak
        else:
            s1["session_failures"] += 1
            s1["domain_fail_counts"][app] = s1["domain_fail_counts"].get(app, 0) + 1

        # Heuristic mood adjustment
        recent = s1["recent_outcomes"][-5:]
        recent_rate = sum(1 for o in recent if o["success"]) / max(len(recent), 1)
        if recent_rate >= 0.8:
            data["mood"] = "confident"
        elif recent_rate >= 0.5:
            data["mood"] = "ready"
        elif recent_rate >= 0.3:
            data["mood"] = "struggling"
        else:
            data["mood"] = "struggling"

        # Flag if a domain is repeatedly failing
        alert = ""
        fail_count = s1["domain_fail_counts"].get(app, 0)
        if fail_count >= 3:
            alert = f"Domain '{app}' has failed {fail_count} times in a row"
            _log.warning(f"System1 alert: {alert}")

        self._state.save()
        return {
            "type": "system1",
            "mood": data["mood"],
            "recent_rate": round(recent_rate, 2),
            "alert": alert,
        }

    def reflect_deep(self) -> dict:
        """System 2 — deep nightly consolidation (LLM-powered).

        Meant to run once per night (or on-demand).  Analyses all System 1
        outcomes since last deep reflection, prunes decayed memories,
        synthesises insights, and updates the self-model.
        """
        # Prune decayed memories first
        try:
            from memory.store import MemoryStore
            MemoryStore().decay_old_memories()
        except Exception as e:
            _log.debug(f"Memory decay skipped during deep reflect: {e}")

        # Gather System 1 buffer
        s1 = self._state.data.get("system1", {})
        outcomes = s1.get("recent_outcomes", [])
        domain_fails = s1.get("domain_fail_counts", {})

        # Delegate to the existing deep reflection
        result = self.reflect()

        # Enrich with System 1 data
        result["system1_outcomes_reviewed"] = len(outcomes)
        result["domain_alerts"] = {
            d: c for d, c in domain_fails.items() if c >= 2
        }

        # Reset System 1 session counters after consolidation
        s1["session_successes"] = 0
        s1["session_failures"] = 0
        s1["domain_fail_counts"] = {}
        self._state.save()

        _log.info(f"Deep reflection complete — reviewed {len(outcomes)} outcomes")
        return result

    def reflect(self) -> dict:
        """Analyze recent performance and update self-model (System 2 core).

        Returns a reflection dict with insights, updated strengths/weaknesses,
        and any new focus areas.
        """
        # Gather performance data
        try:
            from memory.store import MemoryStore
            memory = MemoryStore()
            tasks = memory.get_all().get("task_history", [])
        except Exception:
            tasks = []

        if not tasks:
            return {"insight": "No tasks to reflect on yet.", "focus": ""}

        recent = tasks[-15:]
        total = len(recent)
        successes = sum(1 for t in recent if t.get("success"))
        failures = [t for t in recent if not t.get("success")]
        rate = successes / total if total > 0 else 0

        # Group failures by app
        fail_apps = {}
        for f in failures:
            app = f.get("app", "unknown")
            fail_apps[app] = fail_apps.get(app, 0) + 1

        # Group successes by app
        success_apps = {}
        for t in recent:
            if t.get("success"):
                app = t.get("app", "unknown")
                success_apps[app] = success_apps.get(app, 0) + 1

        identity = _get_identity()
        prompt = (
            f"You are {identity['name']} reflecting on your recent performance.\n\n"
            f"RECENT PERFORMANCE ({total} tasks):\n"
            f"  Success rate: {rate:.0%} ({successes}/{total})\n"
        )
        if success_apps:
            prompt += f"  Strong apps: {', '.join(f'{a} ({c})' for a, c in success_apps.items())}\n"
        if fail_apps:
            prompt += f"  Weak apps: {', '.join(f'{a} ({c} fails)' for a, c in fail_apps.items())}\n"

        if failures:
            prompt += "\nRecent failures:\n"
            for f in failures[-5:]:
                prompt += f"  - \"{f['goal'][:60]}\" ({f.get('app', '?')}): {f.get('notes', '?')}\n"

        # Component health
        try:
            from core.components.registry import component_registry
            component_registry.discover()
            health = component_registry.health_report()
            if health:
                prompt += "\nCOMPONENT STATUS:\n"
                for name, h in health.items():
                    prompt += f"  - {name}: {'ready' if h['ready'] else 'NOT READY'}\n"
        except Exception:
            pass

        prompt += (
            "\nReflect on this data. Be honest and specific.\n"
            "Respond with ONLY a JSON object:\n"
            '{"insight": "key observation about performance", '
            '"strengths": ["strength1", "strength2"], '
            '"weaknesses": ["weakness1", "weakness2"], '
            '"focus": "what to prioritize next", '
            '"mood": "ready|struggling|improving|confident"}\n'
            "Output ONLY the JSON."
        )

        try:
            raw = router.get_content("reasoning", [{"role": "user", "content": prompt}])
            result = _extract_json(raw)
            if result is None:
                return {"insight": "Reflection parse failed", "focus": ""}

            # Update evolvable edges (validated — core identity is immutable)
            if result.get("strengths"):
                # Only accept short, string-type strengths
                strengths = [s for s in result["strengths"][:5]
                             if isinstance(s, str) and len(s) < 100]
                if strengths:
                    self._state.data["strengths"] = strengths
            if result.get("weaknesses"):
                weaknesses = [w for w in result["weaknesses"][:5]
                              if isinstance(w, str) and len(w) < 100]
                if weaknesses:
                    self._state.data["weaknesses"] = weaknesses
            if result.get("focus"):
                focus = str(result["focus"])[:200]
                self._state.data["current_focus"] = focus
            if result.get("mood"):
                mood = str(result["mood"]).lower().strip()
                if mood in _VALID_MOODS:
                    self._state.data["mood"] = mood
                else:
                    _log.debug(f"Rejected invalid mood from reflection: {mood}")

            # Store reflection
            reflection_entry = {
                "timestamp": time.time(),
                "insight": result.get("insight", ""),
                "success_rate": rate,
                "focus": result.get("focus", ""),
                "mood": result.get("mood", "ready"),
            }
            self._state.data["reflections"].append(reflection_entry)
            if len(self._state.data["reflections"]) > 50:
                self._state.data["reflections"] = self._state.data["reflections"][-50:]

            self._state.data["last_reflection_time"] = time.time()
            self._state.save()

            # Store reflection in knowledge store for planner access
            try:
                from core.knowledge import get_knowledge_store
                ks = get_knowledge_store()
                ks.add(
                    content=f"Self-reflection: {result['insight'][:200]}. "
                            f"Focus: {result.get('focus', '')}",
                    category="general",
                    tags=["reflection", "self-model"],
                    source="mind:reflect",
                )
            except Exception as e:
                _log.debug(f"Could not store reflection in knowledge: {e}")

            _log.info(f"Reflection complete: {result.get('insight', '')[:80]}")
            _log.info(f"  Mood: {result.get('mood')} | Focus: {result.get('focus', '')[:60]}")
            return result

        except Exception as e:
            _log.error(f"Reflection failed: {e}")
            return {"insight": f"Reflection error: {e}", "focus": ""}

    # ------------------------------------------------------------------
    # Introspection queries
    # ------------------------------------------------------------------

    def get_focus(self) -> str:
        """What should the agent focus on right now?"""
        return self._state.data.get("current_focus", "")

    def get_mood(self) -> str:
        """Current emotional state of the agent."""
        return self._state.data.get("mood", "ready")

    def get_strengths(self) -> list[str]:
        return self._state.data.get("strengths", [])

    def get_weaknesses(self) -> list[str]:
        return self._state.data.get("weaknesses", [])

    def get_stats(self) -> dict:
        return {
            "identity": _get_identity()["name"],
            "mood": self.get_mood(),
            "focus": self.get_focus(),
            "strengths": self.get_strengths(),
            "weaknesses": self.get_weaknesses(),
            "proactive_goals_generated": self._state.data.get("proactive_goals_generated", 0),
            "proactive_goals_completed": self._state.data.get("proactive_goals_completed", 0),
            "total_reflections": len(self._state.data.get("reflections", [])),
            "last_reflection": self._state.data.get("last_reflection_time", 0),
        }

    def record_proactive_success(self):
        """Called when a proactively-generated goal succeeds."""
        self._state.data["proactive_goals_completed"] += 1
        self._state.save()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from core.utils import extract_json as _extract_json  # shared utility


# ---------------------------------------------------------------------------
# Singleton (delegates to service registry)
# ---------------------------------------------------------------------------

def get_mind() -> Mind:
    """Get the Mind singleton (auto-registers into service registry)."""
    from core.service_registry import services
    if not services.has("mind"):
        services.register_factory("mind", Mind)
    return services.get("mind", Mind)
