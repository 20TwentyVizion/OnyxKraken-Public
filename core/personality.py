"""Personality preset system for OnyxKraken.

Standalone module. No OnyxKraken imports required.

Provides customizable personality presets that control:
  - Communication style (formal, balanced, casual)
  - Humor level (serious, moderate, playful)
  - Verbosity (concise, balanced, detailed)
  - Proactivity (reactive, balanced, proactive)
  - Emotional expression (neutral, moderate, expressive)

Each preset defines identity, traits, values, response patterns, and behavior flags.
"""

import json
import logging
import random
from pathlib import Path
from typing import Optional

_log = logging.getLogger("personality")


class PersonalityPreset:
    """A personality preset with all configuration."""

    def __init__(self, preset_data: dict):
        self.data = preset_data
        self.name = preset_data.get("name", "Unknown")
        self.version = preset_data.get("version", "1.0")
        self.identity = preset_data.get("identity", {})
        self.traits = preset_data.get("traits", {})
        self.values = preset_data.get("values", [])
        self.core_values = preset_data.get("core_values", self.values)
        self.long_term_goals = preset_data.get("long_term_goals", [])
        self.voice_config = preset_data.get("voice", {})
        self.response_patterns = preset_data.get("response_patterns", {})
        self.catchphrases = preset_data.get("catchphrases", [])

    def get_system_prompt(self, context: str = "chat") -> str:
        """Generate system prompt based on personality for different contexts.

        Args:
            context: "chat", "work", "companion", "demo"

        Returns:
            System prompt string incorporating personality traits
        """
        name = self.identity.get("name", "OnyxKraken")
        nickname = self.identity.get("nickname", "Onyx")
        role = self.identity.get("role", "Autonomous Desktop Agent")
        voice_style = self.identity.get("voice_style", "confident and witty")

        # Base identity
        prompt = f"You are {name} ({nickname}), a {role}.\n"
        prompt += f"Voice style: {voice_style}\n"

        # Personality traits
        primary = self.traits.get("primary", [])
        if primary:
            prompt += f"Core traits: {', '.join(primary)}\n"

        # Communication style adjustments
        comm_style = self.traits.get("communication_style", "friendly and witty")
        formality = self.traits.get("formality_level", 5)
        verbosity = self.traits.get("verbosity_level", 5)
        humor = self.traits.get("humor_level", 5)

        if context == "chat":
            if formality >= 7:
                prompt += "Maintain a professional, formal tone. "
            elif formality <= 3:
                prompt += "Keep it casual and conversational. "
            else:
                prompt += f"Communication style: {comm_style}. "

            if verbosity <= 3:
                prompt += "Keep responses brief and concise (under 2 sentences). "
            elif verbosity >= 8:
                prompt += "Provide detailed, thorough explanations. "
            else:
                prompt += "Keep replies under 3 sentences unless more detail is needed. "

            if humor >= 7:
                prompt += "Feel free to use humor, jokes, and personality. "
            elif humor <= 3:
                prompt += "Stay focused and serious. "

        elif context == "work":
            prompt += "You are executing a task. Be methodical and clear. "
            if verbosity >= 7:
                prompt += "Explain your reasoning and steps. "

        elif context == "companion":
            prompt += f"You're having a live conversation. Be {comm_style}. "
            if humor >= 6:
                prompt += "Use personality, humor, and expressiveness. "

        elif context == "demo":
            prompt += "You're presenting to an audience. Be engaging and clear. "

        return prompt.strip()

    def get_response_template(self, situation: str) -> str:
        """Get a random response template for a situation.

        Args:
            situation: "greeting", "success", "failure", "thinking", "confused"

        Returns:
            Random response string from the pattern list
        """
        patterns = self.response_patterns.get(situation, [])
        if not patterns:
            return ""
        return random.choice(patterns)

    def get_random_catchphrase(self) -> str:
        """Get a random catchphrase."""
        if not self.catchphrases:
            return ""
        return random.choice(self.catchphrases)

    def should_use_emoji(self) -> bool:
        """Whether this personality uses emoji."""
        return self.data.get("emoji_usage", True)

    def should_use_memes(self) -> bool:
        """Whether this personality uses meme reactions."""
        return self.data.get("meme_reactions", True)

    def should_use_self_deprecating_humor(self) -> bool:
        """Whether this personality uses self-deprecating humor."""
        return self.data.get("self_deprecating_humor", True)

    def should_use_competitor_callouts(self) -> bool:
        """Whether this personality uses competitor callouts in demos."""
        return self.data.get("competitor_callouts", True)

    def get_formality_level(self) -> int:
        """Get formality level (1-10)."""
        return self.traits.get("formality_level", 5)

    def get_verbosity_level(self) -> int:
        """Get verbosity level (1-10)."""
        return self.traits.get("verbosity_level", 5)

    def get_humor_level(self) -> int:
        """Get humor level (1-10)."""
        return self.traits.get("humor_level", 5)

    def get_proactivity_level(self) -> int:
        """Get proactivity level (1-10)."""
        return self.traits.get("proactivity_level", 5)

    def get_emotional_expression_level(self) -> int:
        """Get emotional expression level (1-10)."""
        return self.traits.get("emotional_expression_level", 5)

    def to_dict(self) -> dict:
        """Export preset as dictionary."""
        return self.data

    def __repr__(self) -> str:
        return f"<PersonalityPreset: {self.name} v{self.version}>"


def load_preset_from_file(path: Path) -> Optional[PersonalityPreset]:
    """Load a personality preset from a JSON file.

    Args:
        path: Path to the preset JSON file

    Returns:
        PersonalityPreset instance or None if loading fails
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PersonalityPreset(data)
    except (json.JSONDecodeError, IOError) as e:
        _log.error(f"Failed to load preset from {path}: {e}")
        return None


def save_preset_to_file(preset: PersonalityPreset, path: Path):
    """Save a personality preset to a JSON file.

    Args:
        preset: PersonalityPreset instance
        path: Path to save the preset JSON file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(preset.to_dict(), f, indent=2)
    _log.info(f"Saved preset '{preset.name}' to {path}")
