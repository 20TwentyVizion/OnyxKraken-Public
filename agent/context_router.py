"""Context Router — prevents context drift during long multi-step tasks.

Inspired by the PreToolUse hook pattern (01d research): after N actions in a step,
the orchestrator's LLM starts forgetting app-specific rules, past failures, and
goal context. This module scans recent history + action results for keywords,
matches against a route table, and injects relevant context into the next
observation — keeping the LLM on track without bloating the base prompt.

Integration: called between _build_observation() and _request_action() in the
orchestrator's interact loop.

Budget: max ~500 tokens injected per action. Debounce prevents redundant injections.
"""

import logging
import time
from typing import Optional

_log = logging.getLogger("agent.context_router")


# ---------------------------------------------------------------------------
# Static route table — keyword patterns → context snippets
# Each route: {"keywords": [...], "context": "...", "category": "..."}
# A route matches if >= match_threshold keywords appear in the scan text.
# ---------------------------------------------------------------------------

_ROUTES = [
    # --- App-specific: Blender ---
    {
        "keywords": ["blender", "viewport", "3d", "shift+a", "f3"],
        "match_threshold": 2,
        "category": "blender",
        "context": (
            "BLENDER RULES: Shortcuts are viewport-context-sensitive — mouse must be "
            "over 3D viewport. Use F3 (operator search) + type name to add objects. "
            "pyautogui.hotkey() fails in Blender — use win.type_keys() for combos. "
            "After Escape (splash dismiss), default cube is pre-selected — do NOT "
            "click before X (delete). Click viewport center BEFORE F3/Shift+A."
        ),
    },
    {
        "keywords": ["blender", "render", "f12", "cycles", "eevee"],
        "match_threshold": 2,
        "category": "blender_render",
        "context": (
            "BLENDER RENDER: F12 starts render. Cycles is slow but high quality. "
            "EEVEE is fast for previews. Render output goes to scene.render.filepath. "
            "For background renders, use --background --python script.py."
        ),
    },
    # --- App-specific: Notepad ---
    {
        "keywords": ["notepad", "type", "text", "save", "file"],
        "match_threshold": 2,
        "category": "notepad",
        "context": (
            "NOTEPAD RULES: After typing text, do NOT save or close unless the step "
            "explicitly asks for it. Ctrl+S saves. Type action works directly. "
            "Verify typed text appears in the accessibility tree after typing."
        ),
    },
    # --- App-specific: Chrome ---
    {
        "keywords": ["chrome", "browser", "navigate", "url", "address"],
        "match_threshold": 2,
        "category": "chrome",
        "context": (
            "CHROME RULES: Click address bar (or Ctrl+L) before typing URLs. "
            "Press Enter after typing URL to navigate. Wait for page load before "
            "interacting with page elements. Use accessibility tree to find elements."
        ),
    },
    # --- App-specific: Chat apps (Grok, etc.) ---
    {
        "keywords": ["grok", "chatgpt", "claude", "chat", "response", "wait"],
        "match_threshold": 2,
        "category": "chat_app",
        "context": (
            "CHAT APP RULES: After sending a message, WAIT for the response to finish "
            "generating. Look for the response in the accessibility tree. The chat_wait "
            "step type handles this automatically — do not try to manually poll."
        ),
    },
    # --- Common failure patterns ---
    {
        "keywords": ["not found", "element", "target", "missing", "cannot find"],
        "match_threshold": 2,
        "category": "element_not_found",
        "context": (
            "ELEMENT NOT FOUND: If a target element can't be found by name, try: "
            "(1) use fallback_coords from the screenshot, (2) use a different "
            "target_type (e.g., 'name' vs 'control_type'), (3) check if the window "
            "needs to be focused first, (4) check if a menu or dialog needs to be "
            "opened first."
        ),
    },
    {
        "keywords": ["blocked", "safety", "rejected", "not allowed"],
        "match_threshold": 2,
        "category": "safety_blocked",
        "context": (
            "SAFETY BLOCK: The action was blocked by safety rules. Do NOT retry the "
            "same action. Choose a completely different approach. Check if there's a "
            "safer way to achieve the same result (e.g., using a menu instead of a "
            "keyboard shortcut, or using a different target)."
        ),
    },
    {
        "keywords": ["focus", "window", "active", "foreground", "minimize"],
        "match_threshold": 2,
        "category": "window_focus",
        "context": (
            "WINDOW FOCUS: If the target window isn't in focus, click on it first or "
            "use the launch action. Check the 'Visible Windows' list to confirm the "
            "window exists. Some actions fail silently if the wrong window is active."
        ),
    },
    # --- Task type context ---
    {
        "keywords": ["file", "write", "create", "path", "desktop", "directory"],
        "match_threshold": 3,
        "category": "file_ops",
        "context": (
            "FILE OPERATIONS: Use the write_file action for creating files. "
            "Desktop path is ~/Desktop. Always use forward slashes or raw strings "
            "for paths. Verify file creation with read_file action if needed."
        ),
    },
    {
        "keywords": ["command", "terminal", "powershell", "cmd", "run"],
        "match_threshold": 2,
        "category": "terminal",
        "context": (
            "TERMINAL: Use run_command action for shell commands. Commands run in "
            "PowerShell by default. Output is captured and returned. Timeout default "
            "is 30 seconds. Do NOT run destructive commands (rm, del, format)."
        ),
    },
    # --- Step completion ---
    {
        "keywords": ["done", "complete", "finished", "already", "accomplished"],
        "match_threshold": 2,
        "category": "step_done",
        "context": (
            "STEP COMPLETION: If the current step appears to be already done based on "
            "the screenshot and accessibility tree, output a 'done' action IMMEDIATELY. "
            "Do NOT perform additional actions like saving or closing unless explicitly "
            "asked in the step description."
        ),
    },
]

# ---------------------------------------------------------------------------
# Context Router class
# ---------------------------------------------------------------------------

# How many actions into a step before context injection activates
_ACTIVATION_THRESHOLD = 3

# Max characters of injected context (~500 tokens ≈ ~2000 chars)
_MAX_INJECT_CHARS = 2000

# Minimum actions between re-injecting the same route category
_DEBOUNCE_ACTIONS = 4


class ContextRouter:
    """Scans recent agent history for keyword signals and injects relevant context."""

    def __init__(self):
        self._action_count = 0
        self._last_injected: dict[str, int] = {}  # category → action_count when last injected
        self._knowledge_cache: list[dict] = []
        self._knowledge_cache_time = 0.0

    def reset(self):
        """Reset state for a new step."""
        self._action_count = 0
        self._last_injected.clear()

    def tick(self):
        """Called after each action to advance the counter."""
        self._action_count += 1

    def get_context_injection(
        self,
        history: list[dict],
        current_step: str,
        app_name: str = "",
        last_result: str = "",
    ) -> Optional[str]:
        """Scan recent history and return context to inject, or None.

        Args:
            history: Recent action history entries.
            current_step: The current step description.
            app_name: Current app name (for filtering).
            last_result: The result of the last executed action.

        Returns:
            Context string to append to observation, or None if no injection needed.
        """
        # Don't activate until we're deep enough into the step
        if self._action_count < _ACTIVATION_THRESHOLD:
            return None

        # Build scan text from recent history + step + last result
        scan_parts = [current_step.lower()]
        if last_result:
            scan_parts.append(last_result.lower()[:500])
        if app_name:
            scan_parts.append(app_name.lower())

        # Include last 3 history entries
        for entry in history[-3:]:
            content = entry.get("content", "")
            if isinstance(content, str):
                scan_parts.append(content.lower()[:300])

        scan_text = " ".join(scan_parts)

        # Match routes
        matched = []
        total_chars = 0

        for route in _ROUTES:
            category = route["category"]

            # Debounce: skip if recently injected
            last_inject = self._last_injected.get(category, -_DEBOUNCE_ACTIONS)
            if self._action_count - last_inject < _DEBOUNCE_ACTIONS:
                continue

            # Count keyword matches
            threshold = route.get("match_threshold", 2)
            hits = sum(1 for kw in route["keywords"] if kw in scan_text)
            if hits >= threshold:
                ctx = route["context"]
                if total_chars + len(ctx) <= _MAX_INJECT_CHARS:
                    matched.append((category, ctx))
                    total_chars += len(ctx)

        # Also pull from knowledge store (dynamic routes)
        if total_chars < _MAX_INJECT_CHARS:
            knowledge_ctx = self._get_knowledge_context(scan_text, app_name)
            if knowledge_ctx and total_chars + len(knowledge_ctx) <= _MAX_INJECT_CHARS:
                matched.append(("knowledge", knowledge_ctx))
                total_chars += len(knowledge_ctx)

        if not matched:
            return None

        # Record injection
        for category, _ in matched:
            self._last_injected[category] = self._action_count

        # Format injection block
        injections = "\n".join(ctx for _, ctx in matched)
        block = (
            f"\n## Context Injection (auto-retrieved, action #{self._action_count})\n"
            f"{injections}"
        )

        _log.debug(
            f"Injecting context at action #{self._action_count}: "
            f"{[cat for cat, _ in matched]}"
        )
        return block

    def _get_knowledge_context(self, scan_text: str, app_name: str) -> Optional[str]:
        """Pull relevant knowledge from the knowledge store."""
        # Cache knowledge for 30s to avoid repeated disk reads
        now = time.time()
        if now - self._knowledge_cache_time > 30.0:
            try:
                from core.knowledge import get_knowledge_store
                ks = get_knowledge_store()
                self._knowledge_cache = ks.get_all()
                self._knowledge_cache_time = now
            except Exception:
                self._knowledge_cache = []

        if not self._knowledge_cache:
            return None

        # Simple keyword match against knowledge entries
        scan_words = set(scan_text.split())
        scored = []
        for entry in self._knowledge_cache:
            content = entry.get("content", "")
            content_words = set(content.lower().split())
            overlap = len(scan_words & content_words)
            # Boost entries tagged with current app
            if app_name and app_name.lower() in [t.lower() for t in entry.get("tags", [])]:
                overlap += 3
            if overlap >= 3:
                scored.append((overlap, content))

        if not scored:
            return None

        scored.sort(key=lambda x: x[0], reverse=True)
        # Take top 2 knowledge entries
        top = scored[:2]
        snippets = [f"• {content[:200]}" for _, content in top]
        return "LEARNED KNOWLEDGE:\n" + "\n".join(snippets)


# Singleton
_router: Optional[ContextRouter] = None


def get_context_router() -> ContextRouter:
    global _router
    if _router is None:
        _router = ContextRouter()
    return _router
