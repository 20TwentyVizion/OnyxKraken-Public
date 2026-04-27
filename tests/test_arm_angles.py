"""Test arm angles to debug the confident pose."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tkinter as tk
from face.stage.character_body_v2 import RobotBody
import math

def test_arm_angles():
    root = tk.Tk()
    root.title("Arm Angle Test")
    root.geometry("800x600")
    root.configure(bg="#000000")
    
    canvas = tk.Canvas(root, bg="#0a0e16", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    
    # Create body
    colors = {"primary": "#00d4ff", "secondary": "#0088aa", "dark": "#004455"}
    body = RobotBody(canvas, colors)
    
    # Test different angles
    test_angles = [
        ("Neutral (0, 0)", 0, 0),
        ("Confident (-20, 0)", -20, 0),
        ("Out (45, 0)", 45, 0),
        ("Down (90, 0)", 90, 0),
    ]
    
    current_test = [0]
    
    def draw_test():
        canvas.delete("all")
        
        angle_name, shoulder, elbow = test_angles[current_test[0]]
        
        # Set angles
        body.left_shoulder_angle = shoulder
        body.left_elbow_angle = elbow
        body.right_shoulder_angle = -shoulder  # Mirror
        body.right_elbow_angle = -elbow
        
        # Draw body
        body.draw(400, 300, 1.0, "front")
        
        # Info
        info = f"{angle_name}\nLeft: shoulder={shoulder}°, elbow={elbow}°\nRight: shoulder={-shoulder}°, elbow={-elbow}°"
        canvas.create_text(
            400, 50,
            text=info,
            fill="#ffffff",
            font=("Consolas", 12),
            justify="center"
        )
        
        # Instructions
        canvas.create_text(
            400, 550,
            text="Press SPACE for next test, ESC to exit",
            fill="#88aacc",
            font=("Consolas", 10)
        )
    
    def next_test(event=None):
        current_test[0] = (current_test[0] + 1) % len(test_angles)
        draw_test()
    
    root.bind("<space>", next_test)
    root.bind("<Escape>", lambda e: root.quit())
    
    draw_test()
    root.mainloop()

if __name__ == "__main__":
    test_arm_angles()
