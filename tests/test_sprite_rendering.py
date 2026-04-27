"""Test sprite rendering with transforms."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from face.stage.character_library import create_character_from_template

rig, _, _ = create_character_from_template('onyx', use_sprites=True)

print("Before update_transforms():")
sprites = rig.get_all_sprites_sorted()
for sprite in sprites[:3]:
    print(f"  {sprite.socket.name}: ({sprite.world_position.x:.1f}, {sprite.world_position.y:.1f})")

print("\nCalling update_transforms()...")
rig.update_transforms()

print("\nAfter update_transforms():")
for sprite in sprites[:3]:
    print(f"  {sprite.socket.name}: ({sprite.world_position.x:.1f}, {sprite.world_position.y:.1f})")

print(f"\n✓ Sprites have transforms: {any(s.world_position.x != 0 or s.world_position.y != 0 for s in sprites)}")
