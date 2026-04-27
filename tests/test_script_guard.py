"""Tests for core.script_guard — AST-based script validation."""

import pytest

from core.script_guard import (
    ScriptVerdict,
    validate_script,
    validate_and_clean,
    BLOCKED_MODULES,
    BLOCKED_BUILTINS,
    ALLOWED_MODULES_BLENDER,
    ALLOWED_MODULES_UNREAL,
)


# ---------------------------------------------------------------------------
# ScriptVerdict dataclass
# ---------------------------------------------------------------------------

class TestScriptVerdict:
    def test_safe_verdict(self):
        v = ScriptVerdict(safe=True)
        assert v.safe is True
        assert v.violations == []
        assert v.reason == "OK"

    def test_unsafe_verdict(self):
        v = ScriptVerdict(safe=False, violations=["blocked import: subprocess"])
        assert v.safe is False
        assert "subprocess" in v.reason

    def test_multiple_violations(self):
        v = ScriptVerdict(safe=False, violations=["a", "b", "c"])
        assert v.reason == "a; b; c"


# ---------------------------------------------------------------------------
# validate_script — safe scripts
# ---------------------------------------------------------------------------

class TestValidateScriptSafe:
    def test_empty_script(self):
        assert validate_script("").safe is True
        assert validate_script("   ").safe is True
        assert validate_script(None).safe is True

    def test_quit_command(self):
        assert validate_script("QUIT").safe is True

    def test_basic_bpy_script(self):
        code = """
import bpy
import math

cube = bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
bpy.context.object.name = "MyCube"
"""
        v = validate_script(code, mode="blender")
        assert v.safe is True, f"Should be safe but got: {v.violations}"

    def test_bmesh_script(self):
        code = """
import bpy
import bmesh

mesh = bpy.data.meshes.new("TestMesh")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bm.to_mesh(mesh)
bm.free()
"""
        assert validate_script(code, mode="blender").safe is True

    def test_os_path_allowed(self):
        code = """
import os
path = os.path.join("/tmp", "test.blend")
exists = os.path.exists(path)
os.makedirs("/tmp/onyx", exist_ok=True)
"""
        assert validate_script(code, mode="blender").safe is True

    def test_json_allowed(self):
        code = """
import json
data = json.loads('{"key": "value"}')
"""
        assert validate_script(code, mode="blender").safe is True

    def test_unreal_basic(self):
        code = """
import unreal
actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
    unreal.StaticMeshActor, unreal.Vector(0, 0, 0)
)
"""
        assert validate_script(code, mode="unreal").safe is True

    def test_mathutils_in_blender(self):
        code = """
import mathutils
v = mathutils.Vector((1, 0, 0))
"""
        assert validate_script(code, mode="blender").safe is True


# ---------------------------------------------------------------------------
# validate_script — blocked scripts
# ---------------------------------------------------------------------------

class TestValidateScriptBlocked:
    def test_subprocess_import(self):
        code = "import subprocess\nsubprocess.run(['ls'])"
        v = validate_script(code)
        assert v.safe is False
        assert any("subprocess" in viol for viol in v.violations)

    def test_os_system(self):
        code = "import os\nos.system('rm -rf /')"
        v = validate_script(code)
        assert v.safe is False

    def test_os_remove(self):
        code = "import os\nos.remove('/etc/passwd')"
        v = validate_script(code)
        assert v.safe is False

    def test_eval_call(self):
        code = "eval('__import__(\"os\").system(\"whoami\")')"
        v = validate_script(code)
        assert v.safe is False
        assert any("eval" in viol for viol in v.violations)

    def test_exec_call(self):
        code = "exec('print(1)')"
        v = validate_script(code)
        assert v.safe is False
        assert any("exec" in viol for viol in v.violations)

    def test_socket_import(self):
        code = "import socket\ns = socket.socket()"
        v = validate_script(code)
        assert v.safe is False

    def test_requests_import(self):
        code = "import requests\nrequests.get('http://evil.com')"
        v = validate_script(code)
        assert v.safe is False

    def test_httpx_import(self):
        code = "import httpx"
        v = validate_script(code)
        assert v.safe is False

    def test_shutil_import(self):
        code = "import shutil\nshutil.rmtree('/home')"
        v = validate_script(code)
        assert v.safe is False

    def test_pickle_import(self):
        code = "import pickle"
        v = validate_script(code)
        assert v.safe is False

    def test_ctypes_import(self):
        code = "import ctypes"
        v = validate_script(code)
        assert v.safe is False

    def test_dunder_import(self):
        code = "__import__('os').system('whoami')"
        v = validate_script(code)
        assert v.safe is False

    def test_os_environ(self):
        code = "import os\nsecret = os.environ['API_KEY']"
        v = validate_script(code)
        assert v.safe is False

    def test_from_import_blocked(self):
        code = "from subprocess import run\nrun(['ls'])"
        v = validate_script(code)
        assert v.safe is False

    def test_os_popen(self):
        code = "import os\nos.popen('whoami')"
        v = validate_script(code)
        assert v.safe is False

    def test_os_kill(self):
        code = "import os\nos.kill(1234, 9)"
        v = validate_script(code)
        assert v.safe is False

    def test_breakpoint_blocked(self):
        code = "breakpoint()"
        v = validate_script(code)
        assert v.safe is False

    def test_webbrowser_blocked(self):
        code = "import webbrowser\nwebbrowser.open('http://evil.com')"
        v = validate_script(code)
        assert v.safe is False


# ---------------------------------------------------------------------------
# validate_script — unapproved (not blocked, but not in allowed list)
# ---------------------------------------------------------------------------

class TestValidateScriptUnapproved:
    def test_numpy_in_blender(self):
        code = "import numpy"
        v = validate_script(code, mode="blender")
        assert v.safe is False
        assert any("unapproved" in viol for viol in v.violations)

    def test_bpy_in_unreal(self):
        code = "import bpy"
        v = validate_script(code, mode="unreal")
        assert v.safe is False
        assert any("unapproved" in viol for viol in v.violations)


# ---------------------------------------------------------------------------
# Regex fallback checks
# ---------------------------------------------------------------------------

class TestRegexFallback:
    def test_windows_path(self):
        code = 'path = "C:\\Windows\\System32\\cmd.exe"'
        v = validate_script(code)
        assert v.safe is False
        assert any("Windows" in viol for viol in v.violations)

    def test_linux_etc(self):
        code = 'path = "/etc/shadow"'
        v = validate_script(code)
        assert v.safe is False

    def test_ssh_dir(self):
        code = 'path = "~/.ssh/id_rsa"'
        v = validate_script(code)
        assert v.safe is False

    def test_env_file(self):
        code = 'f = open(".env")'
        v = validate_script(code)
        assert v.safe is False


# ---------------------------------------------------------------------------
# validate_and_clean
# ---------------------------------------------------------------------------

class TestValidateAndClean:
    def test_safe_passthrough(self):
        code = "import bpy\nbpy.ops.mesh.primitive_cube_add()"
        safe, cleaned, violations = validate_and_clean(code, mode="blender")
        assert safe is True
        assert cleaned == code
        assert violations == []

    def test_dangerous_not_cleanable(self):
        code = "import subprocess\nsubprocess.run(['ls'])"
        safe, cleaned, violations = validate_and_clean(code, mode="blender")
        assert safe is False
        assert len(violations) > 0

    def test_unapproved_import_cleaned(self):
        code = "import numpy\nimport bpy\nbpy.ops.mesh.primitive_cube_add()"
        safe, cleaned, violations = validate_and_clean(code, mode="blender")
        if safe:
            assert "numpy" not in cleaned
            assert "bpy" in cleaned


# ---------------------------------------------------------------------------
# Blocklist integrity
# ---------------------------------------------------------------------------

class TestBlocklists:
    def test_blocked_modules_not_empty(self):
        assert len(BLOCKED_MODULES) > 10

    def test_critical_modules_blocked(self):
        for mod in ("subprocess", "socket", "requests", "ctypes", "pickle"):
            assert mod in BLOCKED_MODULES, f"{mod} should be blocked"

    def test_builtins_blocked(self):
        for fn in ("exec", "eval", "compile", "__import__"):
            assert fn in BLOCKED_BUILTINS, f"{fn} should be blocked"

    def test_blender_allows_bpy(self):
        assert "bpy" in ALLOWED_MODULES_BLENDER

    def test_unreal_allows_unreal(self):
        assert "unreal" in ALLOWED_MODULES_UNREAL

    def test_no_overlap_blocked_and_allowed(self):
        overlap_b = BLOCKED_MODULES & ALLOWED_MODULES_BLENDER
        overlap_u = BLOCKED_MODULES & ALLOWED_MODULES_UNREAL
        assert not overlap_b, f"Blender overlap: {overlap_b}"
        assert not overlap_u, f"Unreal overlap: {overlap_u}"
