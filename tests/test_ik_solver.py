"""Test IK Solver — Demonstrate inverse kinematics."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tkinter as tk
import math

from face.stage.character_rig import create_humanoid_rig, Vector2
from face.stage.rig_renderer import RigRenderer
from face.stage.ik_solver import IKSolver, create_simple_arm_ik, create_simple_leg_ik


class IKDemo(tk.Tk):
    """Interactive IK demonstration."""
    
    def __init__(self):
        super().__init__()
        
        self.title("IK Solver Demo - 2-Bone IK")
        self.geometry("1200x800")
        self.configure(bg="#0a0e16")
        
        # Create character rig
        self.rig = create_humanoid_rig("IK Demo")
        self.rig.root_bone.position = Vector2(0, 0)
        
        # Create IK solver
        self.ik_solver = IKSolver()
        
        # IK targets (will be controlled by mouse)
        self.left_hand_target = Vector2(-100, 100)
        self.right_hand_target = Vector2(100, 100)
        self.left_foot_target = Vector2(-50, 200)
        self.right_foot_target = Vector2(50, 200)
        
        # Setup IK chains
        self._setup_ik_chains()
        
        # Active target (which one is being dragged)
        self.active_target = None
        
        # Build UI
        self._build_ui()
        
        # Start animation loop
        self._animate()
    
    def _setup_ik_chains(self):
        """Setup IK chains for arms and legs."""
        # Left arm IK
        left_upper_arm = self.rig.bones.get("left_upper_arm")
        left_lower_arm = self.rig.bones.get("left_lower_arm")
        if left_upper_arm and left_lower_arm:
            left_arm_chain = create_simple_arm_ik(
                "left_arm",
                left_upper_arm,
                left_lower_arm,
                self.left_hand_target
            )
            self.ik_solver.add_chain(left_arm_chain)
        
        # Right arm IK
        right_upper_arm = self.rig.bones.get("right_upper_arm")
        right_lower_arm = self.rig.bones.get("right_lower_arm")
        if right_upper_arm and right_lower_arm:
            right_arm_chain = create_simple_arm_ik(
                "right_arm",
                right_upper_arm,
                right_lower_arm,
                self.right_hand_target
            )
            self.ik_solver.add_chain(right_arm_chain)
        
        # Left leg IK
        left_upper_leg = self.rig.bones.get("left_upper_leg")
        left_lower_leg = self.rig.bones.get("left_lower_leg")
        if left_upper_leg and left_lower_leg:
            left_leg_chain = create_simple_leg_ik(
                "left_leg",
                left_upper_leg,
                left_lower_leg,
                self.left_foot_target
            )
            self.ik_solver.add_chain(left_leg_chain)
        
        # Right leg IK
        right_upper_leg = self.rig.bones.get("right_upper_leg")
        right_lower_leg = self.rig.bones.get("right_lower_leg")
        if right_upper_leg and right_lower_leg:
            right_leg_chain = create_simple_leg_ik(
                "right_leg",
                right_upper_leg,
                right_lower_leg,
                self.right_foot_target
            )
            self.ik_solver.add_chain(right_leg_chain)
    
    def _build_ui(self):
        """Build the UI."""
        # Info panel
        info_frame = tk.Frame(self, bg="#0c1825", height=60)
        info_frame.pack(fill="x", side="top")
        info_frame.pack_propagate(False)
        
        tk.Label(
            info_frame,
            text="IK SOLVER DEMO - Drag the colored targets to move limbs",
            bg="#0c1825", fg="#00d4ff",
            font=("Consolas", 12, "bold")
        ).pack(pady=10)
        
        tk.Label(
            info_frame,
            text="Red = Left Hand | Green = Right Hand | Blue = Left Foot | Yellow = Right Foot",
            bg="#0c1825", fg="#88aacc",
            font=("Consolas", 9)
        ).pack()
        
        # Canvas
        self.canvas = tk.Canvas(
            self,
            bg="#0a0e16",
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)
        
        # Bind mouse events
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        
        # Keyboard shortcuts
        self.bind("<Escape>", lambda e: self.quit())
    
    def _animate(self):
        """Animation loop."""
        # Update IK chains with current targets
        for chain in self.ik_solver.chains:
            if chain.name == "left_arm":
                chain.target_position = self.left_hand_target
            elif chain.name == "right_arm":
                chain.target_position = self.right_hand_target
            elif chain.name == "left_leg":
                chain.target_position = self.left_foot_target
            elif chain.name == "right_leg":
                chain.target_position = self.right_foot_target
        
        # Solve IK
        self.ik_solver.solve_all()
        
        # Update transforms
        self.rig.update_transforms()
        
        # Render
        self._render()
        
        # Schedule next frame
        self.after(16, self._animate)  # ~60 FPS
    
    def _render(self):
        """Render the scene."""
        self.canvas.delete("all")
        
        # Get canvas center
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        offset = Vector2(width / 2, height / 2)
        
        # Render rig
        renderer = RigRenderer(self.canvas)
        renderer.show_bones = True
        renderer.canvas_scale = 1.0
        renderer.render(self.rig, offset)
        
        # Render IK targets
        self._render_target(self.left_hand_target, "#ff4466", "L Hand", offset)
        self._render_target(self.right_hand_target, "#44ff88", "R Hand", offset)
        self._render_target(self.left_foot_target, "#4488ff", "L Foot", offset)
        self._render_target(self.right_foot_target, "#ffff44", "R Foot", offset)
        
        # Draw center reference
        self.canvas.create_line(
            offset.x - 20, offset.y,
            offset.x + 20, offset.y,
            fill="#445566", width=1
        )
        self.canvas.create_line(
            offset.x, offset.y - 20,
            offset.x, offset.y + 20,
            fill="#445566", width=1
        )
    
    def _render_target(self, target: Vector2, color: str, label: str, offset: Vector2):
        """Render an IK target."""
        x = target.x + offset.x
        y = target.y + offset.y
        
        # Draw target circle
        size = 12
        self.canvas.create_oval(
            x - size, y - size,
            x + size, y + size,
            fill=color,
            outline="#ffffff",
            width=2,
            tags="ik_target"
        )
        
        # Draw crosshair
        self.canvas.create_line(
            x - size, y,
            x + size, y,
            fill="#ffffff", width=1
        )
        self.canvas.create_line(
            x, y - size,
            x, y + size,
            fill="#ffffff", width=1
        )
        
        # Draw label
        self.canvas.create_text(
            x, y - size - 10,
            text=label,
            fill=color,
            font=("Consolas", 8, "bold")
        )
    
    def _on_mouse_down(self, event):
        """Handle mouse down."""
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        offset = Vector2(width / 2, height / 2)
        
        # Convert to world space
        world_x = event.x - offset.x
        world_y = event.y - offset.y
        
        # Check which target is closest
        targets = [
            ("left_hand", self.left_hand_target),
            ("right_hand", self.right_hand_target),
            ("left_foot", self.left_foot_target),
            ("right_foot", self.right_foot_target)
        ]
        
        min_dist = 30  # Threshold for selection
        closest = None
        
        for name, target in targets:
            dist = math.sqrt((target.x - world_x) ** 2 + (target.y - world_y) ** 2)
            if dist < min_dist:
                min_dist = dist
                closest = name
        
        self.active_target = closest
    
    def _on_mouse_drag(self, event):
        """Handle mouse drag."""
        if not self.active_target:
            return
        
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        offset = Vector2(width / 2, height / 2)
        
        # Convert to world space
        world_x = event.x - offset.x
        world_y = event.y - offset.y
        
        # Update target position
        if self.active_target == "left_hand":
            self.left_hand_target.x = world_x
            self.left_hand_target.y = world_y
        elif self.active_target == "right_hand":
            self.right_hand_target.x = world_x
            self.right_hand_target.y = world_y
        elif self.active_target == "left_foot":
            self.left_foot_target.x = world_x
            self.left_foot_target.y = world_y
        elif self.active_target == "right_foot":
            self.right_foot_target.x = world_x
            self.right_foot_target.y = world_y
    
    def _on_mouse_up(self, event):
        """Handle mouse up."""
        self.active_target = None


def main():
    """Run the IK demo."""
    print("=" * 60)
    print("IK SOLVER DEMO")
    print("=" * 60)
    print("\nFeatures:")
    print("  ✓ 2-bone IK solver (analytical)")
    print("  ✓ Real-time IK solving")
    print("  ✓ Interactive target dragging")
    print("  ✓ Angle constraints")
    print("\nControls:")
    print("  • Drag colored targets to move limbs")
    print("  • Red = Left Hand")
    print("  • Green = Right Hand")
    print("  • Blue = Left Foot")
    print("  • Yellow = Right Foot")
    print("  • ESC = Exit")
    print("\n" + "=" * 60)
    
    demo = IKDemo()
    demo.mainloop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDemo closed by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
