"""Face enhancement modules for improved animation and interaction."""

from .smooth_transitions import ease_in_out_cubic, interpolate_emotion
from .eye_tracking import EyeTracker
from .micro_expressions import MicroExpressionEngine
from .gesture_system import GestureSystem

__all__ = [
    "ease_in_out_cubic",
    "interpolate_emotion",
    "EyeTracker",
    "MicroExpressionEngine",
    "GestureSystem",
]
