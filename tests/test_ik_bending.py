"""Test IK Bending — Verify elbows/knees bend correctly."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tkinter as tk
import math

from face.stage.character_rig import Bone, Vector2
from face.stage.ik_solver import IKSolver, IKChain


class IKBendingTest(tk.Tk):
    """Test IK bending behavior."""
    
    def __init__(self):
        super().__init__()
        
        self.title("IK Bending Test - Watch the elbow bend!")
        self.geometry("800x600")
        self.configure(bg="#0a0e16")
        
        # Create simple 2-bone arm
        self.shoulder = Bone("shoulder", position=Vector2(0, 0), length=80)
        self.upper_arm = Bone("upper_arm", position=Vector2(0, 0), length=80, parent=self.shoulder)
        self.lower_arm = Bone("lower_arm", position=Vector2(0, 80), length=70, parent=self.upper_arm)
        
        # Create IK solver
        self.ik_solver = IKSolver()
        self.target = Vector2(100, 50)
        
        self.chain = IKChain(
            name="test_arm",
            bones=[self.upper_arm, self.lower_arm],
            target_position=self.target,
            min_angles=[-180, -150],
            max_angles=[180, 0]
        )
        self.ik_solver.add_chain(self.chain)
        
        # Animation state
        self.time = 0
        self.auto_animate = True
        
        # Build UI
        self._build_ui()
        
        # Start animation
        self._animate()
    
    def _build_ui(self):
        """Build UI."""
        # Info
        info = tk.Label(
            self,
            text="IK BENDING TEST - Watch the elbow bend as target moves close",
            bg="#0c1825", fg="#00d4ff",
            font=("Consolas", 11, "bold"),
            pady=10
        )
        info.pack(fill="x")
        
        # Canvas
        self.canvas = tk.Canvas(self, bg="#0a0e16", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Debug info
        self.debug_label = tk.Label(
            self,
            text="",
            bg="#0c1825", fg="#88aacc",
            font=("Consolas", 9),
            justify="left",
            anchor="w",
            padx=10, pady=5
        )
        self.debug_label.pack(fill="x")
        
        # Controls
        control_frame = tk.Frame(self, bg="#0c1825", height=40)
        control_frame.pack(fill="x")
        control_frame.pack_propagate(False)
        
        tk.Button(
            control_frame,
            text="Toggle Animation",
            command=self._toggle_animation,
            bg="#0c1825", fg="#00d4ff",
            font=("Consolas", 9),
            relief="flat", cursor="hand2"
        ).pack(side="left", padx=10)
        
        # Mouse control
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        
        self.bind("<Escape>", lambda e: self.quit())
    
    def _toggle_animation(self):
        """Toggle auto animation."""
        self.auto_animate = not self.auto_animate
    
    def _on_click(self, event):
        """Handle click."""
        self.auto_animate = False
        self._update_target_from_mouse(event)
    
    def _on_drag(self, event):
        """Handle drag."""
        self._update_target_from_mouse(event)
    
    def _update_target_from_mouse(self, event):
        """Update target from mouse position."""
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        
        # Convert to world space
        self.target.x = event.x - width / 2
        self.target.y = event.y - height / 2
        self.chain.target_position = self.target
    
    def _animate(self):
        """Animation loop."""
        if self.auto_animate:
            # Animate target in a circle, moving close and far
            self.time += 0.05
            
            # Vary distance from 30 to 150 (well within reach to fully extended)
            distance = 90 + 60 * math.sin(self.time * 0.5)
            angle = self.time
            
            self.target.x = distance * math.cos(angle)
            self.target.y = distance * math.sin(angle)
            self.chain.target_position = self.target
        
        # Solve IK
        self.shoulder.update_world_transform()
        self.ik_solver.solve_all()
        self.shoulder.update_world_transform()
        
        # Render
        self._render()
        
        # Schedule next frame
        self.after(16, self._animate)
    
    def _render(self):
        """Render the scene."""
        self.canvas.delete("all")
        
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        offset_x = width / 2
        offset_y = height / 2
        
        # Draw reference circle (max reach)
        max_reach = self.upper_arm.length + self.lower_arm.length
        self.canvas.create_oval(
            offset_x - max_reach, offset_y - max_reach,
            offset_x + max_reach, offset_y + max_reach,
            outline="#445566", width=1, dash=(5, 5)
        )
        
        # Draw shoulder (root)
        shoulder_x = self.shoulder.world_position.x + offset_x
        shoulder_y = self.shoulder.world_position.y + offset_y
        
        self.canvas.create_oval(
            shoulder_x - 8, shoulder_y - 8,
            shoulder_x + 8, shoulder_y + 8,
            fill="#ff4466", outline="#ffffff", width=2
        )
        self.canvas.create_text(
            shoulder_x, shoulder_y - 20,
            text="Shoulder", fill="#ff4466", font=("Consolas", 9, "bold")
        )
        
        # Draw upper arm
        upper_start = self.upper_arm.world_position
        upper_end = self.upper_arm.get_end_position()
        
        self.canvas.create_line(
            upper_start.x + offset_x, upper_start.y + offset_y,
            upper_end.x + offset_x, upper_end.y + offset_y,
            fill="#00d4ff", width=6
        )
        
        # Draw elbow
        elbow_x = upper_end.x + offset_x
        elbow_y = upper_end.y + offset_y
        
        self.canvas.create_oval(
            elbow_x - 6, elbow_y - 6,
            elbow_x + 6, elbow_y + 6,
            fill="#44ff88", outline="#ffffff", width=2
        )
        self.canvas.create_text(
            elbow_x, elbow_y - 15,
            text="Elbow", fill="#44ff88", font=("Consolas", 8, "bold")
        )
        
        # Draw lower arm
        lower_start = self.lower_arm.world_position
        lower_end = self.lower_arm.get_end_position()
        
        self.canvas.create_line(
            lower_start.x + offset_x, lower_start.y + offset_y,
            lower_end.x + offset_x, lower_end.y + offset_y,
            fill="#00d4ff", width=6
        )
        
        # Draw hand
        hand_x = lower_end.x + offset_x
        hand_y = lower_end.y + offset_y
        
        self.canvas.create_oval(
            hand_x - 5, hand_y - 5,
            hand_x + 5, hand_y + 5,
            fill="#ffff44", outline="#ffffff", width=2
        )
        self.canvas.create_text(
            hand_x, hand_y - 12,
            text="Hand", fill="#ffff44", font=("Consolas", 8, "bold")
        )
        
        # Draw target
        target_x = self.target.x + offset_x
        target_y = self.target.y + offset_y
        
        self.canvas.create_oval(
            target_x - 10, target_y - 10,
            target_x + 10, target_y + 10,
            fill="", outline="#ff00ff", width=3
        )
        self.canvas.create_line(
            target_x - 10, target_y,
            target_x + 10, target_y,
            fill="#ff00ff", width=2
        )
        self.canvas.create_line(
            target_x, target_y - 10,
            target_x, target_y + 10,
            fill="#ff00ff", width=2
        )
        self.canvas.create_text(
            target_x, target_y + 20,
            text="Target", fill="#ff00ff", font=("Consolas", 9, "bold")
        )
        
        # Draw line from hand to target
        self.canvas.create_line(
            hand_x, hand_y,
            target_x, target_y,
            fill="#ff00ff", width=1, dash=(3, 3)
        )
        
        # Update debug info
        dist_to_target = math.sqrt(
            (lower_end.x - self.target.x) ** 2 +
            (lower_end.y - self.target.y) ** 2
        )
        
        target_dist = math.sqrt(self.target.x ** 2 + self.target.y ** 2)
        
        elbow_angle = abs(self.lower_arm.rotation)
        
        debug_text = (
            f"Target Distance: {target_dist:.1f}px  |  "
            f"Max Reach: {max_reach:.1f}px  |  "
            f"Elbow Angle: {elbow_angle:.1f}°  |  "
            f"Error: {dist_to_target:.2f}px  |  "
            f"Upper Arm Rot: {self.upper_arm.rotation:.1f}°"
        )
        
        self.debug_label.config(text=debug_text)


def main():
    """Run the test."""
    print("=" * 60)
    print("IK BENDING TEST")
    print("=" * 60)
    print("\nThis test verifies that:")
    print("  ✓ Elbows bend when target is close")
    print("  ✓ Arms extend when target is far")
    print("  ✓ IK solves correctly at all distances")
    print("\nControls:")
    print("  • Watch the automatic animation")
    print("  • Click/drag to manually position target")
    print("  • Toggle Animation button to pause")
    print("  • ESC to exit")
    print("\nExpected behavior:")
    print("  • When target is close: Elbow bends (angle > 0°)")
    print("  • When target is far: Arm extends (angle ≈ 0°)")
    print("  • Hand should always reach target (error ≈ 0)")
    print("\n" + "=" * 60)
    
    test = IKBendingTest()
    test.mainloop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest closed by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
