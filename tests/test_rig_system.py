"""Test the new character rig system."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tkinter as tk
from face.stage.character_rig import create_humanoid_rig, Vector2
from face.stage.rig_renderer import RigRenderer


def test_rig_system():
    """Test the rig system with visualization."""
    print("=" * 60)
    print("CHARACTER RIG SYSTEM TEST")
    print("=" * 60)
    
    # Create window
    root = tk.Tk()
    root.title("Character Rig Test")
    root.geometry("800x600")
    root.configure(bg="#000000")
    
    # Create canvas
    canvas = tk.Canvas(root, bg="#0a0e16", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    
    # Create humanoid rig
    print("\n--- Creating Humanoid Rig ---")
    rig = create_humanoid_rig("Test Character")
    
    print(f"Bones: {len(rig.bones)}")
    for bone_name in rig.bones:
        print(f"  • {bone_name}")
    
    print(f"\nSockets: {len(rig.sockets)}")
    for socket_name in rig.sockets:
        print(f"  • {socket_name}")
    
    # Create renderer
    renderer = RigRenderer(canvas)
    renderer.show_bones = True  # Show skeleton
    renderer.show_sockets = True  # Show sockets
    renderer.canvas_scale = 1.0
    
    # Animation state
    animation_state = {"angle": 0.0}
    
    def animate():
        """Animate the rig."""
        # Clear previous frame
        renderer.clear()
        
        # Animate some bones
        animation_state["angle"] += 2.0
        if animation_state["angle"] > 360:
            animation_state["angle"] -= 360
        
        # Rotate upper arms (shoulders stay fixed)
        if "left_upper_arm" in rig.bones:
            rig.bones["left_upper_arm"].rotation = animation_state["angle"] * 0.5
        if "right_upper_arm" in rig.bones:
            rig.bones["right_upper_arm"].rotation = -animation_state["angle"] * 0.5
        
        # Bend lower arms (elbows)
        if "left_lower_arm" in rig.bones:
            rig.bones["left_lower_arm"].rotation = 30 + math.sin(math.radians(animation_state["angle"])) * 20
        if "right_lower_arm" in rig.bones:
            rig.bones["right_lower_arm"].rotation = 30 + math.sin(math.radians(animation_state["angle"])) * 20
        
        # Render rig
        offset = Vector2(400, 300)  # Center of screen
        renderer.render(rig, offset)
        
        # Schedule next frame
        root.after(33, animate)  # ~30 FPS
    
    # Info text
    info_text = (
        "CHARACTER RIG SYSTEM TEST\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Cyan lines = Bones\n"
        "White circles = Joints\n"
        "Magenta circles = Sockets (image attachment points)\n"
        "\n"
        "The arms are animating to show the hierarchy working.\n"
        "When a parent bone rotates, all children follow automatically!\n"
        "\n"
        "Press ESC to exit"
    )
    
    info_label = tk.Label(
        canvas,
        text=info_text,
        bg="#0a1520", fg="#88aacc",
        font=("Consolas", 9),
        justify="left",
        anchor="nw",
        padx=15, pady=10
    )
    canvas.create_window(10, 10, window=info_label, anchor="nw")
    
    # Keyboard shortcuts
    root.bind("<Escape>", lambda e: root.quit())
    
    print("\n--- Test Running ---")
    print("Watch the arms rotate!")
    print("Press ESC to exit")
    
    # Start animation
    animate()
    
    root.mainloop()


if __name__ == "__main__":
    try:
        test_rig_system()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
