"""Structured Audit Log — JSON Lines event logger for OnyxKraken.

Every significant agent action is recorded as a single JSON line:
  - User commands submitted
  - LLM prompts and responses
  - Desktop actions proposed, allowed, blocked, or executed
  - IPC scripts sent to Blender/UE (with ScriptGuard verdicts)
  - Safety decisions (allow/block/default-deny)
  - Errors and recovery attempts

Hash-chain integrity:
  Each entry includes ``prev_hash`` (SHA-256 of the previous entry) and
  ``entry_hash`` (SHA-256 of the current entry including prev_hash).
  If any log line is edited, inserted, or deleted, the chain breaks.
  Call ``verify_chain()`` to validate an entire audit log file.

Log file: data/audit/audit.jsonl (rotated daily)

Usage:
    from core.audit_log import audit, verify_chain

    audit("action.executed", app="blender", action="click", target="File",
          result="success")
    audit("script.blocked", reason="os.system() call", script_hash="abc123")

    # Verify integrity
    ok, errors = verify_chain("data/audit/audit_2026-03-02.jsonl")
"""

import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_log = logging.getLogger("core.audit_log")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent
_AUDIT_DIR = _PROJECT_ROOT / "data" / "audit"
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file before rotation
_MAX_CONTENT_LEN = 2000  # truncate long script/prompt content in logs

# ---------------------------------------------------------------------------
# Thread-safe writer
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_current_file: Optional[Any] = None
_current_path: Optional[str] = None
_session_id: Optional[str] = None
_prev_hash: str = "0" * 64  # genesis hash for the chain


def _get_session_id() -> str:
    """Lazy-init a session ID (timestamp-based)."""
    global _session_id
    if _session_id is None:
        _session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return _session_id


def _get_log_path() -> Path:
    """Get the current audit log file path (daily rotation)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _AUDIT_DIR / f"audit_{today}.jsonl"


def _ensure_file():
    """Open or rotate the audit log file."""
    global _current_file, _current_path

    target = _get_log_path()
    target_str = str(target)

    # Rotate if day changed or file too large
    if _current_file is not None:
        if _current_path != target_str:
            _current_file.close()
            _current_file = None
        elif os.path.exists(target_str) and os.path.getsize(target_str) > _MAX_FILE_SIZE:
            _current_file.close()
            # Rename with sequence number
            seq = 1
            while os.path.exists(target_str.replace(".jsonl", f".{seq}.jsonl")):
                seq += 1
            os.rename(target_str, target_str.replace(".jsonl", f".{seq}.jsonl"))
            _current_file = None

    if _current_file is None:
        os.makedirs(_AUDIT_DIR, exist_ok=True)
        _current_file = open(target, "a", encoding="utf-8")
        _current_path = target_str

    return _current_file


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def audit(event: str, **kwargs):
    """Log a structured audit event.

    Args:
        event: Dot-separated event type, e.g.:
            - "goal.submitted"
            - "action.proposed"
            - "action.executed"
            - "action.blocked"
            - "action.confirmed"
            - "action.rejected"
            - "safety.check"
            - "safety.default_deny"
            - "script.validated"
            - "script.blocked"
            - "ipc.command_sent"
            - "ipc.signature_created"
            - "llm.prompt"
            - "llm.response"
            - "error"
            - "session.start"
            - "session.end"
        **kwargs: Additional fields to include in the log entry.
            Large content fields (script, prompt, response) are auto-truncated.
    """
    global _prev_hash

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session": _get_session_id(),
        "event": event,
    }

    # Truncate large content fields
    for key in ("script", "prompt", "response", "content", "code"):
        if key in kwargs and isinstance(kwargs[key], str):
            val = kwargs[key]
            if len(val) > _MAX_CONTENT_LEN:
                kwargs[key] = val[:_MAX_CONTENT_LEN] + f"... ({len(val)} chars total)"
            # Add a hash for full-content reference
            kwargs[f"{key}_sha256"] = hashlib.sha256(val.encode("utf-8")).hexdigest()[:16]

    entry.update(kwargs)

    try:
        with _lock:
            # Hash-chain: link this entry to the previous one
            entry["prev_hash"] = _prev_hash
            # Compute entry_hash over deterministic JSON (without entry_hash itself)
            canonical = json.dumps(entry, ensure_ascii=False, default=str, sort_keys=True)
            entry_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            entry["entry_hash"] = entry_hash
            _prev_hash = entry_hash

            line = json.dumps(entry, ensure_ascii=False, default=str, sort_keys=True)
            f = _ensure_file()
            f.write(line + "\n")
            f.flush()
    except Exception as e:
        _log.debug("Audit log write failed: %s", e)


def audit_action(app: str, action: dict, safety_result: str,
                 executed: bool = False, result: str = ""):
    """Convenience: log a desktop automation action."""
    audit(
        "action.executed" if executed else "action.proposed",
        app=app,
        action_type=action.get("action", ""),
        target=action.get("target", ""),
        thought=action.get("thought", ""),
        safety=safety_result,
        executed=executed,
        result=result,
    )


def audit_script(script: str, mode: str, safe: bool,
                 violations: list[str] = None, executed: bool = False):
    """Convenience: log a script validation + execution event."""
    audit(
        "script.validated" if safe else "script.blocked",
        mode=mode,
        safe=safe,
        violations=violations or [],
        executed=executed,
        script=script,
    )


def audit_ipc(command_type: str, sync_dir: str, signed: bool = False,
              content: str = ""):
    """Convenience: log an IPC command event."""
    audit(
        "ipc.command_sent",
        command_type=command_type,
        sync_dir=sync_dir,
        signed=signed,
        content=content,
    )


def close():
    """Flush and close the audit log file."""
    global _current_file
    with _lock:
        if _current_file is not None:
            try:
                _current_file.flush()
                _current_file.close()
            except Exception:
                pass
            _current_file = None


# ---------------------------------------------------------------------------
# Hash-chain verification
# ---------------------------------------------------------------------------

def verify_chain(path: str | Path) -> tuple[bool, list[str]]:
    """Verify the hash-chain integrity of an audit log file.

    Returns:
        (all_valid, errors) — errors is a list of human-readable descriptions
        of any broken links.  Empty list means the file is intact.
    """
    path = Path(path)
    if not path.exists():
        return False, [f"File not found: {path}"]

    errors: list[str] = []
    prev_hash = "0" * 64  # genesis
    line_num = 0

    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line_num += 1
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                errors.append(f"Line {line_num}: invalid JSON — {exc}")
                continue

            stored_hash = entry.pop("entry_hash", None)
            if stored_hash is None:
                errors.append(f"Line {line_num}: missing entry_hash")
                continue

            # Check prev_hash link
            if entry.get("prev_hash") != prev_hash:
                errors.append(
                    f"Line {line_num}: prev_hash mismatch — "
                    f"expected {prev_hash[:16]}..., got {entry.get('prev_hash', 'MISSING')[:16]}..."
                )

            # Recompute entry hash
            canonical = json.dumps(entry, ensure_ascii=False, default=str, sort_keys=True)
            expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if stored_hash != expected_hash:
                errors.append(
                    f"Line {line_num}: entry_hash mismatch (tampered?) — "
                    f"expected {expected_hash[:16]}..., got {stored_hash[:16]}..."
                )

            prev_hash = stored_hash

    return (len(errors) == 0, errors)
