"""Test complete Animation Studio with all features."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from face.stage.animation_studio import launch_animation_studio
from face.stage.character_library import get_template_list

if __name__ == "__main__":
    print("=" * 60)
    print("ANIMATION STUDIO - COMPLETE TEST")
    print("=" * 60)
    print()
    print("FEATURES TO TEST:")
    print()
    print("1. SAVE/LOAD SYSTEM:")
    print("   - File > New Animation")
    print("   - File > Save Animation / Save As")
    print("   - File > Open Animation")
    print()
    print("2. FK MODE (IK disabled):")
    print("   - Click on bone joints to select")
    print("   - Drag to rotate bones")
    print("   - Add keyframes with selected bone")
    print()
    print("3. IK MODE (View > Enable IK):")
    print("   - Drag colored IK targets:")
    print("     * Red = Left Hand")
    print("     * Green = Right Hand")
    print("     * Blue = Left Foot")
    print("     * Yellow = Right Foot")
    print()
    print("4. CAMERA CONTROLS:")
    print("   - Middle mouse drag = Pan camera")
    print("   - Mouse wheel = Zoom")
    print("   - View menu = Camera presets")
    print()
    print("5. GROUND PLANE:")
    print("   - View > Show Ground Plane (toggle)")
    print()
    print("6. CHARACTER LIBRARY (8 characters!):")
    print("   Character menu:")
    for key, name, desc in get_template_list():
        print(f"   - {name}: {desc}")
    print()
    print("7. TIMELINE:")
    print("   - Scrub timeline to see animation")
    print("   - Play/pause animation")
    print("   - Add keyframes at current frame")
    print()
    print("=" * 60)
    print()
    
    launch_animation_studio()
