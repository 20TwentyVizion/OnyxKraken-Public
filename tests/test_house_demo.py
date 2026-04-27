"""Regression test — locks the house demo structure so it never silently breaks.

Verifies:
  - Exact phase IDs, names, and order
  - Phase script content (key function calls present)
  - Narration text for each phase
  - Demo sequence step count and recording_steps
  - _assemble_steps produces correct narration order (hook → intro → core → outro)
  - No duplicate intro narrations
"""

import hashlib
import unittest


class TestHouseDemoPhases(unittest.TestCase):
    """Verify HOUSE_PHASES structure is exactly what we shipped."""

    def setUp(self):
        from addons.blender.house_demo import HOUSE_PHASES
        self.phases = HOUSE_PHASES

    def test_phase_count(self):
        self.assertEqual(len(self.phases), 11, "House demo must have exactly 11 phases")

    def test_phase_ids_in_order(self):
        expected = [
            "foundation", "walls", "openings", "floors",
            "living_room", "kitchen", "bedroom", "bathroom",
            "ceiling_roof", "exterior", "camera",
        ]
        actual = [p["id"] for p in self.phases]
        self.assertEqual(actual, expected)

    def test_phase_names(self):
        expected_names = [
            "Foundation & Ground",
            "Exterior & Interior Walls",
            "Doors & Windows",
            "Floor Materials",
            "Living Room Furniture",
            "Kitchen & Dining",
            "Bedroom",
            "Bathroom",
            "Ceiling & Roof",
            "Exterior Details",
            "Final Shot",
        ]
        actual = [p["name"] for p in self.phases]
        self.assertEqual(actual, expected_names)

    def test_every_phase_has_required_keys(self):
        required = {"id", "name", "narration", "script_fn", "wait"}
        for p in self.phases:
            with self.subTest(phase=p["id"]):
                self.assertTrue(required.issubset(p.keys()),
                                f"Phase {p['id']} missing keys: {required - p.keys()}")

    def test_every_phase_has_narration(self):
        for p in self.phases:
            with self.subTest(phase=p["id"]):
                self.assertIsInstance(p["narration"], str)
                self.assertGreater(len(p["narration"]), 10,
                                   f"Phase {p['id']} narration too short")

    def test_phase_wait_times(self):
        expected_waits = {
            "foundation": 3.0, "walls": 3.0, "openings": 3.0,
            "floors": 2.5, "living_room": 3.0, "kitchen": 3.0,
            "bedroom": 3.0, "bathroom": 2.0, "ceiling_roof": 3.0,
            "exterior": 2.5, "camera": 1.0,
        }
        for p in self.phases:
            with self.subTest(phase=p["id"]):
                self.assertEqual(p["wait"], expected_waits[p["id"]])


class TestHouseDemoScripts(unittest.TestCase):
    """Verify phase scripts contain required function calls."""

    def setUp(self):
        from addons.blender.house_demo import HOUSE_PHASES
        self.scripts = {p["id"]: p["script_fn"]() for p in HOUSE_PHASES}

    def test_foundation_has_ground_and_slab(self):
        s = self.scripts["foundation"]
        self.assertIn("create_floor", s)
        self.assertIn("create_box", s)
        self.assertIn("orbit_camera", s)
        self.assertIn("set_viewport_shading", s)

    def test_walls_has_wall_loop(self):
        s = self.scripts["walls"]
        self.assertIn("create_wall_loop", s)
        self.assertIn("create_wall", s)
        self.assertIn("mat_wall_exterior", s)

    def test_openings_has_boolean_cuts(self):
        s = self.scripts["openings"]
        self.assertIn("cut_door", s)
        self.assertIn("cut_window", s)
        self.assertIn("set_viewport_shading", s)

    def test_floors_has_materials(self):
        s = self.scripts["floors"]
        self.assertIn("mat_floor_wood", s)
        self.assertIn("mat_floor_tile", s)

    def test_living_room_hides_exterior_walls(self):
        s = self.scripts["living_room"]
        self.assertIn("hide_viewport = True", s)
        self.assertIn("ExtWall_0", s)
        self.assertIn("add_sofa", s)
        self.assertIn("add_table", s)
        self.assertIn("add_lamp", s)
        self.assertIn("add_bookshelf", s)

    def test_kitchen_has_furniture(self):
        s = self.scripts["kitchen"]
        self.assertIn("add_table", s)
        self.assertIn("add_chair", s)

    def test_bedroom_has_furniture(self):
        s = self.scripts["bedroom"]
        self.assertIn("add_bed", s)
        self.assertIn("add_lamp", s)

    def test_bathroom_has_fixtures(self):
        s = self.scripts["bathroom"]
        self.assertIn("Bathtub", s)
        self.assertIn("Sink", s)
        self.assertIn("Toilet", s)

    def test_ceiling_roof_shows_walls_again(self):
        s = self.scripts["ceiling_roof"]
        self.assertIn("hide_viewport = False", s)
        self.assertIn("create_roof_gable", s)
        self.assertIn("set_viewport_shading", s)

    def test_exterior_has_landscaping(self):
        s = self.scripts["exterior"]
        self.assertIn("FrontPath", s)
        self.assertIn("Hedge", s)

    def test_final_camera_uses_rendered_mode(self):
        s = self.scripts["camera"]
        self.assertIn('set_viewport_shading("RENDERED")', s)
        self.assertIn("setup_cycles", s)

    def test_all_interior_phases_have_orbit_camera(self):
        """Every phase must reposition the camera."""
        for pid, script in self.scripts.items():
            with self.subTest(phase=pid):
                self.assertIn("orbit_camera", script,
                              f"Phase {pid} missing orbit_camera call")


class TestHouseDemoSequence(unittest.TestCase):
    """Verify the DemoSequence produced by _seq_house."""

    def setUp(self):
        from face.demo_runner import _seq_house
        self.seq = _seq_house()

    def test_sequence_id(self):
        self.assertEqual(self.seq.id, "house")

    def test_sequence_has_recording_steps(self):
        self.assertIsNotNone(self.seq.recording_steps)
        self.assertGreater(len(self.seq.recording_steps), 0)

    def test_recording_steps_have_narration(self):
        narrate_steps = [s for s in self.seq.recording_steps if s.kind == "narrate"]
        self.assertGreaterEqual(len(narrate_steps), 2,
                                "Recording steps must have at least 2 narration lines (recap + close)")

    def test_core_steps_do_not_contain_intro_narration(self):
        """The core steps should NOT have an intro narrate — that comes from _assemble_steps."""
        for step in self.seq.steps:
            if step.kind == "narrate":
                self.assertNotIn("In this demo", step.text,
                                 "Core steps must not duplicate the intro narration")

    def test_core_steps_have_blender_build(self):
        build_steps = [s for s in self.seq.steps if s.kind == "blender_build"]
        self.assertEqual(len(build_steps), 11,
                         "Must have exactly 11 blender_build steps (one per phase)")


class TestHouseDemoNarrationOrder(unittest.TestCase):
    """Verify _assemble_steps produces the correct narration order for recording mode."""

    def test_recording_mode_order(self):
        """Hook → Intro → core (no intro narrate) → recording outro. No duplicates."""
        from face.demo_runner import _seq_house, DemoRunner

        seq = _seq_house()

        # Mock a runner in recording mode to call _assemble_steps
        runner = DemoRunner.__new__(DemoRunner)
        runner._mode = "recording"
        assembled = runner._assemble_steps(seq)

        narrations = [s.text for s in assembled if s.kind == "narrate"]

        # First narration should be the hook
        self.assertIn("house in Blender", narrations[0],
                      "First narration should be the hook")

        # Second should be the intro (mentions 'Onyx')
        self.assertIn("Onyx", narrations[1],
                      "Second narration should be the personality intro")

        # Should NOT have duplicate "In this demo" narrations
        intro_count = sum(1 for n in narrations if "In this demo" in n)
        self.assertLessEqual(intro_count, 1,
                             f"Found {intro_count} 'In this demo' narrations — should be at most 1")

        # Last narrations should be the recording outro (recap + close)
        self.assertIn("Thanks for watching", narrations[-1],
                      "Final narration should be the closing line")


class TestHouseDemoScriptHashes(unittest.TestCase):
    """Snapshot-based check: detect ANY change to phase scripts.

    If a phase script changes intentionally, update the hash here.
    This prevents accidental regressions.
    """

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.strip().encode()).hexdigest()[:16]

    def test_script_hashes_match_snapshot(self):
        from addons.blender.house_demo import HOUSE_PHASES

        # Generate current hashes — update these after intentional changes
        current = {p["id"]: self._hash(p["script_fn"]()) for p in HOUSE_PHASES}

        # Snapshot taken 2026-02-20 after all fixes verified
        # Update these ONLY after intentional, tested changes to phase scripts
        snapshot = {
            "foundation":   "0119445d9b97aacc",
            "walls":        "740dfcc9344c79f4",
            "openings":     "5c83129f3a449889",
            "floors":       "694349720677d37d",
            "living_room":  "086edbdf61adee8e",
            "kitchen":      "4944a0bf3c5ea689",
            "bedroom":      "d6250635e2ed5530",
            "bathroom":     "8b023a08a7133f2b",
            "ceiling_roof": "b408d0b66b5f5754",
            "exterior":     "0d036674270ec527",
            "camera":       "83f30fb12f267ed4",
        }

        for pid, expected_hash in snapshot.items():
            with self.subTest(phase=pid):
                self.assertEqual(current[pid], expected_hash,
                                 f"Phase '{pid}' script changed! If intentional, update the hash.")


if __name__ == "__main__":
    unittest.main()
