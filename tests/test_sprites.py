"""Test sprite loading."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from face.stage.character_library import create_character_from_template

rig, _, _ = create_character_from_template('onyx', use_sprites=True)
sprites = rig.get_all_sprites_sorted()

print(f"Total sprites: {len(sprites)}")
print()

for i, sprite in enumerate(sprites):
    print(f"{i+1}. Socket: {sprite.socket.name}")
    print(f"   Image path: {sprite.image_path}")
    print(f"   Image loaded: {sprite.image is not None}")
    print(f"   World pos: ({sprite.world_position.x:.1f}, {sprite.world_position.y:.1f})")
    print()
