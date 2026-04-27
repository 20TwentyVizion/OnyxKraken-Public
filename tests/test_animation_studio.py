"""Test Animation Studio — Launch the complete 2.5D animation editor."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from face.stage.animation_studio import launch_animation_studio


def main():
    """Launch the animation studio."""
    print("=" * 60)
    print("ONYX ANIMATION STUDIO - 2.5D ENGINE")
    print("=" * 60)
    print("\nLaunching animation studio...")
    print("\nFeatures:")
    print("  ✓ Character rig system with bones")
    print("  ✓ 2.5D camera (X, Y, Z + 180° flip)")
    print("  ✓ Timeline editor with keyframes")
    print("  ✓ Hierarchy panel (scene tree)")
    print("  ✓ Properties panel (object editing)")
    print("  ✓ Live preview canvas")
    print("\nControls:")
    print("  • Middle mouse drag — Pan camera")
    print("  • Mouse wheel — Zoom camera")
    print("  • Timeline controls — Play/pause animation")
    print("  • Hierarchy — Select objects")
    print("  • Properties — Edit selected object")
    print("\nMenu:")
    print("  • File → Export Video/Images")
    print("  • Edit → Add/Delete Keyframes")
    print("  • View → Camera presets")
    print("\n" + "=" * 60)
    
    try:
        launch_animation_studio()
    except KeyboardInterrupt:
        print("\n\nStudio closed by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
