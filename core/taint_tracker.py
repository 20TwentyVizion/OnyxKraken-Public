"""Secret Taint Tracker — detects leaked secrets in LLM I/O and logs.

Maintains a set of known secret patterns (env vars, API keys, tokens)
and scans text for their presence. When a secret is found in an
unexpected context (e.g. an LLM response, an audit log entry, or a
generated script), it is flagged and an audit event is emitted.

Usage:
    from core.taint_tracker import taint_check, register_secret

    # Register secrets from environment
    register_secret("NETLIFY_AUTH_TOKEN", os.environ.get("NETLIFY_AUTH_TOKEN", ""))

    # Check text for leaked secrets
    leaks = taint_check(llm_response_text, context="llm.response")
    if leaks:
        print(f"LEAKED: {leaks}")
"""

import logging
import os
import re
import threading
from typing import Optional

_log = logging.getLogger("core.taint_tracker")

_lock = threading.Lock()

# Registry: {label: secret_value}
_secrets: dict[str, str] = {}

# Generic patterns that look like API keys / tokens (high-entropy strings)
_GENERIC_PATTERNS = [
    # AWS-style keys
    re.compile(r"AKIA[0-9A-Z]{16}"),
    # GitHub tokens
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"),
    # Generic long hex/base64 tokens (32+ chars, with optional separator chunks)
    re.compile(r"(?:sk|pk|token|key|secret|password|auth)[_\-]?(?:live|test|prod)?[_\-]?[A-Za-z0-9]{20,}",
               re.IGNORECASE),
    # Bearer tokens in headers
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    # .env style KEY=VALUE where value looks secret
    re.compile(r"(?:API_KEY|SECRET|TOKEN|PASSWORD|AUTH)\s*=\s*\S{8,}", re.IGNORECASE),
]

# Env var names to auto-register on init
_AUTO_REGISTER_VARS = [
    "NETLIFY_AUTH_TOKEN",
    "GUMROAD_LICENSE_KEY",
    "DISCORD_BOT_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "HUGGINGFACE_TOKEN",
    "ELEVENLABS_API_KEY",
    "GITHUB_TOKEN",
]


def _auto_register():
    """Auto-register secrets from known environment variables."""
    for var in _AUTO_REGISTER_VARS:
        val = os.environ.get(var, "")
        if val and len(val) >= 8:
            register_secret(var, val)


def register_secret(label: str, value: str):
    """Register a secret value to track.

    Args:
        label: Human-readable name (e.g. "NETLIFY_AUTH_TOKEN").
        value: The actual secret value. Must be >= 8 chars to avoid false positives.
    """
    if not value or len(value) < 8:
        return
    with _lock:
        _secrets[label] = value
    _log.debug("Registered taint for: %s (%d chars)", label, len(value))


def unregister_secret(label: str):
    """Remove a secret from tracking."""
    with _lock:
        _secrets.pop(label, None)


def taint_check(text: str, context: str = "unknown") -> list[dict]:
    """Scan text for leaked secrets.

    Args:
        text: The text to scan (LLM response, log entry, script, etc.).
        context: Where the text came from (e.g. "llm.response", "audit_log",
                 "generated_script").

    Returns:
        List of leak dicts: [{"label": str, "type": "exact"|"pattern",
                              "context": str, "snippet": str}]
        Empty list = clean.
    """
    if not text:
        return []

    leaks: list[dict] = []

    # 1. Check registered secrets (exact substring match)
    with _lock:
        secrets_snapshot = dict(_secrets)

    for label, value in secrets_snapshot.items():
        if value in text:
            # Find approximate position for snippet
            idx = text.index(value)
            snippet_start = max(0, idx - 20)
            snippet_end = min(len(text), idx + len(value) + 20)
            snippet = text[snippet_start:snippet_end]
            # Redact the actual secret in the snippet
            snippet = snippet.replace(value, f"[{label}:REDACTED]")

            leaks.append({
                "label": label,
                "type": "exact",
                "context": context,
                "snippet": snippet,
            })

    # 2. Check generic secret patterns
    for pattern in _GENERIC_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            # Skip if it's a known registered secret (already caught above)
            is_known = any(match in v or v in match for v in secrets_snapshot.values())
            if is_known:
                continue
            leaks.append({
                "label": f"pattern:{pattern.pattern[:30]}",
                "type": "pattern",
                "context": context,
                "snippet": match[:40] + ("..." if len(match) > 40 else ""),
            })

    # 3. Audit log the leaks
    if leaks:
        _log.warning("Secret taint detected in %s: %d leak(s)", context, len(leaks))
        try:
            from core.audit_log import audit
            audit(
                "security.secret_taint_detected",
                context=context,
                leak_count=len(leaks),
                labels=[l["label"] for l in leaks],
            )
        except ImportError:
            pass

    return leaks


def redact(text: str) -> str:
    """Return a copy of text with all known secrets replaced by [REDACTED].

    Useful for sanitizing text before logging or displaying.
    """
    if not text:
        return text

    with _lock:
        secrets_snapshot = dict(_secrets)

    result = text
    for label, value in secrets_snapshot.items():
        if value in result:
            result = result.replace(value, f"[{label}:REDACTED]")

    return result


# Auto-register on import
_auto_register()
