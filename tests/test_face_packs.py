"""Tests for core.face_packs — face pack discovery, install, activation."""

import json
import os
import shutil
import tempfile
import zipfile
import pytest
from pathlib import Path

from core.face_packs import FacePackManager, FacePack, _deep_merge


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    """Temp directory cleaned up after test."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def mgr(tmp_dir):
    """Fresh FacePackManager that scans the real built-in packs dir."""
    m = FacePackManager()
    m.discover()
    return m


@pytest.fixture
def sample_pack_dir(tmp_dir):
    """Create a sample face pack directory with a manifest."""
    pack_dir = os.path.join(tmp_dir, "test_pack")
    os.makedirs(pack_dir)
    manifest = {
        "id": "test_pack",
        "name": "Test Pack",
        "version": "1.0.0",
        "author": "Tester",
        "description": "A test face pack",
        "price": 0,
        "tags": ["test", "free"],
        "spec_overrides": {
            "colors": {
                "bg": "#111111",
                "accent_bright": "#ff0000"
            },
            "geometry": {
                "eye_width": 70
            }
        }
    }
    with open(os.path.join(pack_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f)
    return pack_dir


@pytest.fixture
def sample_zip(sample_pack_dir, tmp_dir):
    """Create a .zip from the sample pack directory."""
    zip_path = os.path.join(tmp_dir, "test_pack.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for root, dirs, files in os.walk(sample_pack_dir):
            for fname in files:
                full = os.path.join(root, fname)
                arcname = os.path.join("test_pack", os.path.relpath(full, sample_pack_dir))
                zf.write(full, arcname)
    return zip_path


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

class TestDiscovery:

    def test_discovers_builtin_packs(self, mgr):
        packs = mgr.list_packs()
        ids = [p.id for p in packs]
        assert "default" in ids
        assert "phantom" in ids
        assert "inferno" in ids

    def test_builtin_packs_are_marked_builtin(self, mgr):
        for p in mgr.list_packs():
            assert p.builtin is True

    def test_default_pack_is_free(self, mgr):
        default = mgr.get_pack("default")
        assert default is not None
        assert default.is_free is True

    def test_inferno_pack_is_paid(self, mgr):
        inferno = mgr.get_pack("inferno")
        assert inferno is not None
        assert inferno.is_free is False
        assert inferno.price == 299

    def test_phantom_has_spec_overrides(self, mgr):
        phantom = mgr.get_pack("phantom")
        assert phantom is not None
        assert "colors" in phantom.spec_overrides
        assert "geometry" in phantom.spec_overrides

    def test_pack_to_dict(self, mgr):
        p = mgr.get_pack("default")
        d = p.to_dict()
        assert d["id"] == "default"
        assert d["is_free"] is True
        assert "name" in d

    def test_filter_by_tag(self, mgr):
        free_packs = mgr.list_packs(tag="free")
        assert all("free" in p.tags for p in free_packs)

    def test_filter_free_only(self, mgr):
        free_packs = mgr.list_packs(free_only=True)
        assert all(p.is_free for p in free_packs)


# ---------------------------------------------------------------------------
# Spec merging
# ---------------------------------------------------------------------------

class TestSpecMerge:

    def test_base_spec_loads(self, mgr):
        spec = mgr.get_base_spec()
        assert "reference" in spec
        assert "colors" in spec
        assert "geometry" in spec

    def test_merged_spec_without_active_pack(self, mgr):
        spec = mgr.get_merged_spec()
        base = mgr.get_base_spec()
        assert spec["colors"]["bg"] == base["colors"]["bg"]

    def test_merged_spec_with_active_pack(self, mgr):
        mgr.activate_pack("phantom")
        spec = mgr.get_merged_spec()
        # Phantom overrides bg color
        assert spec["colors"]["bg"] == "#080a0e"
        # But reference should remain from base
        assert spec["reference"]["width"] == 400

    def test_deep_merge_utility(self):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"x": 10, "z": 30}, "c": 4}
        _deep_merge(base, override)
        assert base == {"a": {"x": 10, "y": 2, "z": 30}, "b": 3, "c": 4}


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------

class TestActivation:

    def test_activate_free_pack(self, mgr):
        ok = mgr.activate_pack("phantom")
        assert ok is True
        assert mgr.get_active_pack().id == "phantom"

    def test_deactivate(self, mgr):
        mgr.activate_pack("phantom")
        mgr.activate_pack(None)
        assert mgr.get_active_pack() is None

    def test_activate_nonexistent(self, mgr):
        ok = mgr.activate_pack("does_not_exist")
        assert ok is False

    def test_active_pack_persists(self, mgr):
        mgr.activate_pack("phantom")
        # Simulate restart
        mgr2 = FacePackManager()
        mgr2.init()
        assert mgr2._active_pack_id == "phantom"
        # Clean up
        mgr.activate_pack(None)


# ---------------------------------------------------------------------------
# Installation from zip
# ---------------------------------------------------------------------------

class TestInstallZip:

    def test_install_from_zip(self, mgr, sample_zip):
        pack = mgr.install_from_zip(sample_zip)
        assert pack is not None
        assert pack.id == "test_pack"
        assert pack.name == "Test Pack"
        assert pack.builtin is False

    def test_installed_pack_appears_in_list(self, mgr, sample_zip):
        mgr.install_from_zip(sample_zip)
        ids = [p.id for p in mgr.list_packs()]
        assert "test_pack" in ids

    def test_install_invalid_zip(self, mgr, tmp_dir):
        bad = os.path.join(tmp_dir, "bad.zip")
        with open(bad, "w") as f:
            f.write("not a zip")
        result = mgr.install_from_zip(bad)
        assert result is None

    def test_install_zip_no_manifest(self, mgr, tmp_dir):
        zip_path = os.path.join(tmp_dir, "empty.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", "no manifest here")
        result = mgr.install_from_zip(zip_path)
        assert result is None


# ---------------------------------------------------------------------------
# Installation from directory
# ---------------------------------------------------------------------------

class TestInstallDir:

    def test_install_from_directory(self, mgr, sample_pack_dir):
        pack = mgr.install_from_directory(sample_pack_dir)
        assert pack is not None
        assert pack.id == "test_pack"

    def test_install_dir_no_manifest(self, mgr, tmp_dir):
        empty_dir = os.path.join(tmp_dir, "empty")
        os.makedirs(empty_dir)
        result = mgr.install_from_directory(empty_dir)
        assert result is None


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------

class TestUninstall:

    def test_uninstall_user_pack(self, mgr, sample_zip):
        mgr.install_from_zip(sample_zip)
        assert mgr.get_pack("test_pack") is not None
        ok = mgr.uninstall("test_pack")
        assert ok is True
        assert mgr.get_pack("test_pack") is None

    def test_cannot_uninstall_builtin(self, mgr):
        ok = mgr.uninstall("default")
        assert ok is False

    def test_uninstall_nonexistent(self, mgr):
        ok = mgr.uninstall("nope")
        assert ok is False

    def test_uninstall_deactivates_if_active(self, mgr, sample_zip):
        mgr.install_from_zip(sample_zip)
        mgr.activate_pack("test_pack")
        mgr.uninstall("test_pack")
        assert mgr.get_active_pack() is None


# ---------------------------------------------------------------------------
# FacePack dataclass
# ---------------------------------------------------------------------------

class TestFacePackDataclass:

    def test_free_check(self):
        p = FacePack(id="t", name="T", price=0)
        assert p.is_free is True

    def test_paid_check(self):
        p = FacePack(id="t", name="T", price=499)
        assert p.is_free is False

    def test_preview_path_missing(self):
        p = FacePack(id="t", name="T", path="/nonexistent/path")
        assert p.preview_path is None
