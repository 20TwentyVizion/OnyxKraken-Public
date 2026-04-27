"""Eye tracking and attention system for more lifelike gaze."""
import time
import random
import math
from typing import Tuple, Optional


class EyeTracker:
    """Manages realistic eye movements including saccades and smooth pursuit."""
    
    def __init__(self):
        self.target_x = 0.0
        self.target_y = 0.0
        self.current_x = 0.0
        self.current_y = 0.0
        self.last_saccade = time.time()
        self.saccade_interval = random.uniform(2.0, 4.0)
        self.attention_mode = "idle"  # idle, tracking, focused
        self.blink_timer = 0.0
        self.blink_interval = random.uniform(3.0, 6.0)
    
    def update(
        self,
        dt: float,
        mouse_pos: Optional[Tuple[int, int]] = None,
        window_size: Tuple[int, int] = (800, 600)
    ) -> Tuple[float, float, bool]:
        """Update eye position with smooth tracking.
        
        Args:
            dt: Delta time in seconds
            mouse_pos: Optional mouse position (x, y)
            window_size: Window dimensions for normalization
        
        Returns:
            Tuple of (eye_x, eye_y, should_blink)
        """
        current_time = time.time()
        should_blink = False
        
        # Blink timing
        self.blink_timer += dt
        if self.blink_timer >= self.blink_interval:
            should_blink = True
            self.blink_timer = 0.0
            self.blink_interval = random.uniform(3.0, 6.0)
        
        # Saccade (quick eye movement) timing
        if current_time - self.last_saccade > self.saccade_interval:
            self._trigger_saccade(mouse_pos, window_size)
        
        # Smooth pursuit toward target
        speed = 5.0 if self.attention_mode == "tracking" else 3.0
        dx = self.target_x - self.current_x
        dy = self.target_y - self.current_y
        
        move_dist = speed * dt
        dist = math.sqrt(dx*dx + dy*dy)
        
        if dist > 0.01:
            # Move toward target
            self.current_x += (dx / dist) * min(move_dist, dist)
            self.current_y += (dy / dist) * min(move_dist, dist)
        
        # Add micro-movements (eye jitter)
        if self.attention_mode == "idle":
            jitter_x = random.uniform(-0.01, 0.01)
            jitter_y = random.uniform(-0.01, 0.01)
            self.current_x += jitter_x
            self.current_y += jitter_y
        
        # Clamp to reasonable range
        self.current_x = max(-0.4, min(0.4, self.current_x))
        self.current_y = max(-0.3, min(0.3, self.current_y))
        
        return self.current_x, self.current_y, should_blink
    
    def _trigger_saccade(
        self,
        mouse_pos: Optional[Tuple[int, int]],
        window_size: Tuple[int, int]
    ):
        """Quick eye movement to new target."""
        if mouse_pos and self.attention_mode == "tracking":
            # Look toward mouse (with some randomness)
            norm_x = (mouse_pos[0] / window_size[0]) - 0.5
            norm_y = (mouse_pos[1] / window_size[1]) - 0.5
            
            # Add slight randomness so it's not perfect tracking
            self.target_x = norm_x + random.uniform(-0.05, 0.05)
            self.target_y = norm_y + random.uniform(-0.05, 0.05)
        else:
            # Random look direction (idle wandering)
            self.target_x = random.uniform(-0.3, 0.3)
            self.target_y = random.uniform(-0.2, 0.2)
        
        self.last_saccade = time.time()
        self.saccade_interval = random.uniform(2.0, 4.0)
    
    def set_attention_mode(self, mode: str):
        """Set attention mode: idle, tracking, or focused.
        
        Args:
            mode: One of "idle", "tracking", "focused"
        """
        if mode in ("idle", "tracking", "focused"):
            self.attention_mode = mode
    
    def look_at(self, x: float, y: float):
        """Immediately look at a specific position.
        
        Args:
            x: Normalized x position (-0.5 to 0.5)
            y: Normalized y position (-0.5 to 0.5)
        """
        self.target_x = x
        self.target_y = y
        self.last_saccade = time.time()
    
    def look_at_center(self):
        """Look at center (straight ahead)."""
        self.look_at(0.0, 0.0)


class AttentionSystem:
    """Manages what the face is paying attention to."""
    
    def __init__(self):
        self.focus_target = None  # What we're looking at
        self.focus_duration = 0.0
        self.distraction_chance = 0.1  # 10% chance per second to get distracted
    
    def update(self, dt: float, eye_tracker: EyeTracker):
        """Update attention and eye tracking.
        
        Args:
            dt: Delta time in seconds
            eye_tracker: EyeTracker instance to control
        """
        self.focus_duration += dt
        
        # Chance to get distracted
        if random.random() < self.distraction_chance * dt:
            self._get_distracted(eye_tracker)
        
        # Return to center after long distraction
        if self.focus_duration > 5.0 and self.focus_target != "center":
            eye_tracker.look_at_center()
            self.focus_target = "center"
            self.focus_duration = 0.0
    
    def _get_distracted(self, eye_tracker: EyeTracker):
        """Look at something random."""
        directions = [
            (-0.3, -0.2),  # upper left
            (0.3, -0.2),   # upper right
            (-0.3, 0.2),   # lower left
            (0.3, 0.2),    # lower right
            (0.0, -0.3),   # up
            (0.0, 0.3),    # down
        ]
        
        x, y = random.choice(directions)
        eye_tracker.look_at(x, y)
        self.focus_target = "distracted"
        self.focus_duration = 0.0
    
    def focus_on_user(self, eye_tracker: EyeTracker):
        """Focus attention on user (center)."""
        eye_tracker.look_at_center()
        eye_tracker.set_attention_mode("focused")
        self.focus_target = "user"
        self.focus_duration = 0.0
    
    def track_mouse(self, eye_tracker: EyeTracker):
        """Start tracking mouse movements."""
        eye_tracker.set_attention_mode("tracking")
        self.focus_target = "mouse"
        self.focus_duration = 0.0
    
    def idle(self, eye_tracker: EyeTracker):
        """Return to idle wandering."""
        eye_tracker.set_attention_mode("idle")
        self.focus_target = None
        self.focus_duration = 0.0
