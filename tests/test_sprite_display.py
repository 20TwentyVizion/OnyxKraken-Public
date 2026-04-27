"""Test sprite display in a simple tkinter window.

Run directly:  python tests/test_sprite_display.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    import tkinter as tk
    from face.stage.character_library import create_character_from_template
    from face.stage.character_rig import Vector2

    root = tk.Tk()
    root.title("Sprite Test")
    root.geometry("800x600")

    canvas = tk.Canvas(root, bg="#0a0e16", width=800, height=600)
    canvas.pack()

    rig, _, _ = create_character_from_template('onyx', use_sprites=True)
    rig.update_transforms()

    sprites = rig.get_all_sprites_sorted()
    print(f"Testing {len(sprites)} sprites")

    offset = Vector2(400, 300)
    for i, sprite in enumerate(sprites):
        print(f"\nSprite {i+1}: {sprite.socket.name}")
        print(f"  Image: {sprite.image is not None}")
        print(f"  World pos: ({sprite.world_position.x:.1f}, {sprite.world_position.y:.1f})")
        print(f"  World scale: ({sprite.world_scale.x:.2f}, {sprite.world_scale.y:.2f})")

        if sprite.image:
            try:
                photo = sprite.get_photo_image(1.0)
                if photo:
                    screen_x = sprite.world_position.x + offset.x
                    screen_y = sprite.world_position.y + offset.y
                    canvas.create_image(screen_x, screen_y, image=photo, anchor="center")
                    print(f"  ✓ Rendered at ({screen_x:.1f}, {screen_y:.1f})")

                    if not hasattr(canvas, '_images'):
                        canvas._images = []
                    canvas._images.append(photo)
                else:
                    print(f"  ✗ get_photo_image returned None")
            except Exception as e:
                print(f"  ✗ Error: {e}")

    for bone in rig.bones.values():
        x = bone.world_position.x + offset.x
        y = bone.world_position.y + offset.y
        canvas.create_oval(x-5, y-5, x+5, y+5, fill="#00d4ff", outline="#ffffff")
        canvas.create_text(x, y-15, text=bone.name, fill="#ffffff", font=("Arial", 8))

    print("\n" + "="*60)
    print("Window open - check if sprites are visible")
    print("="*60)

    root.mainloop()


if __name__ == "__main__":
    main()
