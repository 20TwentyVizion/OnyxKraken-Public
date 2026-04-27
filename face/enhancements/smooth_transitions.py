"""Smooth emotion transitions with easing functions."""
import math
from typing import Dict, Any


def ease_in_out_cubic(t: float) -> float:
    """Smooth acceleration and deceleration (cubic easing).
    
    Args:
        t: Progress from 0.0 to 1.0
    
    Returns:
        Eased value from 0.0 to 1.0
    """
    t = max(0.0, min(1.0, t))  # Clamp to [0, 1]
    
    if t < 0.5:
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2


def ease_in_out_sine(t: float) -> float:
    """Smooth sinusoidal easing."""
    t = max(0.0, min(1.0, t))
    return -(math.cos(math.pi * t) - 1) / 2


def ease_out_elastic(t: float) -> float:
    """Elastic bounce effect (good for excited emotions)."""
    t = max(0.0, min(1.0, t))
    
    if t == 0 or t == 1:
        return t
    
    c4 = (2 * math.pi) / 3
    return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between two values.
    
    Args:
        a: Start value
        b: End value
        t: Progress from 0.0 to 1.0
    
    Returns:
        Interpolated value
    """
    return a + (b - a) * t


def interpolate_emotion(
    from_emotion: Dict[str, Any],
    to_emotion: Dict[str, Any],
    progress: float,
    easing_func=ease_in_out_cubic
) -> Dict[str, Any]:
    """Smoothly interpolate between two emotion states.
    
    Args:
        from_emotion: Starting emotion state dict
        to_emotion: Target emotion state dict
        progress: Transition progress (0.0 to 1.0)
        easing_func: Easing function to use
    
    Returns:
        Interpolated emotion state
    """
    t = easing_func(progress)
    
    result = {}
    
    # Interpolate all numeric values
    for key in from_emotion:
        if key in to_emotion:
            from_val = from_emotion[key]
            to_val = to_emotion[key]
            
            if isinstance(from_val, (int, float)) and isinstance(to_val, (int, float)):
                result[key] = lerp(from_val, to_val, t)
            else:
                # Non-numeric: use from_emotion until halfway, then switch
                result[key] = from_val if t < 0.5 else to_val
        else:
            result[key] = from_emotion[key]
    
    # Add any keys only in to_emotion
    for key in to_emotion:
        if key not in result:
            result[key] = to_emotion[key]
    
    return result


class EmotionTransitionManager:
    """Manages smooth transitions between emotions."""
    
    def __init__(self, transition_duration: float = 0.3):
        """Initialize transition manager.
        
        Args:
            transition_duration: Time in seconds for transitions
        """
        self.transition_duration = transition_duration
        self.current_emotion = None
        self.target_emotion = None
        self.transition_start_time = 0.0
        self.transition_progress = 1.0  # 1.0 = complete
    
    def set_emotion(self, emotion: Dict[str, Any], current_time: float):
        """Start transition to a new emotion.
        
        Args:
            emotion: Target emotion state
            current_time: Current time in seconds
        """
        if self.current_emotion is None:
            # First emotion, no transition
            self.current_emotion = emotion.copy()
            self.target_emotion = emotion.copy()
            self.transition_progress = 1.0
        else:
            # Start new transition
            self.target_emotion = emotion.copy()
            self.transition_start_time = current_time
            self.transition_progress = 0.0
    
    def update(self, current_time: float) -> Dict[str, Any]:
        """Update and get current interpolated emotion.
        
        Args:
            current_time: Current time in seconds
        
        Returns:
            Current emotion state (interpolated if transitioning)
        """
        if self.transition_progress >= 1.0:
            return self.current_emotion
        
        # Calculate progress
        elapsed = current_time - self.transition_start_time
        self.transition_progress = min(1.0, elapsed / self.transition_duration)
        
        # Interpolate
        interpolated = interpolate_emotion(
            self.current_emotion,
            self.target_emotion,
            self.transition_progress
        )
        
        # If complete, update current
        if self.transition_progress >= 1.0:
            self.current_emotion = self.target_emotion.copy()
        
        return interpolated
    
    def is_transitioning(self) -> bool:
        """Check if currently transitioning."""
        return self.transition_progress < 1.0
