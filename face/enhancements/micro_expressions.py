"""Micro-expressions and subtle facial movements for more lifelike animation."""
import random
import time
from typing import Dict, Any, Optional


class MicroExpressionEngine:
    """Generates subtle micro-expressions during idle and conversation."""
    
    def __init__(self):
        self.last_micro = time.time()
        self.micro_interval = random.uniform(5.0, 10.0)
        self.current_micro = None
        self.micro_duration = 0.0
        self.micro_progress = 0.0
    
    def update(self, dt: float, base_emotion: str) -> Optional[Dict[str, float]]:
        """Update and get current micro-expression modifiers.
        
        Args:
            dt: Delta time in seconds
            base_emotion: Current base emotion name
        
        Returns:
            Dict of modifiers to apply, or None if no micro-expression
        """
        current_time = time.time()
        
        # Check if we should trigger a new micro-expression
        if self.current_micro is None:
            if current_time - self.last_micro > self.micro_interval:
                self._trigger_micro(base_emotion)
        else:
            # Update current micro-expression
            self.micro_progress += dt / self.micro_duration
            
            if self.micro_progress >= 1.0:
                # Micro-expression complete
                self.current_micro = None
                self.last_micro = current_time
                self.micro_interval = random.uniform(5.0, 10.0)
                return None
        
        if self.current_micro:
            # Calculate intensity (fade in, hold, fade out)
            if self.micro_progress < 0.2:
                # Fade in
                intensity = self.micro_progress / 0.2
            elif self.micro_progress > 0.8:
                # Fade out
                intensity = (1.0 - self.micro_progress) / 0.2
            else:
                # Hold
                intensity = 1.0
            
            # Apply intensity to modifiers
            return {
                key: value * intensity
                for key, value in self.current_micro["modifiers"].items()
            }
        
        return None
    
    def _trigger_micro(self, base_emotion: str):
        """Trigger a new micro-expression."""
        # Choose micro-expression based on base emotion
        micros = self._get_micros_for_emotion(base_emotion)
        
        if not micros:
            return
        
        micro = random.choice(micros)
        self.current_micro = micro
        self.micro_duration = micro["duration"]
        self.micro_progress = 0.0
    
    def _get_micros_for_emotion(self, emotion: str) -> list:
        """Get appropriate micro-expressions for an emotion."""
        # Define micro-expressions for each base emotion
        micros_by_emotion = {
            "neutral": [
                {
                    "name": "slight_smile",
                    "duration": 0.5,
                    "modifiers": {"mouth_curve": 0.1, "eye_squint": 0.05}
                },
                {
                    "name": "eyebrow_raise",
                    "duration": 0.4,
                    "modifiers": {"eyebrow_height": 0.15}
                },
                {
                    "name": "head_tilt",
                    "duration": 0.6,
                    "modifiers": {"head_angle": 5.0}
                },
            ],
            "thinking": [
                {
                    "name": "squint",
                    "duration": 0.8,
                    "modifiers": {"eye_squint": 0.2}
                },
                {
                    "name": "lip_press",
                    "duration": 0.6,
                    "modifiers": {"mouth_height": -0.1}
                },
                {
                    "name": "eyebrow_furrow",
                    "duration": 0.7,
                    "modifiers": {"eyebrow_angle": -10.0}
                },
            ],
            "happy": [
                {
                    "name": "eye_sparkle",
                    "duration": 0.3,
                    "modifiers": {"eye_brightness": 0.2}
                },
                {
                    "name": "cheek_raise",
                    "duration": 0.5,
                    "modifiers": {"eye_squint": 0.15, "mouth_curve": 0.05}
                },
            ],
            "curious": [
                {
                    "name": "one_eyebrow_raise",
                    "duration": 0.5,
                    "modifiers": {"eyebrow_asymmetry": 0.2}
                },
                {
                    "name": "head_tilt",
                    "duration": 0.7,
                    "modifiers": {"head_angle": 8.0}
                },
            ],
            "listening": [
                {
                    "name": "nod",
                    "duration": 0.4,
                    "modifiers": {"head_nod": 1.0}
                },
                {
                    "name": "attentive_eyes",
                    "duration": 0.6,
                    "modifiers": {"eye_width": 0.1}
                },
            ],
        }
        
        return micros_by_emotion.get(emotion, micros_by_emotion["neutral"])


class BreathingAnimation:
    """Subtle breathing animation for idle states."""
    
    def __init__(self, rate: float = 0.25):
        """Initialize breathing animation.
        
        Args:
            rate: Breaths per second (default: 15 breaths/min = 0.25/sec)
        """
        self.rate = rate
        self.phase = 0.0
    
    def update(self, dt: float) -> Dict[str, float]:
        """Update breathing animation.
        
        Args:
            dt: Delta time in seconds
        
        Returns:
            Dict of breathing modifiers
        """
        import math
        
        self.phase += dt * self.rate * 2 * math.pi
        
        # Sine wave for smooth breathing
        breath = math.sin(self.phase)
        
        # Breathing affects body slightly
        return {
            "body_scale_y": 1.0 + breath * 0.01,  # Very subtle
            "shoulder_height": breath * 2.0,       # Slight shoulder movement
        }


class IdleBehaviorEngine:
    """Combines micro-expressions, breathing, and other idle behaviors."""
    
    def __init__(self):
        self.micro_engine = MicroExpressionEngine()
        self.breathing = BreathingAnimation()
        self.last_shift = time.time()
        self.shift_interval = random.uniform(20.0, 40.0)
    
    def update(self, dt: float, base_emotion: str) -> Dict[str, float]:
        """Update all idle behaviors.
        
        Args:
            dt: Delta time in seconds
            base_emotion: Current base emotion
        
        Returns:
            Combined modifiers from all idle behaviors
        """
        modifiers = {}
        
        # Breathing
        breath_mods = self.breathing.update(dt)
        modifiers.update(breath_mods)
        
        # Micro-expressions
        micro_mods = self.micro_engine.update(dt, base_emotion)
        if micro_mods:
            modifiers.update(micro_mods)
        
        # Occasional weight shift
        current_time = time.time()
        if current_time - self.last_shift > self.shift_interval:
            self._trigger_weight_shift()
        
        return modifiers
    
    def _trigger_weight_shift(self):
        """Trigger a subtle weight shift (body lean)."""
        self.last_shift = time.time()
        self.shift_interval = random.uniform(20.0, 40.0)
        # Implementation would adjust body position slightly
