"""Test Timeline Editor — Demo the animation timeline."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tkinter as tk
from face.stage.timeline_editor import TimelineEditor
from face.stage.keyframe_system import (
    AnimationClip, AnimationTrack, InterpolationType,
    create_position_tracks, create_bone_tracks
)


def test_timeline_editor():
    """Test the timeline editor."""
    print("=" * 60)
    print("TIMELINE EDITOR TEST")
    print("=" * 60)
    
    # Create window
    root = tk.Tk()
    root.title("Timeline Editor Test")
    root.geometry("1400x600")
    root.configure(bg="#000000")
    
    # Create animation clip
    clip = AnimationClip("Test Animation", fps=30)
    
    # Add some tracks
    print("\n--- Creating Tracks ---")
    
    # Character position
    pos_tracks = create_position_tracks("Onyx")
    for track in pos_tracks:
        clip.add_track(track)
        print(f"  ✓ {track.name}")
    
    # Character arms
    left_arm_tracks = create_bone_tracks("Onyx", "left_arm")
    right_arm_tracks = create_bone_tracks("Onyx", "right_arm")
    for track in left_arm_tracks + right_arm_tracks:
        clip.add_track(track)
        print(f"  ✓ {track.name}")
    
    # Camera position
    cam_tracks = create_position_tracks("Camera")
    for track in cam_tracks:
        clip.add_track(track)
        print(f"  ✓ {track.name}")
    
    # Add some sample keyframes
    print("\n--- Adding Sample Keyframes ---")
    
    # Onyx moves from left to right
    onyx_x = clip.get_track("Onyx", "position.x")
    onyx_x.add_keyframe(0, -100, InterpolationType.LINEAR)
    onyx_x.add_keyframe(30, 0, InterpolationType.EASE_IN_OUT)
    onyx_x.add_keyframe(60, 100, InterpolationType.LINEAR)
    print("  ✓ Onyx position.x: 3 keyframes")
    
    # Onyx waves arms
    left_shoulder = clip.get_track("Onyx", "bones.left_arm.shoulder_angle")
    left_shoulder.add_keyframe(0, 0, InterpolationType.LINEAR)
    left_shoulder.add_keyframe(15, -45, InterpolationType.EASE_IN_OUT)
    left_shoulder.add_keyframe(30, 0, InterpolationType.EASE_IN_OUT)
    left_shoulder.add_keyframe(45, -45, InterpolationType.EASE_IN_OUT)
    left_shoulder.add_keyframe(60, 0, InterpolationType.LINEAR)
    print("  ✓ Left arm: 5 keyframes (wave)")
    
    # Camera zooms in
    cam_z = clip.get_track("Camera", "position.z")
    cam_z.add_keyframe(0, 0, InterpolationType.LINEAR)
    cam_z.add_keyframe(60, 50, InterpolationType.EASE_IN_OUT)
    print("  ✓ Camera zoom: 2 keyframes")
    
    print(f"\nTotal tracks: {len(clip.tracks)}")
    print(f"Duration: {clip.duration_frames} frames ({clip.get_duration_seconds():.1f}s)")
    
    # Create timeline editor
    timeline = TimelineEditor(root, clip, width=1400, height=500)
    timeline.pack(fill="both", expand=True)
    
    # Frame change callback
    def on_frame_changed(frame):
        values = clip.evaluate_at_frame(frame)
        print(f"\rFrame {frame}: {len(values)} values", end="", flush=True)
    
    timeline.on_frame_changed = on_frame_changed
    
    # Info panel
    info_text = (
        "TIMELINE EDITOR TEST\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Controls:\n"
        "  ▶ Play — Start playback\n"
        "  ⏸ Pause — Pause playback\n"
        "  ◀/▶ — Previous/Next frame\n"
        "  ◀◀/▶▶ — Jump to start/end\n"
        "  Click timeline — Scrub to frame\n"
        "  Mouse wheel — Zoom in/out\n"
        "  Loop — Toggle loop mode\n"
        "  + Keyframe — Add keyframe at current frame\n\n"
        "Features:\n"
        "  • Multiple animation tracks\n"
        "  • Keyframe visualization (diamonds)\n"
        "  • Playhead scrubbing\n"
        "  • Smooth interpolation\n"
        "  • Frame-accurate playback\n\n"
        "Press ESC to exit"
    )
    
    info_label = tk.Label(
        root,
        text=info_text,
        bg="#0a1520", fg="#88aacc",
        font=("Consolas", 8),
        justify="left",
        anchor="nw",
        padx=15, pady=10
    )
    info_window = tk.Label(root, bg="#0a1520")
    info_window.place(x=10, y=10)
    info_label.pack(in_=info_window)
    
    # Keyboard shortcuts
    root.bind("<space>", lambda e: timeline.toggle_play())
    root.bind("<Left>", lambda e: timeline.previous_frame())
    root.bind("<Right>", lambda e: timeline.next_frame())
    root.bind("<Home>", lambda e: timeline.jump_to_start())
    root.bind("<End>", lambda e: timeline.jump_to_end())
    root.bind("<Escape>", lambda e: root.quit())
    
    print("\n--- Timeline Ready ---")
    print("Press SPACE to play, ESC to exit")
    
    root.mainloop()


if __name__ == "__main__":
    try:
        test_timeline_editor()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
