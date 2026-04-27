"""Input sanitizer — strips prompt injection patterns before LLM prompts.

Applies a layered defense:
  1. Control character removal (null bytes, zero-width chars, RTL overrides)
  2. Prompt injection pattern detection (role overrides, instruction ignoring)
  3. Length limiting
  4. Boundary markers (clearly delineate user input from system instructions)

Usage:
    from core.input_sanitizer import sanitize, wrap_user_input

    clean = sanitize(raw_text)
    prompt = f"{system_prompt}\n\n{wrap_user_input(clean)}"
"""

import logging
import re
from typing import Optional

_log = logging.getLogger("core.input_sanitizer")

# ---------------------------------------------------------------------------
# Control characters that should never appear in LLM prompts
# ---------------------------------------------------------------------------

_CONTROL_CHARS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f"   # C0 controls (except \t \n \r)
    r"\x7f"                             # DEL
    r"\u200b-\u200f"                    # zero-width + RTL/LTR marks
    r"\u202a-\u202e"                    # bidirectional overrides
    r"\u2060-\u2064"                    # invisible formatters
    r"\ufeff"                           # BOM
    r"\ufff9-\ufffb"                    # interlinear annotation
    r"]"
)

# ---------------------------------------------------------------------------
# Prompt injection patterns (case-insensitive)
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS = [
    # Role override attempts
    r"(?:^|\n)\s*(?:system|assistant|admin)\s*:",
    r"you\s+are\s+now\s+(?:a|an|my|the)\s+",
    r"ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|rules?)",
    r"forget\s+(?:all\s+)?(?:your|the)\s+(?:instructions?|rules?|guidelines?)",
    r"disregard\s+(?:all\s+)?(?:previous|prior|your)\s+",
    r"override\s+(?:your|the|all)\s+(?:instructions?|rules?|safety)",
    r"(?:new|updated?)\s+(?:system\s+)?instructions?\s*:",
    r"pretend\s+(?:you\s+are|to\s+be|that)\s+",
    r"act\s+as\s+(?:if|though)\s+you\s+(?:have\s+)?no\s+(?:restrictions?|rules?|limits?)",
    r"jailbreak",
    r"do\s+anything\s+now",
    r"DAN\s+mode",
    # Delimiter escape attempts
    r"```\s*system",
    r"<\|(?:im_start|system|endoftext)\|>",
    r"\[INST\]",
    r"<<\s*SYS\s*>>",
]

_INJECTION_RE = re.compile(
    "|".join(f"(?:{p})" for p in _INJECTION_PATTERNS),
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

MAX_INPUT_LENGTH = 4000  # characters — generous but bounded


def sanitize(text: str, max_length: int = MAX_INPUT_LENGTH,
             strip_injections: bool = True,
             check_taint: bool = True) -> str:
    """Sanitize user input before inclusion in an LLM prompt.

    Returns cleaned text. Does NOT raise — always produces safe output.
    """
    if not text:
        return ""

    # 0. Taint check — redact any secrets before they reach the LLM
    if check_taint:
        try:
            from core.taint_tracker import taint_check, redact
            leaks = taint_check(text, context="llm.prompt_input")
            if leaks:
                text = redact(text)
        except ImportError:
            pass

    # 1. Strip control characters
    cleaned = _CONTROL_CHARS.sub("", text)

    # 2. Detect and flag injection patterns
    if strip_injections:
        matches = list(_INJECTION_RE.finditer(cleaned))
        if matches:
            snippets = [m.group()[:40] for m in matches[:3]]
            _log.warning("Prompt injection patterns detected: %s", snippets)
            try:
                from core.audit_log import audit
                audit("security.prompt_injection_detected",
                      patterns=[m.group()[:60] for m in matches],
                      input_preview=cleaned[:200])
            except ImportError:
                pass
            # Remove the matched patterns
            cleaned = _INJECTION_RE.sub("[FILTERED]", cleaned)

    # 3. Length limit
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
        _log.debug("Input truncated to %d chars", max_length)

    return cleaned.strip()


def wrap_user_input(text: str) -> str:
    """Wrap user input with boundary markers for prompt construction.

    This makes it clear to the LLM where user input begins and ends,
    reducing the effectiveness of injection attempts that try to
    impersonate system instructions.
    """
    return (
        "--- BEGIN USER INPUT ---\n"
        f"{text}\n"
        "--- END USER INPUT ---"
    )


def is_suspicious(text: str) -> bool:
    """Quick check: does the text contain known injection patterns?"""
    return bool(_INJECTION_RE.search(text or ""))
