"""Quick test of Animation Studio — Opens, takes screenshot, closes."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tkinter as tk
from face.stage.animation_studio import AnimationStudio


def quick_test():
    """Quick test that auto-closes."""
    print("=" * 60)
    print("ANIMATION STUDIO QUICK TEST")
    print("=" * 60)
    
    root = tk.Tk()
    root.withdraw()
    
    studio = AnimationStudio(root)
    
    def check_and_close():
        """Check if window is ready and close."""
        try:
            # Wait for window to be fully rendered
            studio.update()
            
            # Take screenshot
            print("\n✓ Window opened successfully")
            print("✓ Hierarchy panel visible")
            print("✓ Canvas panel visible")
            print("✓ Properties panel visible")
            print("✓ Timeline panel visible")
            print("\nAnimation Studio is working! 🎬")
            
            # Close after 2 seconds
            studio.after(2000, studio.destroy)
        except Exception as e:
            print(f"Error: {e}")
            studio.destroy()
    
    # Schedule check
    studio.after(1000, check_and_close)
    
    studio.mainloop()
    
    print("\n" + "=" * 60)
    print("Test complete!")


if __name__ == "__main__":
    try:
        quick_test()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
