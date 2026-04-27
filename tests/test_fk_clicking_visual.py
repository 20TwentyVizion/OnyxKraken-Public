"""Visual test for FK clicking and sprite alignment."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tkinter as tk
from face.stage.character_library import create_onyx_character
from face.stage.rig_renderer import RigRenderer
from face.stage.camera_2d5 import Camera2D5
from face.stage.character_rig import Vector2
import math
from log import get_logger

_log = get_logger("test_fk_visual")


class FKClickTest(tk.Tk):
    """Simple test window for FK clicking."""
    
    def __init__(self):
        super().__init__()
        
        self.title("FK Clicking Test - Click joints to rotate")
        self.geometry("800x600")
        self.configure(bg="#0a0e16")
        
        # Create canvas
        self.canvas = tk.Canvas(self, bg="#0a0e16", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Create character
        self.visual_character = create_onyx_character("Onyx")
        self.rig = self.visual_character.rig
        self.rig.root_bone.position.x = 0
        self.rig.root_bone.position.y = 0
        self.rig.update_transforms()
        
        # Create camera
        self.camera = Camera2D5(800, 600)
        
        # Create renderer
        self.renderer = RigRenderer(self.canvas)
        self.renderer.show_bones = True
        self.renderer.canvas_scale = 1.0
        
        # FK state
        self.selected_bone = None
        self.dragging = False
        self.drag_start_angle = 0
        
        # Bind mouse events
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        # Instructions
        self.info_label = tk.Label(
            self,
            text="Click on any joint (cyan dot) to select. Drag to rotate. Selected joint shows yellow gizmo.",
            bg="#0c1825", fg="#00d4ff",
            font=("Consolas", 10),
            pady=10
        )
        self.info_label.pack(side="bottom", fill="x")
        
        # Start render loop
        self.render_loop()
        
        _log.info("FK Click Test initialized")
    
    def render_loop(self):
        """Render loop."""
        self.canvas.delete("all")
        
        # Update transforms
        self.rig.update_transforms()
        
        # Get offset
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        offset = Vector2(canvas_width / 2, canvas_height / 2)
        
        # Draw ground plane
        ground_y = canvas_height / 2 + 200
        self.canvas.create_line(0, ground_y, canvas_width, ground_y, fill="#445566", width=2)
        
        # Render character
        self.renderer.render(self.rig, offset)
        
        # Draw clickable joints
        self.draw_clickable_joints(offset)
        
        # Draw rotation gizmo if bone selected
        if self.selected_bone:
            self.draw_rotation_gizmo(offset)
        
        # Schedule next frame
        self.after(33, self.render_loop)
    
    def draw_clickable_joints(self, offset):
        """Draw clickable joint markers."""
        for bone in self.rig.bones.values():
            bone_pos = bone.world_position
            screen_x = bone_pos.x + offset.x
            screen_y = bone_pos.y + offset.y
            
            is_selected = bone == self.selected_bone
            
            # Draw clickable circle
            self.canvas.create_oval(
                screen_x - 15, screen_y - 15,
                screen_x + 15, screen_y + 15,
                fill="#00d4ff" if is_selected else "",
                outline="#00d4ff" if is_selected else "#445566",
                width=3 if is_selected else 1,
                tags="joint"
            )
            
            # Draw center dot
            if not is_selected:
                self.canvas.create_oval(
                    screen_x - 3, screen_y - 3,
                    screen_x + 3, screen_y + 3,
                    fill="#00d4ff",
                    outline="",
                    tags="joint"
                )
    
    def draw_rotation_gizmo(self, offset):
        """Draw rotation gizmo for selected bone."""
        bone_pos = self.selected_bone.world_position
        screen_x = bone_pos.x + offset.x
        screen_y = bone_pos.y + offset.y
        
        # Draw rotation circle
        gizmo_radius = 40
        self.canvas.create_oval(
            screen_x - gizmo_radius, screen_y - gizmo_radius,
            screen_x + gizmo_radius, screen_y + gizmo_radius,
            outline="#ffff00",
            width=3,
            tags="gizmo"
        )
        
        # Draw rotation handle
        angle_rad = math.radians(self.selected_bone.rotation)
        handle_x = screen_x + math.cos(angle_rad) * gizmo_radius
        handle_y = screen_y + math.sin(angle_rad) * gizmo_radius
        
        self.canvas.create_line(
            screen_x, screen_y,
            handle_x, handle_y,
            fill="#ffff00",
            width=3,
            tags="gizmo"
        )
        
        # Draw handle endpoint
        self.canvas.create_oval(
            handle_x - 8, handle_y - 8,
            handle_x + 8, handle_y + 8,
            fill="#ffff00",
            outline="#ffffff",
            width=2,
            tags="gizmo"
        )
        
        # Draw label
        self.canvas.create_text(
            screen_x, screen_y - gizmo_radius - 15,
            text=f"{self.selected_bone.name} ({int(self.selected_bone.rotation)}°)",
            fill="#ffff00",
            font=("Consolas", 10, "bold"),
            tags="gizmo"
        )
    
    def on_click(self, event):
        """Handle mouse click."""
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        offset_x = canvas_width / 2
        offset_y = canvas_height / 2
        
        world_x = event.x - offset_x
        world_y = event.y - offset_y
        
        _log.info(f"Click at screen ({event.x}, {event.y}) -> world ({world_x:.1f}, {world_y:.1f})")
        
        # Check all bones
        for bone in self.rig.bones.values():
            joint_pos = bone.world_position
            dist = math.sqrt((joint_pos.x - world_x) ** 2 + (joint_pos.y - world_y) ** 2)
            
            if dist < 15:
                self.selected_bone = bone
                self.dragging = True
                
                # Calculate initial angle
                dx = world_x - joint_pos.x
                dy = world_y - joint_pos.y
                self.drag_start_angle = math.degrees(math.atan2(dy, dx)) - bone.rotation
                
                _log.info(f"Selected bone: {bone.name} at rotation {bone.rotation:.1f}°")
                return
        
        # No bone selected
        self.selected_bone = None
        _log.info("No bone selected")
    
    def on_drag(self, event):
        """Handle mouse drag."""
        if not self.dragging or not self.selected_bone:
            return
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        offset_x = canvas_width / 2
        offset_y = canvas_height / 2
        
        world_x = event.x - offset_x
        world_y = event.y - offset_y
        
        # Calculate angle
        joint_pos = self.selected_bone.world_position
        dx = world_x - joint_pos.x
        dy = world_y - joint_pos.y
        
        angle = math.degrees(math.atan2(dy, dx))
        new_rotation = angle - self.drag_start_angle
        
        # Apply rotation
        self.selected_bone.rotation = new_rotation
        
        _log.debug(f"Rotating {self.selected_bone.name} to {new_rotation:.1f}°")
    
    def on_release(self, event):
        """Handle mouse release."""
        if self.dragging:
            _log.info(f"Released bone: {self.selected_bone.name if self.selected_bone else 'None'}")
            self.dragging = False


if __name__ == "__main__":
    _log.info("Starting FK Click Test...")
    app = FKClickTest()
    app.mainloop()
