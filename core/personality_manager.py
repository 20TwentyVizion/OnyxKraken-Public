"""Personality manager for OnyxKraken.

Manages personality presets:
  - Loading/saving presets from disk
  - Switching between presets
  - Creating custom presets
  - Tracking active preset
"""

import json
from pathlib import Path
from typing import Optional

from core.personality import PersonalityPreset, load_preset_from_file, save_preset_to_file
from log import get_logger

_log = get_logger("personality_manager")


class PersonalityManager:
    """Manages personality presets and switching."""

    def __init__(self, presets_dir: Optional[Path] = None, active_file: Optional[Path] = None):
        """Initialize the personality manager.

        Args:
            presets_dir: Directory containing preset JSON files (default: data/personality_presets)
            active_file: File tracking the active preset (default: data/active_personality.json)
        """
        if presets_dir is None:
            presets_dir = Path(__file__).parent.parent / "data" / "personality_presets"
        if active_file is None:
            active_file = Path(__file__).parent.parent / "data" / "active_personality.json"

        self.presets_dir = presets_dir
        self.active_file = active_file
        self.presets_dir.mkdir(parents=True, exist_ok=True)

        self._presets: dict[str, PersonalityPreset] = {}
        self._active_preset: Optional[PersonalityPreset] = None

        self._load_all_presets()
        self._load_active_preset()

    def _load_all_presets(self):
        """Load all preset files from the presets directory."""
        if not self.presets_dir.exists():
            _log.warning(f"Presets directory not found: {self.presets_dir}")
            return

        for preset_file in self.presets_dir.glob("*.json"):
            preset = load_preset_from_file(preset_file)
            if preset:
                self._presets[preset.name] = preset
                _log.info(f"Loaded preset: {preset.name}")

    def _load_active_preset(self):
        """Load the active preset from the active_personality.json file."""
        if not self.active_file.exists():
            # Default to "OnyxKraken Default" if no active preset is set
            self._active_preset = self._presets.get("OnyxKraken Default")
            if self._active_preset:
                _log.info("No active preset file found, defaulting to 'OnyxKraken Default'")
                self._save_active_preset()
            return

        try:
            with open(self.active_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            preset_name = data.get("active_preset")
            if preset_name and preset_name in self._presets:
                self._active_preset = self._presets[preset_name]
                _log.info(f"Active preset: {preset_name}")
            else:
                _log.warning(f"Active preset '{preset_name}' not found, using default")
                self._active_preset = self._presets.get("OnyxKraken Default")
        except (json.JSONDecodeError, IOError) as e:
            _log.error(f"Failed to load active preset: {e}")
            self._active_preset = self._presets.get("OnyxKraken Default")

    def _save_active_preset(self):
        """Save the current active preset name to disk."""
        if not self._active_preset:
            return

        data = {"active_preset": self._active_preset.name}
        self.active_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.active_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def list_presets(self) -> list[str]:
        """List all available preset names.

        Returns:
            List of preset names
        """
        return sorted(self._presets.keys())

    def get_preset(self, name: str) -> Optional[PersonalityPreset]:
        """Get a preset by name.

        Args:
            name: Preset name

        Returns:
            PersonalityPreset instance or None if not found
        """
        return self._presets.get(name)

    def get_active_preset(self) -> Optional[PersonalityPreset]:
        """Get the currently active preset.

        Returns:
            Active PersonalityPreset instance or None
        """
        return self._active_preset

    def switch_preset(self, name: str) -> bool:
        """Switch to a different preset.

        Args:
            name: Name of the preset to switch to

        Returns:
            True if successful, False if preset not found
        """
        if name not in self._presets:
            _log.error(f"Preset '{name}' not found")
            return False

        previous = self._active_preset
        self._active_preset = self._presets[name]
        self._save_active_preset()
        _log.info(f"Switched to preset: {name}")

        # Emit event so Voice, Chat, Mind, etc. can react
        try:
            from core.events import bus, PERSONALITY_CHANGED
            bus.emit(PERSONALITY_CHANGED, {
                "preset_name": name,
                "preset": self._active_preset,
                "previous_name": previous.name if previous else None,
            })
        except Exception as e:
            _log.debug(f"Could not emit personality_changed: {e}")

        return True

    def save_preset(self, preset: PersonalityPreset, set_active: bool = False):
        """Save a preset to disk.

        Args:
            preset: PersonalityPreset instance to save
            set_active: If True, set this as the active preset
        """
        preset_path = self.presets_dir / f"{preset.name.lower().replace(' ', '_')}.json"
        save_preset_to_file(preset, preset_path)
        self._presets[preset.name] = preset

        if set_active:
            self._active_preset = preset
            self._save_active_preset()

    def create_custom_preset(
        self,
        name: str,
        base_preset_name: str = "OnyxKraken Default",
        modifications: Optional[dict] = None,
    ) -> Optional[PersonalityPreset]:
        """Create a custom preset based on an existing one.

        Args:
            name: Name for the new preset
            base_preset_name: Name of the preset to use as a base
            modifications: Dictionary of modifications to apply

        Returns:
            New PersonalityPreset instance or None if base not found
        """
        base = self._presets.get(base_preset_name)
        if not base:
            _log.error(f"Base preset '{base_preset_name}' not found")
            return None

        # Deep copy the base preset data
        import copy
        new_data = copy.deepcopy(base.to_dict())
        new_data["name"] = name
        new_data["version"] = "1.0"

        # Apply modifications
        if modifications:
            for key, value in modifications.items():
                if key in new_data:
                    if isinstance(new_data[key], dict) and isinstance(value, dict):
                        new_data[key].update(value)
                    else:
                        new_data[key] = value
                else:
                    new_data[key] = value

        new_preset = PersonalityPreset(new_data)
        _log.info(f"Created custom preset: {name} (based on {base_preset_name})")
        return new_preset

    def delete_preset(self, name: str) -> bool:
        """Delete a preset.

        Args:
            name: Name of the preset to delete

        Returns:
            True if successful, False if preset not found or is active
        """
        if name not in self._presets:
            _log.error(f"Preset '{name}' not found")
            return False

        if self._active_preset and self._active_preset.name == name:
            _log.error(f"Cannot delete active preset '{name}'")
            return False

        # Delete from disk
        preset_path = self.presets_dir / f"{name.lower().replace(' ', '_')}.json"
        if preset_path.exists():
            preset_path.unlink()

        # Remove from memory
        del self._presets[name]
        _log.info(f"Deleted preset: {name}")
        return True

    def reload_presets(self):
        """Reload all presets from disk."""
        self._presets.clear()
        self._load_all_presets()
        self._load_active_preset()
        _log.info("Reloaded all presets")


# ---------------------------------------------------------------------------
# Singleton (delegates to service registry)
# ---------------------------------------------------------------------------

def get_personality_manager() -> PersonalityManager:
    """Get the singleton personality manager instance."""
    from core.service_registry import services
    if not services.has("personality_manager"):
        services.register_factory("personality_manager", PersonalityManager)
    return services.get("personality_manager", PersonalityManager)
