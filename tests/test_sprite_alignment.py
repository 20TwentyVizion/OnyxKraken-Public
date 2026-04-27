"""Test sprite alignment and FK clicking in Animation Studio."""

import tkinter as tk
from face.stage.animation_studio import AnimationStudio
from log import get_logger

_log = get_logger("test_sprite_alignment")

def test_sprite_alignment():
    """Test sprite alignment with skeleton."""
    _log.info("Testing sprite alignment...")
    
    # Create root window
    root = tk.Tk()
    root.withdraw()
    
    # Create animation studio
    studio = AnimationStudio(root)
    
    # Wait for initialization
    root.after(2000, lambda: check_alignment(studio, root))
    
    root.mainloop()

def check_alignment(studio, root):
    """Check sprite alignment after initialization."""
    _log.info("Checking sprite alignment...")
    
    # Check that character rig exists
    if not studio.character_rig:
        _log.error("No character rig found!")
        root.quit()
        return
    
    _log.info(f"Character rig: {studio.character_rig.name}")
    _log.info(f"Bones: {len(studio.character_rig.bones)}")
    _log.info(f"Sockets: {len(studio.character_rig.sockets)}")
    
    # Check sprites
    sprites = studio.character_rig.get_all_sprites_sorted()
    _log.info(f"Sprites: {len(sprites)}")
    
    for sprite in sprites:
        _log.info(f"  - {sprite.socket.name}: pivot={sprite.pivot.to_tuple()}, offset={sprite.offset.to_tuple()}")
    
    # Check renderer
    if studio.renderer:
        _log.info(f"Renderer: show_bones={studio.renderer.show_bones}")
        _log.info(f"Renderer: canvas_scale={studio.renderer.canvas_scale}")
    
    # Test FK mode
    _log.info(f"IK enabled: {studio.ik_enabled}")
    _log.info(f"Show skeleton: {studio.show_skeleton}")
    _log.info(f"Show ground plane: {studio.show_ground_plane}")
    
    # Check clickable joints
    _log.info("Testing FK clicking...")
    _log.info("Click on any joint in the preview window to test FK rotation")
    _log.info("The rotation gizmo (yellow circle) should appear when you click a joint")
    
    # Keep window open for manual testing
    _log.info("Window will stay open for manual testing. Close to exit.")

if __name__ == "__main__":
    test_sprite_alignment()
