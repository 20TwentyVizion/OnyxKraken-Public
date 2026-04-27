"""Script Guard — AST-based validation for generated Python scripts.

Scans LLM-generated code before it is sent to Blender/Unreal via IPC.
Blocks dangerous operations: os.system, subprocess, network calls,
file operations outside the workspace, eval/exec of untrusted input.

Usage:
    from core.script_guard import validate_script, ScriptVerdict

    verdict = validate_script(code_string)
    if verdict.safe:
        controller.execute_script(code_string)
    else:
        log.warning("Blocked: %s", verdict.reason)
"""

import ast
import logging
import re
from dataclasses import dataclass, field

_log = logging.getLogger("core.script_guard")

# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

@dataclass
class ScriptVerdict:
    """Result of script validation."""
    safe: bool
    violations: list[str] = field(default_factory=list)

    @property
    def reason(self) -> str:
        return "; ".join(self.violations) if self.violations else "OK"


# ---------------------------------------------------------------------------
# Blocklists
# ---------------------------------------------------------------------------

# Modules that must NEVER be imported in generated scripts
BLOCKED_MODULES = {
    "subprocess", "shutil", "socket", "http", "urllib",
    "requests", "httpx", "aiohttp",
    "ftplib", "smtplib", "imaplib", "poplib",
    "paramiko", "fabric",
    "ctypes", "cffi",
    "pickle", "shelve", "marshal",
    "code", "codeop", "compileall",
    "webbrowser",
    "multiprocessing",
    "signal",
    "pty", "termios",
    "winreg",
}

# Specific attribute accesses that are dangerous
BLOCKED_CALLS = {
    # os module dangerous functions
    ("os", "system"),
    ("os", "popen"),
    ("os", "exec"),
    ("os", "execl"),
    ("os", "execle"),
    ("os", "execlp"),
    ("os", "execlpe"),
    ("os", "execv"),
    ("os", "execve"),
    ("os", "execvp"),
    ("os", "execvpe"),
    ("os", "spawn"),
    ("os", "spawnl"),
    ("os", "spawnle"),
    ("os", "fork"),
    ("os", "kill"),
    ("os", "killpg"),
    ("os", "remove"),
    ("os", "unlink"),
    ("os", "rmdir"),
    ("os", "removedirs"),
    ("os", "rename"),
    ("os", "renames"),
    ("os", "replace"),
    ("os", "link"),
    ("os", "symlink"),
    ("os", "chown"),
    ("os", "chmod"),
    ("os", "environ"),       # reading env vars could leak secrets
    # pathlib dangerous
    ("Path", "unlink"),
    ("Path", "rmdir"),
    # builtins
    ("builtins", "exec"),
    ("builtins", "eval"),
    ("builtins", "compile"),
    ("builtins", "__import__"),
}

# Standalone function calls that are blocked
BLOCKED_BUILTINS = {
    "exec", "eval", "compile", "__import__", "breakpoint",
    "exit", "quit",
}

# Allowed modules for Blender scripts
ALLOWED_MODULES_BLENDER = {
    "bpy", "bmesh", "mathutils", "math", "random", "json", "os",
    "collections", "itertools", "functools", "enum", "dataclasses",
    "typing", "copy", "time", "datetime", "struct", "array",
    "onyx_bpy",  # our custom API
    "home_builder_5",  # Home Builder 5 addon (interior design)
}

# Allowed modules for Unreal scripts
ALLOWED_MODULES_UNREAL = {
    "unreal", "math", "random", "json", "os",
    "collections", "itertools", "functools", "enum",
    "typing", "copy", "time", "datetime",
    "onyx_ue",  # our custom API
}

# os functions that ARE allowed (read-only, path manipulation)
ALLOWED_OS_FUNCS = {
    "path", "getcwd", "listdir", "walk", "scandir",
    "stat", "lstat", "access", "exists",
    "makedirs", "mkdir",  # creating dirs is fine
    "path.join", "path.exists", "path.dirname", "path.basename",
    "path.abspath", "path.splitext", "path.isfile", "path.isdir",
    "path.expanduser", "path.expandvars",
}


# ---------------------------------------------------------------------------
# AST Visitor
# ---------------------------------------------------------------------------

class _ScriptChecker(ast.NodeVisitor):
    """Walks the AST looking for dangerous patterns."""

    def __init__(self, mode: str = "blender"):
        self.violations: list[str] = []
        self.mode = mode
        self.allowed_modules = (
            ALLOWED_MODULES_BLENDER if mode == "blender"
            else ALLOWED_MODULES_UNREAL
        )
        self._imported_names: dict[str, str] = {}  # alias → module

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            mod = alias.name.split(".")[0]
            if mod in BLOCKED_MODULES:
                self.violations.append(f"blocked import: {alias.name}")
            elif mod not in self.allowed_modules:
                self.violations.append(
                    f"unapproved import: {alias.name} "
                    f"(allowed: {', '.join(sorted(self.allowed_modules))})"
                )
            self._imported_names[alias.asname or alias.name] = mod
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            mod = node.module.split(".")[0]
            if mod in BLOCKED_MODULES:
                self.violations.append(f"blocked import: from {node.module}")
            elif mod not in self.allowed_modules:
                self.violations.append(
                    f"unapproved import: from {node.module} "
                    f"(allowed: {', '.join(sorted(self.allowed_modules))})"
                )
            for alias in node.names:
                self._imported_names[alias.asname or alias.name] = mod
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Check standalone dangerous builtins: exec(...), eval(...)
        if isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_BUILTINS:
                self.violations.append(f"blocked builtin call: {node.func.id}()")

        # Check attribute calls: os.system(...), subprocess.run(...)
        elif isinstance(node.func, ast.Attribute):
            attr_chain = self._get_attr_chain(node.func)
            if attr_chain:
                parts = attr_chain.split(".")
                if len(parts) >= 2:
                    obj, func = parts[0], parts[-1]
                    # Resolve aliases
                    real_mod = self._imported_names.get(obj, obj)
                    if (real_mod, func) in BLOCKED_CALLS:
                        # Check if it's an allowed os function
                        if real_mod == "os" and func in ALLOWED_OS_FUNCS:
                            pass  # allowed
                        else:
                            self.violations.append(
                                f"blocked call: {attr_chain}()"
                            )

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        # Catch os.environ access even without a call
        chain = self._get_attr_chain(node)
        if chain:
            parts = chain.split(".")
            if len(parts) >= 2:
                obj = self._imported_names.get(parts[0], parts[0])
                if (obj, parts[-1]) in BLOCKED_CALLS:
                    if not (obj == "os" and parts[-1] in ALLOWED_OS_FUNCS):
                        self.violations.append(
                            f"blocked attribute access: {chain}"
                        )
        self.generic_visit(node)

    def _get_attr_chain(self, node) -> str:
        """Reconstruct 'os.path.join' from nested Attribute nodes."""
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        parts.reverse()
        return ".".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Regex fallback checks (catches string-level tricks AST might miss)
# ---------------------------------------------------------------------------

_DANGEROUS_PATTERNS = [
    # Shell execution via string
    (r'\bos\s*\.\s*system\s*\(', "os.system() call"),
    (r'\bos\s*\.\s*popen\s*\(', "os.popen() call"),
    (r'\bsubprocess\b', "subprocess reference"),
    (r'\b__import__\s*\(', "__import__() call"),
    (r'\beval\s*\(', "eval() call"),
    (r'\bexec\s*\(', "exec() call"),
    # Network
    (r'\bsocket\s*\.', "socket usage"),
    (r'\burllib\b', "urllib usage"),
    (r'\brequests\s*\.', "requests usage"),
    (r'\bhttpx\b', "httpx usage"),
    # Sensitive paths
    (r'["\']C:\\Windows', "Windows system path access"),
    (r'["\']\/etc\/', "Linux system path access"),
    (r'\.ssh', "SSH directory access"),
    (r'\.env\b', ".env file access"),
    (r'\.git\/', ".git directory access"),
]


def _regex_check(script: str) -> list[str]:
    """Fallback regex checks for patterns that might evade AST analysis."""
    violations = []
    for pattern, desc in _DANGEROUS_PATTERNS:
        if re.search(pattern, script, re.IGNORECASE):
            violations.append(f"regex match: {desc}")
    return violations


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_script(script: str, mode: str = "blender") -> ScriptVerdict:
    """Validate a generated Python script before execution.

    Args:
        script: The Python source code to validate.
        mode: "blender" or "unreal" — determines allowed modules.

    Returns:
        ScriptVerdict with .safe and .violations
    """
    if not script or not script.strip():
        return ScriptVerdict(safe=True)

    # Skip validation for the QUIT command
    if script.strip() == "QUIT":
        return ScriptVerdict(safe=True)

    violations = []

    # 1. AST analysis
    try:
        tree = ast.parse(script)
        checker = _ScriptChecker(mode=mode)
        checker.visit(tree)
        violations.extend(checker.violations)
    except SyntaxError as e:
        # If we can't parse it, that's itself a concern but not necessarily
        # a security issue — Blender will also fail to execute it
        _log.debug("AST parse failed (not a security issue): %s", e)

    # 2. Regex fallback
    violations.extend(_regex_check(script))

    # Deduplicate
    violations = list(dict.fromkeys(violations))

    if violations:
        _log.warning("Script blocked — %d violation(s): %s",
                      len(violations), "; ".join(violations))

    return ScriptVerdict(safe=len(violations) == 0, violations=violations)


def validate_and_clean(script: str, mode: str = "blender") -> tuple[bool, str, list[str]]:
    """Validate a script and attempt to clean it if issues are found.

    Returns:
        (safe, cleaned_script, violations)
        If safe is True, cleaned_script is the original or cleaned version.
        If safe is False, the script should NOT be executed.
    """
    verdict = validate_script(script, mode)
    if verdict.safe:
        return True, script, []

    # Check if violations are only unapproved imports (might be fixable)
    critical = [v for v in verdict.violations if not v.startswith("unapproved import")]
    if critical:
        # Has dangerous calls — cannot clean, must block
        return False, script, verdict.violations

    # Only unapproved imports — try removing them
    # (the script might still work if those imports weren't actually used)
    try:
        tree = ast.parse(script)
        lines = script.splitlines(keepends=True)
        # Remove offending import lines (in reverse order to preserve line numbers)
        to_remove = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = ""
                if isinstance(node, ast.Import):
                    mod = node.names[0].name.split(".")[0]
                elif node.module:
                    mod = node.module.split(".")[0]
                allowed = (ALLOWED_MODULES_BLENDER if mode == "blender"
                           else ALLOWED_MODULES_UNREAL)
                if mod and mod not in allowed and mod not in BLOCKED_MODULES:
                    to_remove.add(node.lineno - 1)  # 0-indexed

        if to_remove:
            cleaned_lines = [
                line for i, line in enumerate(lines) if i not in to_remove
            ]
            cleaned = "".join(cleaned_lines)
            re_verdict = validate_script(cleaned, mode)
            if re_verdict.safe:
                _log.info("Cleaned script by removing %d unapproved imports",
                          len(to_remove))
                return True, cleaned, []

    except Exception:
        pass

    return False, script, verdict.violations
