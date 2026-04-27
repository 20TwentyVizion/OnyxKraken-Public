"""Face Pack system — discovery, installation, and management of purchasable faces.

A face pack is a directory containing a manifest.json and optional assets.
Packs can be:
  - Built-in (shipped with Onyx in face/packs/)
  - Installed from a .zip downloaded after Gumroad purchase
  - Community-created and shared

Pack structure:
    my_pack/
        manifest.json     # Required: metadata + face spec overrides
        preview.png       # Optional: 400x360 preview image
        icon.png          # Optional: 64x64 icon for the shop

Manifest format:
    {
        "id": "cyberpunk_neon",
        "name": "Cyberpunk Neon",
        "version": "1.0.0",
        "author": "OnyxKraken",
        "description": "Neon-soaked cyberpunk aesthetic with glitch effects",
        "price": 0,                    # 0 = free, >0 = paid (cents)
        "gumroad_product": "",         # Gumroad product ID for paid packs
        "license_component": "",       # Component name for license check
        "tags": ["cyberpunk", "neon", "dark"],
        "spec_overrides": {            # Merged on top of base face_spec.json
            "colors": { ... },
            "themes": { ... },
            "eye_styles": { ... },
            "face_shapes": { ... },
            "accessories": { ... },
            "emotion_presets": { ... },
            "geometry": { ... }
        },
        "draw_plugins": []             # Optional: custom draw plugin module names
    }

Usage:
    from core.face_packs import pack_manager

    packs = pack_manager.list_packs()
    pack_manager.install_from_zip("/path/to/download.zip")
    pack_manager.activate_pack("cyberpunk_neon")
    spec = pack_manager.get_merged_spec()
"""

import json
import logging
import os
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger("core.face_packs")


# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------

def _builtin_packs_dir() -> Path:
    """Built-in packs shipped with Onyx."""
    return Path(__file__).parent.parent / "face" / "packs"


def _user_packs_dir() -> Path:
    """User-installed packs in ~/.onyxkraken/face_packs/."""
    d = Path.home() / ".onyxkraken" / "face_packs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _base_spec_path() -> Path:
    """Path to the base face_spec.json."""
    return Path(__file__).parent.parent / "face" / "face_spec.json"


# ---------------------------------------------------------------------------
# Face Pack dataclass
# ---------------------------------------------------------------------------

@dataclass
class FacePack:
    """Represents a discovered face pack."""
    id: str
    name: str
    version: str = "1.0.0"
    author: str = "Unknown"
    description: str = ""
    price: int = 0  # cents, 0 = free
    gumroad_product: str = ""
    license_component: str = ""
    tags: List[str] = field(default_factory=list)
    spec_overrides: Dict[str, Any] = field(default_factory=dict)
    draw_plugins: List[str] = field(default_factory=list)
    path: str = ""  # absolute path to pack directory
    builtin: bool = False
    installed: bool = True

    @property
    def is_free(self) -> bool:
        return self.price == 0

    @property
    def is_licensed(self) -> bool:
        """Check if this pack is licensed (free packs always return True)."""
        if self.is_free:
            return True
        if not self.license_component:
            return True
        try:
            from core.gumroad import is_component_licensed
            return is_component_licensed(self.license_component)
        except ImportError:
            return False

    @property
    def preview_path(self) -> Optional[str]:
        if self.path:
            p = Path(self.path) / "preview.png"
            if p.exists():
                return str(p)
        return None

    @property
    def icon_path(self) -> Optional[str]:
        if self.path:
            p = Path(self.path) / "icon.png"
            if p.exists():
                return str(p)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "price": self.price,
            "tags": self.tags,
            "builtin": self.builtin,
            "installed": self.installed,
            "is_free": self.is_free,
            "is_licensed": self.is_licensed,
            "has_preview": self.preview_path is not None,
        }


# ---------------------------------------------------------------------------
# Pack Manager
# ---------------------------------------------------------------------------

class FacePackManager:
    """Discovers, installs, activates, and manages face packs."""

    def __init__(self):
        self._packs: Dict[str, FacePack] = {}
        self._active_pack_id: Optional[str] = None
        self._base_spec: Optional[Dict] = None

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> List[FacePack]:
        """Scan builtin and user pack directories for face packs.

        Returns list of all discovered packs.
        """
        self._packs.clear()

        # Discover built-in packs
        builtin_dir = _builtin_packs_dir()
        if builtin_dir.exists():
            for pack_dir in sorted(builtin_dir.iterdir()):
                if pack_dir.is_dir():
                    pack = self._load_pack(pack_dir, builtin=True)
                    if pack:
                        self._packs[pack.id] = pack

        # Discover user-installed packs
        user_dir = _user_packs_dir()
        for pack_dir in sorted(user_dir.iterdir()):
            if pack_dir.is_dir():
                pack = self._load_pack(pack_dir, builtin=False)
                if pack:
                    # User packs override builtin packs with same ID
                    self._packs[pack.id] = pack

        _log.info("Discovered %d face pack(s)", len(self._packs))
        return list(self._packs.values())

    def _load_pack(self, pack_dir: Path, builtin: bool = False) -> Optional[FacePack]:
        """Load a face pack from a directory."""
        manifest_path = pack_dir / "manifest.json"
        if not manifest_path.exists():
            _log.debug("No manifest.json in %s — skipping", pack_dir.name)
            return None

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            _log.error("Failed to parse manifest in %s: %s", pack_dir.name, e)
            return None

        pack_id = data.get("id", pack_dir.name)

        return FacePack(
            id=pack_id,
            name=data.get("name", pack_id),
            version=data.get("version", "1.0.0"),
            author=data.get("author", "Unknown"),
            description=data.get("description", ""),
            price=data.get("price", 0),
            gumroad_product=data.get("gumroad_product", ""),
            license_component=data.get("license_component", ""),
            tags=data.get("tags", []),
            spec_overrides=data.get("spec_overrides", {}),
            draw_plugins=data.get("draw_plugins", []),
            path=str(pack_dir),
            builtin=builtin,
        )

    # ------------------------------------------------------------------
    # Installation
    # ------------------------------------------------------------------

    def install_from_zip(self, zip_path: str) -> Optional[FacePack]:
        """Install a face pack from a downloaded .zip file.

        The zip must contain a manifest.json at the root or in a single
        subdirectory.

        Args:
            zip_path: Path to the .zip file.

        Returns:
            Installed FacePack, or None on failure.
        """
        zip_path = Path(zip_path)
        if not zip_path.exists() or not zipfile.is_zipfile(str(zip_path)):
            _log.error("Invalid zip file: %s", zip_path)
            return None

        user_dir = _user_packs_dir()

        try:
            with zipfile.ZipFile(str(zip_path), "r") as zf:
                names = zf.namelist()

                # Find manifest.json — at root or one level deep
                manifest_name = None
                for name in names:
                    if name == "manifest.json" or name.endswith("/manifest.json"):
                        parts = name.split("/")
                        if len(parts) <= 2:
                            manifest_name = name
                            break

                if not manifest_name:
                    _log.error("No manifest.json found in %s", zip_path.name)
                    return None

                # Read manifest to get pack ID
                manifest_data = json.loads(zf.read(manifest_name))
                pack_id = manifest_data.get("id")
                if not pack_id:
                    _log.error("Manifest missing 'id' in %s", zip_path.name)
                    return None

                # Determine extraction prefix
                prefix = ""
                if "/" in manifest_name:
                    prefix = manifest_name.rsplit("/", 1)[0] + "/"

                # Extract to user packs directory
                target_dir = user_dir / pack_id
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                target_dir.mkdir(parents=True)

                for name in names:
                    if not name.startswith(prefix):
                        continue
                    relative = name[len(prefix):]
                    if not relative or relative.endswith("/"):
                        continue
                    dest = target_dir / relative
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, open(dest, "wb") as dst:
                        dst.write(src.read())

                _log.info("Installed face pack '%s' to %s", pack_id, target_dir)

                # Reload the pack
                pack = self._load_pack(target_dir, builtin=False)
                if pack:
                    self._packs[pack.id] = pack
                return pack

        except Exception as e:
            _log.error("Failed to install face pack from %s: %s", zip_path, e)
            return None

    def install_from_directory(self, source_dir: str) -> Optional[FacePack]:
        """Install a face pack by copying a directory.

        Args:
            source_dir: Path to the pack directory (must contain manifest.json).

        Returns:
            Installed FacePack, or None on failure.
        """
        source = Path(source_dir)
        manifest = source / "manifest.json"
        if not manifest.exists():
            _log.error("No manifest.json in %s", source)
            return None

        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            pack_id = data.get("id", source.name)
        except Exception as e:
            _log.error("Failed to read manifest: %s", e)
            return None

        target = _user_packs_dir() / pack_id
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)

        pack = self._load_pack(target, builtin=False)
        if pack:
            self._packs[pack.id] = pack
            _log.info("Installed face pack '%s' from directory", pack_id)
        return pack

    def uninstall(self, pack_id: str) -> bool:
        """Uninstall a user-installed face pack.

        Cannot uninstall built-in packs.

        Returns True if successfully removed.
        """
        pack = self._packs.get(pack_id)
        if not pack:
            _log.warning("Pack '%s' not found.", pack_id)
            return False

        if pack.builtin:
            _log.warning("Cannot uninstall built-in pack '%s'.", pack_id)
            return False

        pack_dir = Path(pack.path)
        if pack_dir.exists():
            try:
                shutil.rmtree(pack_dir)
            except Exception as e:
                _log.error("Failed to remove pack directory: %s", e)
                return False

        del self._packs[pack_id]

        # Deactivate if this was the active pack
        if self._active_pack_id == pack_id:
            self._active_pack_id = None

        _log.info("Uninstalled face pack '%s'", pack_id)
        return True

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def activate_pack(self, pack_id: str) -> bool:
        """Set a face pack as the active face.

        Args:
            pack_id: Pack ID to activate, or None to use base spec.

        Returns:
            True if activated successfully.
        """
        if pack_id is None:
            self._active_pack_id = None
            _save_active_pack(None)
            _log.info("Deactivated face pack — using default face.")
            return True

        pack = self._packs.get(pack_id)
        if not pack:
            _log.warning("Pack '%s' not found.", pack_id)
            return False

        if not pack.is_licensed:
            _log.warning("Pack '%s' requires a license.", pack_id)
            return False

        self._active_pack_id = pack_id
        _save_active_pack(pack_id)
        _log.info("Activated face pack: %s", pack.name)

        # Emit event on the bus
        try:
            from core.event_bus import bus
            bus.emit("face.pack_changed", {
                "pack_id": pack_id,
                "pack_name": pack.name,
            }, source="face_packs")
        except ImportError:
            pass

        return True

    def get_active_pack(self) -> Optional[FacePack]:
        """Return the currently active face pack, or None for default."""
        if self._active_pack_id:
            return self._packs.get(self._active_pack_id)
        return None

    # ------------------------------------------------------------------
    # Spec merging
    # ------------------------------------------------------------------

    def get_base_spec(self) -> Dict:
        """Load and cache the base face_spec.json."""
        if self._base_spec is None:
            spec_path = _base_spec_path()
            with open(spec_path, "r", encoding="utf-8") as f:
                self._base_spec = json.load(f)
        return self._base_spec

    def get_merged_spec(self) -> Dict:
        """Return the face spec with the active pack's overrides merged in.

        If no pack is active, returns the base spec unchanged.
        Merge is shallow per top-level key, deep for nested dicts.
        """
        base = json.loads(json.dumps(self.get_base_spec()))  # deep copy
        pack = self.get_active_pack()
        if not pack or not pack.spec_overrides:
            return base

        _deep_merge(base, pack.spec_overrides)
        return base

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_packs(self, tag: str = None, free_only: bool = False) -> List[FacePack]:
        """List all discovered packs, optionally filtered.

        Args:
            tag: Only return packs with this tag.
            free_only: Only return free packs.
        """
        if not self._packs:
            self.discover()

        packs = list(self._packs.values())

        if tag:
            packs = [p for p in packs if tag in p.tags]
        if free_only:
            packs = [p for p in packs if p.is_free]

        return packs

    def get_pack(self, pack_id: str) -> Optional[FacePack]:
        """Get a specific pack by ID."""
        return self._packs.get(pack_id)

    # ------------------------------------------------------------------
    # Init — load saved active pack
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Initialize: discover packs and restore last active pack."""
        self.discover()
        saved = _load_active_pack()
        if saved and saved in self._packs:
            self._active_pack_id = saved
            _log.info("Restored active face pack: %s", saved)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override into base (mutates base)."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _active_pack_file() -> Path:
    return Path.home() / ".onyxkraken" / "active_face_pack.txt"


def _save_active_pack(pack_id: Optional[str]) -> None:
    """Persist the active pack ID."""
    f = _active_pack_file()
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        if pack_id:
            f.write_text(pack_id, encoding="utf-8")
        elif f.exists():
            f.unlink()
    except Exception as e:
        _log.error("Failed to save active pack: %s", e)


def _load_active_pack() -> Optional[str]:
    """Load the saved active pack ID."""
    f = _active_pack_file()
    if f.exists():
        try:
            return f.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

pack_manager = FacePackManager()
