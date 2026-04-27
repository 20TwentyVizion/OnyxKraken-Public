"""Gesture system for non-verbal communication (nods, shakes, shrugs, etc.)."""
import time
import math
from typing import Optional, Dict, Any
from enum import Enum


class GestureType(Enum):
    """Types of gestures the face can perform."""
    NOD = "nod"                    # Yes
    SHAKE = "shake"                # No
    TILT = "tilt"                  # Curious/confused
    SHRUG = "shrug"                # Don't know
    LEAN_FORWARD = "lean_forward"  # Interested
    LEAN_BACK = "lean_back"        # Surprised/skeptical
    CELEBRATE = "celebrate"        # Success!
    THINK = "think"                # Pondering


class Gesture:
    """A single gesture animation."""
    
    def __init__(
        self,
        gesture_type: GestureType,
        duration: float,
        keyframes: list
    ):
        """Initialize gesture.
        
        Args:
            gesture_type: Type of gesture
            duration: Total duration in seconds
            keyframes: List of (time, modifiers) tuples
        """
        self.type = gesture_type
        self.duration = duration
        self.keyframes = keyframes
        self.start_time = 0.0
        self.progress = 0.0
    
    def start(self, current_time: float):
        """Start the gesture."""
        self.start_time = current_time
        self.progress = 0.0
    
    def update(self, current_time: float) -> Optional[Dict[str, float]]:
        """Update gesture and get current modifiers.
        
        Args:
            current_time: Current time in seconds
        
        Returns:
            Dict of modifiers, or None if gesture complete
        """
        elapsed = current_time - self.start_time
        self.progress = elapsed / self.duration
        
        if self.progress >= 1.0:
            return None  # Gesture complete
        
        # Find surrounding keyframes
        prev_kf = self.keyframes[0]
        next_kf = self.keyframes[-1]
        
        for i in range(len(self.keyframes) - 1):
            if self.keyframes[i][0] <= self.progress < self.keyframes[i + 1][0]:
                prev_kf = self.keyframes[i]
                next_kf = self.keyframes[i + 1]
                break
        
        # Interpolate between keyframes
        kf_progress = (self.progress - prev_kf[0]) / (next_kf[0] - prev_kf[0])
        
        modifiers = {}
        for key in prev_kf[1]:
            if key in next_kf[1]:
                prev_val = prev_kf[1][key]
                next_val = next_kf[1][key]
                modifiers[key] = prev_val + (next_val - prev_val) * kf_progress
        
        return modifiers


class GestureSystem:
    """Manages gesture animations."""
    
    def __init__(self):
        self.current_gesture: Optional[Gesture] = None
        self.gesture_library = self._build_gesture_library()
    
    def _build_gesture_library(self) -> Dict[GestureType, Gesture]:
        """Build library of predefined gestures."""
        return {
            GestureType.NOD: Gesture(
                GestureType.NOD,
                duration=0.6,
                keyframes=[
                    (0.0, {"head_pitch": 0.0}),
                    (0.3, {"head_pitch": 15.0}),   # Down
                    (0.6, {"head_pitch": 0.0}),    # Back up
                ]
            ),
            
            GestureType.SHAKE: Gesture(
                GestureType.SHAKE,
                duration=0.8,
                keyframes=[
                    (0.0, {"head_yaw": 0.0}),
                    (0.2, {"head_yaw": -15.0}),    # Left
                    (0.4, {"head_yaw": 0.0}),      # Center
                    (0.6, {"head_yaw": 15.0}),     # Right
                    (0.8, {"head_yaw": 0.0}),      # Center
                ]
            ),
            
            GestureType.TILT: Gesture(
                GestureType.TILT,
                duration=0.5,
                keyframes=[
                    (0.0, {"head_roll": 0.0, "eyebrow_height": 0.0}),
                    (0.5, {"head_roll": 12.0, "eyebrow_height": 0.2}),
                ]
            ),
            
            GestureType.SHRUG: Gesture(
                GestureType.SHRUG,
                duration=0.7,
                keyframes=[
                    (0.0, {"shoulder_height": 0.0, "head_tilt": 0.0}),
                    (0.35, {"shoulder_height": 20.0, "head_tilt": 5.0}),
                    (0.7, {"shoulder_height": 0.0, "head_tilt": 0.0}),
                ]
            ),
            
            GestureType.LEAN_FORWARD: Gesture(
                GestureType.LEAN_FORWARD,
                duration=0.6,
                keyframes=[
                    (0.0, {"body_lean": 0.0, "eye_width": 0.0}),
                    (0.6, {"body_lean": 10.0, "eye_width": 0.15}),
                ]
            ),
            
            GestureType.LEAN_BACK: Gesture(
                GestureType.LEAN_BACK,
                duration=0.5,
                keyframes=[
                    (0.0, {"body_lean": 0.0, "eye_width": 0.0}),
                    (0.5, {"body_lean": -8.0, "eye_width": 0.2}),
                ]
            ),
            
            GestureType.CELEBRATE: Gesture(
                GestureType.CELEBRATE,
                duration=1.0,
                keyframes=[
                    (0.0, {"body_bounce": 0.0, "eye_sparkle": 0.0}),
                    (0.2, {"body_bounce": 15.0, "eye_sparkle": 1.0}),
                    (0.4, {"body_bounce": 0.0, "eye_sparkle": 1.0}),
                    (0.6, {"body_bounce": 10.0, "eye_sparkle": 0.8}),
                    (0.8, {"body_bounce": 0.0, "eye_sparkle": 0.5}),
                    (1.0, {"body_bounce": 0.0, "eye_sparkle": 0.0}),
                ]
            ),
            
            GestureType.THINK: Gesture(
                GestureType.THINK,
                duration=0.8,
                keyframes=[
                    (0.0, {"head_tilt": 0.0, "eye_squint": 0.0}),
                    (0.4, {"head_tilt": -8.0, "eye_squint": 0.15}),
                    (0.8, {"head_tilt": -8.0, "eye_squint": 0.15}),  # Hold
                ]
            ),
        }
    
    def trigger_gesture(self, gesture_type: GestureType):
        """Trigger a gesture animation.
        
        Args:
            gesture_type: Type of gesture to perform
        """
        if gesture_type in self.gesture_library:
            self.current_gesture = self.gesture_library[gesture_type]
            self.current_gesture.start(time.time())
    
    def update(self) -> Optional[Dict[str, float]]:
        """Update current gesture.
        
        Returns:
            Dict of modifiers, or None if no active gesture
        """
        if not self.current_gesture:
            return None
        
        modifiers = self.current_gesture.update(time.time())
        
        if modifiers is None:
            # Gesture complete
            self.current_gesture = None
        
        return modifiers
    
    def is_gesturing(self) -> bool:
        """Check if currently performing a gesture."""
        return self.current_gesture is not None
    
    def cancel_gesture(self):
        """Cancel current gesture."""
        self.current_gesture = None
    
    # Convenience methods
    def nod(self):
        """Perform a nod (yes)."""
        self.trigger_gesture(GestureType.NOD)
    
    def shake(self):
        """Perform a head shake (no)."""
        self.trigger_gesture(GestureType.SHAKE)
    
    def shrug(self):
        """Perform a shrug (don't know)."""
        self.trigger_gesture(GestureType.SHRUG)
    
    def celebrate(self):
        """Perform a celebration gesture."""
        self.trigger_gesture(GestureType.CELEBRATE)
    
    def think(self):
        """Perform a thinking gesture."""
        self.trigger_gesture(GestureType.THINK)


class ContextualGestureEngine:
    """Automatically triggers appropriate gestures based on context."""
    
    def __init__(self, gesture_system: GestureSystem):
        self.gesture_system = gesture_system
    
    def on_task_complete(self, success: bool):
        """React to task completion.
        
        Args:
            success: Whether task succeeded
        """
        if success:
            self.gesture_system.celebrate()
        else:
            self.gesture_system.shrug()
    
    def on_user_question(self):
        """React to user asking a question."""
        self.gesture_system.think()
    
    def on_affirmative_response(self):
        """React to saying yes/agreeing."""
        self.gesture_system.nod()
    
    def on_negative_response(self):
        """React to saying no/disagreeing."""
        self.gesture_system.shake()
    
    def on_uncertainty(self):
        """React to being uncertain."""
        self.gesture_system.shrug()
