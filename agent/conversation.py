"""Conversation Manager — multi-turn context tracking for OnyxKraken.

Handles:
  - Follow-up resolution: "now save that" → understands "that" = last result
  - Goal refinement: "do it again but ask about Python" → modifies previous goal
  - Status queries: "what did you do?" → summarizes last task
  - Context injection: passes conversation history to the planner/action model
"""

import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional

_log = logging.getLogger("agent.conversation")


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""
    user_input: str
    resolved_goal: str  # the actual goal passed to the orchestrator
    app_name: str
    result_summary: str = ""
    success: bool = False


@dataclass
class ConversationState:
    """Tracks multi-turn conversation context."""
    turns: list[ConversationTurn] = field(default_factory=list)

    @property
    def last_turn(self) -> Optional[ConversationTurn]:
        return self.turns[-1] if self.turns else None

    @property
    def last_goal(self) -> str:
        return self.last_turn.resolved_goal if self.last_turn else ""

    @property
    def last_app(self) -> str:
        return self.last_turn.app_name if self.last_turn else "unknown"

    @property
    def last_result(self) -> str:
        return self.last_turn.result_summary if self.last_turn else ""

    def summary(self, max_turns: int = 5) -> str:
        """Build a conversation summary for context injection."""
        if not self.turns:
            return ""
        recent = self.turns[-max_turns:]
        lines = []
        for i, turn in enumerate(recent, 1):
            status = "✓" if turn.success else "✗"
            lines.append(f"  {i}. [{status}] \"{turn.user_input}\" → {turn.resolved_goal}")
            if turn.result_summary:
                lines.append(f"     Result: {turn.result_summary[:100]}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

class Intent(StrEnum):
    NEW_GOAL = "new_goal"           # Fresh task, no relation to previous
    FOLLOW_UP = "follow_up"         # Refers to previous result ("save that", "read it again")
    REFINEMENT = "refinement"       # Modifies previous goal ("do it again but...")
    STATUS_QUERY = "status_query"   # Asks about what happened ("what did you do?")
    CONVERSATION = "conversation"   # Casual chat, greeting, or question — no desktop action


# Phrases that are clearly conversational / not a desktop task
_GREETING_PHRASES = (
    "hello", "hi", "hey", "howdy", "greetings", "good morning",
    "good afternoon", "good evening", "good night", "yo", "sup",
    "what's up", "whats up", "how are you", "how's it going",
    "how you doing", "how do you do", "nice to meet you",
)

_IDENTITY_PHRASES = (
    "what's your name", "whats your name", "who are you",
    "what are you", "what can you do", "tell me about yourself",
    "introduce yourself", "what do you do",
)

_CHAT_PHRASES = (
    "tell me a joke", "tell me something", "say something",
    "how do you feel", "are you alive", "do you have feelings",
    "what do you think", "i'm bored", "im bored", "thank you",
    "thanks", "good job", "well done", "nice work", "i love you",
    "you're awesome", "you're cool", "bye", "goodbye", "see you",
    "good bye", "talk to me", "chat with me", "let's talk",
    "lets talk", "can we talk", "just chatting",
)

# Verbs that signal a desktop-automation task
_TASK_VERBS = (
    "open", "close", "create", "make", "build", "write", "read",
    "run", "execute", "launch", "start", "stop", "install",
    "download", "upload", "save", "delete", "remove", "find",
    "search", "navigate", "go to", "click", "type", "press",
    "scroll", "drag", "drop", "copy", "paste", "cut", "move",
    "rename", "edit", "update", "fix", "debug", "test", "deploy",
    "send", "email", "browse", "render", "compile", "generate",
    "calculate", "convert", "extract", "import", "export",
    "automate", "schedule", "monitor", "screenshot", "record",
)


# ---------------------------------------------------------------------------
# Work mode trigger detection
# ---------------------------------------------------------------------------

WORK_TRIGGER_PHRASES = (
    "onyx command:",
    "onyx command",
    "onyx,",
    "switch to work mode",
    "work mode:",
    "work mode",
    "hey onyx, can you",
    "hey onyx can you",
    "hey onyx, please",
    "hey onyx please",
)

# Phrases that explicitly return to companion mode
COMPANION_TRIGGER_PHRASES = (
    "switch to chat",
    "companion mode",
    "chat mode",
    "never mind",
    "nevermind",
    "cancel that",
)


def detect_work_trigger(text: str) -> tuple[bool, str]:
    """Check if text contains a work mode trigger phrase.

    Returns (is_work_trigger, cleaned_goal).
    If a trigger is found, the prefix is stripped and the remaining text is the goal.
    """
    lower = text.lower().strip()

    for phrase in WORK_TRIGGER_PHRASES:
        if lower.startswith(phrase):
            remainder = text[len(phrase):].strip().lstrip(":").strip()
            if remainder:
                return True, remainder
            # Trigger phrase alone with no goal (e.g., "work mode") — signal mode switch
            return True, ""

    return False, text


def detect_companion_trigger(text: str) -> bool:
    """Check if text contains a companion mode trigger phrase."""
    lower = text.lower().strip()
    return any(lower.startswith(p) or lower == p for p in COMPANION_TRIGGER_PHRASES)


def _is_conversational(inp: str) -> bool:
    """Return True if the input is casual chat, not a desktop task."""
    # Exact or near-exact greeting
    if inp.rstrip("!?. ") in _GREETING_PHRASES:
        return True
    # Starts with a greeting phrase
    if any(inp.startswith(g) for g in _GREETING_PHRASES):
        # But not "hey open notepad"
        if not any(v in inp for v in _TASK_VERBS):
            return True
    # Identity / meta questions
    if any(p in inp for p in _IDENTITY_PHRASES):
        return True
    # Chat phrases
    if any(p in inp for p in _CHAT_PHRASES):
        if not any(v in inp for v in _TASK_VERBS):
            return True
    # Short input (≤6 words) with no task verbs is likely conversational
    words = inp.split()
    if len(words) <= 6 and not any(v in inp for v in _TASK_VERBS):
        # But not if it looks like an app name or file path
        if not any(c in inp for c in ("/", "\\", ".", ":")):
            return True
    return False


def classify_intent_scored(user_input: str, state: ConversationState) -> tuple[str, float]:
    """Classify user input with a confidence score (0.0–1.0).

    Returns (intent, confidence). Low confidence (<0.5) indicates the
    classifier is uncertain and the caller should consider asking for
    clarification before acting.
    """
    inp = user_input.lower().strip()
    words = inp.split()
    word_count = len(words)

    # --- High-confidence matches (explicit phrases) ---

    # Status queries
    status_phrases = (
        "what did you do", "what happened", "status", "what's going on",
        "show me what you did", "recap", "summary",
    )
    if state.turns and any(phrase in inp for phrase in status_phrases):
        return Intent.STATUS_QUERY, 0.95

    # Refinement
    refinement_phrases = (
        "do it again", "same thing but", "try again", "retry",
        "again but", "same but", "redo",
    )
    if state.turns and any(phrase in inp for phrase in refinement_phrases):
        return Intent.REFINEMENT, 0.90

    # Follow-up with action verbs
    followup_markers = (
        "that", "this", "it", "the response", "the result", "the answer",
        "what it said", "the output",
    )
    if state.turns and word_count <= 20 and any(m in inp for m in followup_markers):
        action_verbs = ("save", "copy", "paste", "send", "email", "write", "put", "move")
        if any(verb in inp for verb in action_verbs):
            return Intent.FOLLOW_UP, 0.85

    # --- Conversational checks ---
    if _is_conversational(inp):
        # Exact greeting → very high confidence
        if inp.rstrip("!?. ") in _GREETING_PHRASES:
            return Intent.CONVERSATION, 0.95
        # Identity / chat phrases → high confidence
        if any(p in inp for p in _IDENTITY_PHRASES) or any(p in inp for p in _CHAT_PHRASES):
            return Intent.CONVERSATION, 0.90
        # Short + no task verbs → moderate confidence (could be ambiguous)
        if word_count <= 6 and not any(v in inp for v in _TASK_VERBS):
            return Intent.CONVERSATION, 0.65

    # --- Task detection ---
    task_verb_count = sum(1 for v in _TASK_VERBS if v in inp)

    # Strong task signal: multiple task verbs or explicit app names
    if task_verb_count >= 2:
        return Intent.NEW_GOAL, 0.90
    if task_verb_count == 1 and word_count >= 3:
        return Intent.NEW_GOAL, 0.80
    if task_verb_count == 1 and word_count < 3:
        # "open" alone, "save" alone — probably a task but short
        return Intent.NEW_GOAL, 0.65

    # Check for question / reflective language — likely conversational
    is_question = inp.endswith("?")
    personal_pronouns = ("i ", "i'm ", "im ", "my ", "me ", "we ", "you ")
    has_personal = any(inp.startswith(p) or f" {p}" in inp for p in personal_pronouns)
    reflective_phrases = (
        "how does it", "how do you", "what do you think", "what's it like",
        "whats it like", "how does that", "do you feel", "do you know",
        "just wanted", "just checking", "i was wondering", "curious about",
        "tell me about", "what's your", "whats your", "have you", "did you",
        "can you tell", "do you remember", "what's it", "how's it",
    )
    has_reflective = any(p in inp for p in reflective_phrases)

    # Ambiguous zone: no strong signals either way
    if word_count <= 4:
        # Very short, no clear signal → low confidence conversation
        return Intent.CONVERSATION, 0.40

    # Longer conversational text: questions, personal, reflective → chat
    if is_question and has_personal:
        return Intent.CONVERSATION, 0.75
    if has_reflective:
        return Intent.CONVERSATION, 0.70
    if is_question:
        return Intent.CONVERSATION, 0.60

    # Longer text with no task verbs and no clear goal structure → conversation
    return Intent.CONVERSATION, 0.45


# Confidence threshold for auto-proceeding vs asking for clarification
CONFIDENCE_THRESHOLD = 0.55


def classify_intent(user_input: str, state: ConversationState) -> str:
    """Classify user input (backward-compatible wrapper).

    Returns just the intent string. For confidence-aware routing, use
    classify_intent_scored() instead.
    """
    intent, _ = classify_intent_scored(user_input, state)
    return intent


# ---------------------------------------------------------------------------
# Goal resolution
# ---------------------------------------------------------------------------

def resolve_goal(user_input: str, intent: str, state: ConversationState) -> tuple[str, str]:
    """Resolve the user's input into an actionable goal and app name.

    Returns (resolved_goal, app_name).
    """
    if intent in (Intent.STATUS_QUERY, Intent.CONVERSATION):
        # Not a real goal — handled separately
        return "", ""

    if intent == Intent.NEW_GOAL:
        return user_input, "unknown"

    if intent == Intent.FOLLOW_UP:
        # Expand pronouns with context from the last turn
        last = state.last_turn
        if last:
            context = last.result_summary or last.resolved_goal
            resolved = f"{user_input} (context: the previous task was \"{last.resolved_goal}\""
            if last.result_summary:
                resolved += f", result: {last.result_summary[:200]}"
            resolved += ")"
            return resolved, last.app_name
        return user_input, "unknown"

    if intent == Intent.REFINEMENT:
        last = state.last_turn
        if last:
            resolved = f"{last.resolved_goal} — modified: {user_input}"
            return resolved, last.app_name
        return user_input, "unknown"

    return user_input, "unknown"


def format_status_response(state: ConversationState) -> str:
    """Generate a human-readable status summary."""
    if not state.turns:
        return "I haven't done anything yet this session."

    last = state.last_turn
    lines = [f"Last task: \"{last.resolved_goal}\""]
    if last.success:
        lines.append(f"Status: Completed successfully")
    else:
        lines.append(f"Status: Did not fully complete")
    if last.result_summary:
        lines.append(f"Result: {last.result_summary[:300]}")

    if len(state.turns) > 1:
        lines.append(f"\nFull conversation ({len(state.turns)} turns):")
        lines.append(state.summary())

    return "\n".join(lines)
