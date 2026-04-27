"""Tests for the Scene Document system (.onyx-scene format).

Covers:
  - SceneDocument creation, serialization, deserialization
  - Clip CRUD (add, remove, move, duplicate, split, merge)
  - Validation
  - File I/O (save / load)
  - Backward compat: to_screenplay / from_screenplay
  - Animation library: register, save, load, capture, search
  - Scene compiler: compile_scene, compile_single_clip
"""

import json
import os
import tempfile
import pytest

# Ensure project root is on path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ===================================================================
# Scene Document tests
# ===================================================================

class TestSceneDocument:
    """Test SceneDocument dataclass and serialization."""

    def _make_doc(self):
        from face.stage.scene_document import (
            SceneDocument, CharacterDef, Clip, BeatDef, CameraDef,
            EnvironmentDef, AnimationDef,
        )
        doc = SceneDocument(
            title="Test Scene",
            description="A test scene for unit tests",
            fps=30,
            background="deep_space",
        )
        doc.characters.append(CharacterDef(
            id="onyx", template="onyx", display_name="Onyx",
            position={"x": -100, "y": 50}, scale=1.0,
        ))
        doc.characters.append(CharacterDef(
            id="xyno", template="xyno", display_name="Xyno",
            position={"x": 100, "y": 50}, scale=1.0,
        ))
        doc.environment.append(EnvironmentDef(
            kind="rect", name="Floor", x=0, y=-10,
            width=1200, height=200, fill="#050810",
        ))
        doc.clips.append(Clip(
            id="clip_001",
            name="Opening Shot",
            camera=CameraDef(shot_type="wide", focus="onyx",
                             transition="fade"),
            beats=[
                BeatDef(target="onyx", action="idle", duration=1.5),
            ],
        ))
        doc.clips.append(Clip(
            id="clip_002",
            name="Dialogue",
            camera=CameraDef(shot_type="medium", focus="onyx",
                             lens="portrait"),
            beats=[
                BeatDef(target="onyx", action="talk",
                        dialogue="Hello, world!", emotion="happy"),
                BeatDef(target="xyno", action="talk",
                        dialogue="Hey Onyx!", emotion="excited"),
            ],
        ))
        return doc

    def test_create_and_properties(self):
        doc = self._make_doc()
        assert doc.title == "Test Scene"
        assert doc.clip_count == 2
        assert len(doc.characters) == 2
        assert doc.character_ids == ["onyx", "xyno"]
        assert doc.total_duration > 0
        assert doc.total_frames > 0

    def test_serialization_roundtrip(self):
        doc = self._make_doc()
        data = doc.to_dict()
        assert data["version"] == "1.0"
        assert data["meta"]["title"] == "Test Scene"
        assert len(data["clips"]) == 2
        assert len(data["characters"]) == 2

        # Roundtrip
        from face.stage.scene_document import SceneDocument
        doc2 = SceneDocument.from_dict(data)
        assert doc2.title == doc.title
        assert doc2.clip_count == doc.clip_count
        assert len(doc2.characters) == len(doc.characters)
        assert doc2.clips[0].id == "clip_001"
        assert doc2.clips[1].beats[0].dialogue == "Hello, world!"

    def test_json_roundtrip(self):
        doc = self._make_doc()
        json_str = json.dumps(doc.to_dict(), indent=2)
        data = json.loads(json_str)
        from face.stage.scene_document import SceneDocument
        doc2 = SceneDocument.from_dict(data)
        assert doc2.title == doc.title
        assert doc2.total_duration == doc.total_duration

    def test_file_save_load(self):
        doc = self._make_doc()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.onyx-scene")
            saved_path = doc.save(path)
            assert os.path.exists(saved_path)
            # Verify it's valid JSON
            with open(saved_path) as f:
                data = json.load(f)
            assert data["meta"]["title"] == "Test Scene"
            # Load back
            from face.stage.scene_document import SceneDocument
            doc2 = SceneDocument.load(saved_path)
            assert doc2.title == doc.title
            assert doc2.clip_count == doc.clip_count

    def test_validation_clean(self):
        doc = self._make_doc()
        issues = doc.validate()
        assert len(issues) == 0

    def test_validation_unknown_character(self):
        from face.stage.scene_document import (
            SceneDocument, CharacterDef, Clip, BeatDef, CameraDef,
        )
        doc = SceneDocument(title="Bad Scene")
        doc.characters.append(CharacterDef(id="onyx"))
        doc.clips.append(Clip(
            name="Bad Clip",
            beats=[BeatDef(target="unknown_char", action="talk",
                          dialogue="Hello")],
        ))
        issues = doc.validate()
        assert any("unknown character" in i.lower() for i in issues)

    def test_validation_empty_clip(self):
        from face.stage.scene_document import (
            SceneDocument, CharacterDef, Clip,
        )
        doc = SceneDocument(title="Empty Clip Scene")
        doc.characters.append(CharacterDef(id="onyx"))
        doc.clips.append(Clip(name="Empty"))
        issues = doc.validate()
        assert any("no beats" in i.lower() for i in issues)

    def test_validation_unknown_animation_ref(self):
        from face.stage.scene_document import (
            SceneDocument, CharacterDef, Clip, BeatDef,
        )
        doc = SceneDocument(title="Bad Anim Ref")
        doc.characters.append(CharacterDef(id="onyx"))
        doc.clips.append(Clip(
            name="Anim Clip",
            animation_ref="nonexistent_anim",
            beats=[BeatDef(target="onyx", action="idle")],
        ))
        issues = doc.validate()
        assert any("unknown animation" in i.lower() for i in issues)


class TestClipOperations:
    """Test clip CRUD on SceneDocument."""

    def _make_doc(self):
        from face.stage.scene_document import (
            SceneDocument, CharacterDef, Clip, BeatDef, CameraDef,
        )
        doc = SceneDocument(title="Clip Ops Test")
        doc.characters.append(CharacterDef(id="onyx"))
        for i in range(3):
            doc.clips.append(Clip(
                id=f"clip_{i}",
                name=f"Clip {i}",
                beats=[BeatDef(target="onyx", action="idle", duration=1.0)],
            ))
        return doc

    def test_add_clip(self):
        from face.stage.scene_document import Clip, BeatDef
        doc = self._make_doc()
        new_clip = Clip(name="New", beats=[BeatDef(target="onyx")])
        doc.add_clip(new_clip)
        assert doc.clip_count == 4
        assert doc.clips[-1].name == "New"

    def test_add_clip_at_index(self):
        from face.stage.scene_document import Clip, BeatDef
        doc = self._make_doc()
        new_clip = Clip(name="Inserted", beats=[BeatDef(target="onyx")])
        doc.add_clip(new_clip, index=1)
        assert doc.clip_count == 4
        assert doc.clips[1].name == "Inserted"

    def test_remove_clip(self):
        doc = self._make_doc()
        assert doc.remove_clip("clip_1")
        assert doc.clip_count == 2
        assert doc.get_clip("clip_1") is None

    def test_remove_nonexistent(self):
        doc = self._make_doc()
        assert not doc.remove_clip("nonexistent")

    def test_move_clip(self):
        doc = self._make_doc()
        assert doc.move_clip("clip_0", 2)
        assert doc.clips[2].id == "clip_0"

    def test_duplicate_clip(self):
        doc = self._make_doc()
        dupe = doc.duplicate_clip("clip_1")
        assert dupe is not None
        assert dupe.id != "clip_1"
        assert dupe.name == "Clip 1 (copy)"
        assert doc.clip_count == 4
        assert doc.clips[2].id == dupe.id  # inserted after original

    def test_split_clip(self):
        from face.stage.scene_document import (
            SceneDocument, CharacterDef, Clip, BeatDef,
        )
        doc = SceneDocument(title="Split Test")
        doc.characters.append(CharacterDef(id="onyx"))
        doc.clips.append(Clip(
            id="multi",
            name="Multi-beat",
            beats=[
                BeatDef(target="onyx", action="talk", dialogue="Line 1"),
                BeatDef(target="onyx", action="idle", duration=1.0),
                BeatDef(target="onyx", action="talk", dialogue="Line 2"),
            ],
        ))
        new_clip = doc.split_clip("multi", 2)
        assert new_clip is not None
        assert len(doc.clips[0].beats) == 2
        assert len(new_clip.beats) == 1
        assert new_clip.beats[0].dialogue == "Line 2"
        assert doc.clip_count == 2

    def test_merge_clips(self):
        doc = self._make_doc()
        original_beats = len(doc.clips[0].beats) + len(doc.clips[1].beats)
        assert doc.merge_clips("clip_0", "clip_1")
        assert doc.clip_count == 2
        assert len(doc.clips[0].beats) == original_beats

    def test_summary(self):
        doc = self._make_doc()
        s = doc.summary()
        assert "Clip Ops Test" in s
        assert "Clip 0" in s


class TestBackwardCompat:
    """Test conversion to/from legacy Screenplay."""

    def test_to_screenplay(self):
        from face.stage.scene_document import (
            SceneDocument, CharacterDef, Clip, BeatDef, CameraDef,
        )
        doc = SceneDocument(title="Compat Test", background="void")
        doc.characters.append(CharacterDef(id="onyx"))
        doc.clips.append(Clip(
            camera=CameraDef(shot_type="closeup", focus="onyx"),
            beats=[
                BeatDef(target="onyx", action="talk",
                        dialogue="Testing compat", emotion="happy"),
            ],
        ))
        sp = doc.to_screenplay()
        assert sp.title == "Compat Test"
        assert len(sp.shots) == 1
        assert sp.shots[0].shot_type == "closeup"
        assert sp.shots[0].beats[0].dialogue == "Testing compat"

    def test_from_screenplay(self):
        from face.stage.scene_director import Beat, Shot, Screenplay
        from face.stage.scene_document import SceneDocument

        sp = Screenplay(
            title="Legacy Scene",
            shots=[
                Shot("wide", "Onyx", beats=[
                    Beat("Onyx", "talk", dialogue="From legacy"),
                ]),
                Shot("closeup", "Onyx", beats=[
                    Beat("Onyx", "idle", duration=1.0),
                ]),
            ],
            background="deep_space",
        )
        doc = SceneDocument.from_screenplay(sp, background="deep_space")
        assert doc.title == "Legacy Scene"
        assert doc.clip_count == 2
        assert doc.clips[0].beats[0].dialogue == "From legacy"
        assert doc.background == "deep_space"

        # Roundtrip: doc -> screenplay -> doc should preserve content
        sp2 = doc.to_screenplay()
        assert len(sp2.shots) == 2
        assert sp2.shots[0].beats[0].dialogue == "From legacy"


# ===================================================================
# Animation Library tests
# ===================================================================

class TestAnimationLibrary:
    """Test the animation library system."""

    def test_register_and_get(self):
        from face.stage.animation_library import AnimationLibrary
        from face.stage.scene_document import AnimationDef

        lib = AnimationLibrary()
        anim = AnimationDef(
            name="test_wave",
            fps=30,
            duration_frames=45,
            channels={"body.right_shoulder": [[0, 0], [15, 120], [45, 0]]},
            description="Test wave animation",
            tags=["test", "gesture"],
        )
        lib.register(anim)
        assert lib.get("test_wave") is not None
        assert lib.count() == 1
        assert "test_wave" in lib.list_all()
        assert "test_wave" in lib.list_user()

    def test_builtin_vs_user(self):
        from face.stage.animation_library import AnimationLibrary
        from face.stage.scene_document import AnimationDef

        lib = AnimationLibrary()
        lib.register(AnimationDef(name="builtin_one"), builtin=True)
        lib.register(AnimationDef(name="user_one"), builtin=False)
        assert lib.is_builtin("builtin_one")
        assert not lib.is_builtin("user_one")
        assert "builtin_one" in lib.list_builtins()
        assert "user_one" in lib.list_user()

    def test_search(self):
        from face.stage.animation_library import AnimationLibrary
        from face.stage.scene_document import AnimationDef

        lib = AnimationLibrary()
        lib.register(AnimationDef(name="happy_dance",
                                  description="A happy dance",
                                  tags=["dance", "happy"]))
        lib.register(AnimationDef(name="sad_walk",
                                  description="Walking sadly",
                                  tags=["walk", "sad"]))
        results = lib.search("happy")
        assert len(results) == 1
        assert results[0].name == "happy_dance"

        results = lib.search(tags=["walk"])
        assert len(results) == 1
        assert results[0].name == "sad_walk"

    def test_save_and_load_user(self):
        from face.stage.animation_library import AnimationLibrary
        from face.stage.scene_document import AnimationDef

        lib = AnimationLibrary()
        anim = AnimationDef(
            name="saved_anim",
            fps=30,
            duration_frames=60,
            channels={"body.left_shoulder": [[0, 0], [30, 90], [60, 0]]},
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = lib.save_animation(anim, directory=tmpdir)
            assert os.path.exists(path)

            # Load in a new library
            lib2 = AnimationLibrary()
            lib2.load_user_animations(directory=tmpdir)
            loaded = lib2.get("saved_anim")
            assert loaded is not None
            assert loaded.duration_frames == 60
            assert "body.left_shoulder" in loaded.channels

    def test_delete_user_not_builtin(self):
        from face.stage.animation_library import AnimationLibrary
        from face.stage.scene_document import AnimationDef

        lib = AnimationLibrary()
        lib.register(AnimationDef(name="builtin_x"), builtin=True)
        lib.register(AnimationDef(name="user_x"), builtin=False)
        assert not lib.delete_animation("builtin_x")  # can't delete builtin
        assert lib.delete_animation("user_x")
        assert lib.get("user_x") is None

    def test_inject_into_document(self):
        from face.stage.animation_library import AnimationLibrary
        from face.stage.scene_document import (
            SceneDocument, CharacterDef, Clip, BeatDef, AnimationDef,
        )

        lib = AnimationLibrary()
        lib.register(AnimationDef(
            name="my_wave",
            channels={"body.right_shoulder": [[0, 0], [30, 120]]},
        ))

        doc = SceneDocument(title="Inject Test")
        doc.characters.append(CharacterDef(id="onyx"))
        doc.clips.append(Clip(
            name="Wave Clip",
            animation_ref="my_wave",
            beats=[BeatDef(target="onyx", action="gesture")],
        ))

        assert "my_wave" not in doc.animation_library
        lib.inject_into_document(doc)
        assert "my_wave" in doc.animation_library

    def test_load_builtins(self):
        from face.stage.animation_library import AnimationLibrary
        lib = AnimationLibrary()
        lib.load_builtins()
        assert lib.count() > 0
        # Should have both pose_ and anim_ prefixed entries
        all_names = lib.list_all()
        has_pose = any(n.startswith("pose_") for n in all_names)
        has_anim = any(n.startswith("anim_") for n in all_names)
        assert has_pose, f"Expected pose_ entries in {all_names[:5]}"
        assert has_anim, f"Expected anim_ entries in {all_names[:5]}"


# ===================================================================
# Beat/Clip dataclass tests
# ===================================================================

class TestBeatDef:
    """Test BeatDef effective_duration and serialization."""

    def test_auto_duration_from_dialogue(self):
        from face.stage.scene_document import BeatDef
        beat = BeatDef(target="onyx", action="talk",
                       dialogue="This is a test line of dialogue.")
        d = beat.effective_duration()
        assert d >= 2.0
        # ~3.7s for 31 chars at 10 chars/sec + 0.6
        assert 2.0 < d < 10.0

    def test_explicit_duration(self):
        from face.stage.scene_document import BeatDef
        beat = BeatDef(target="onyx", action="idle", duration=2.5)
        assert beat.effective_duration() == 2.5

    def test_default_duration(self):
        from face.stage.scene_document import BeatDef
        beat = BeatDef(target="onyx", action="idle")
        assert beat.effective_duration() == 1.0

    def test_serialization_minimal(self):
        from face.stage.scene_document import BeatDef
        beat = BeatDef(target="onyx", action="idle")
        d = beat.to_dict()
        assert d == {"target": "onyx", "action": "idle"}

    def test_serialization_full(self):
        from face.stage.scene_document import BeatDef
        beat = BeatDef(
            target="onyx", action="talk", dialogue="Hi",
            emotion="happy", duration=3.0, pose="confident",
            body_anim="wave", face_hints={"mouth_curve": 0.5},
        )
        d = beat.to_dict()
        assert d["dialogue"] == "Hi"
        assert d["emotion"] == "happy"
        assert d["face_hints"]["mouth_curve"] == 0.5

        # Roundtrip
        beat2 = BeatDef.from_dict(d)
        assert beat2.dialogue == "Hi"
        assert beat2.face_hints["mouth_curve"] == 0.5


class TestQuickBuilders:
    """Test quick_monologue and quick_dialogue scene builders."""

    def test_quick_monologue(self):
        from face.stage.story_to_scene import quick_monologue
        doc = quick_monologue(
            "onyx",
            ["Hello world.", "This is a test.", "Goodbye."],
            title="Test Mono",
        )
        assert doc.title == "Test Mono"
        assert len(doc.characters) == 1
        assert doc.characters[0].id == "Onyx"
        assert doc.clip_count == 3
        assert doc.clips[0].beats[0].dialogue == "Hello world."
        assert doc.clips[2].beats[0].dialogue == "Goodbye."
        # Camera should vary
        shot_types = [c.camera.shot_type for c in doc.clips]
        assert len(set(shot_types)) > 1  # not all the same

    def test_quick_monologue_auto_title(self):
        from face.stage.story_to_scene import quick_monologue
        doc = quick_monologue("xyno", ["Starting something new today."])
        assert "Starting" in doc.title

    def test_quick_dialogue(self):
        from face.stage.story_to_scene import quick_dialogue
        doc = quick_dialogue(
            "onyx", "xyno",
            [
                ("onyx", "Hey there!"),
                ("xyno", "What's up?"),
                ("onyx", "Not much."),
            ],
        )
        assert len(doc.characters) == 2
        assert doc.characters[0].id == "Onyx"
        assert doc.characters[1].id == "Xyno"
        # 1 establishing + 3 exchange clips
        assert doc.clip_count == 4
        # First clip is establishing shot
        assert doc.clips[0].camera.shot_type == "wide"
        # Dialogue clips have talk beats
        assert doc.clips[1].beats[0].dialogue == "Hey there!"
        assert doc.clips[2].beats[0].dialogue == "What's up?"

    def test_quick_dialogue_positions(self):
        from face.stage.story_to_scene import quick_dialogue
        doc = quick_dialogue("onyx", "xyno", [("onyx", "Test")])
        # Characters should be positioned apart
        x_a = doc.characters[0].position["x"]
        x_b = doc.characters[1].position["x"]
        assert x_a < 0
        assert x_b > 0

    def test_quick_monologue_roundtrip(self):
        from face.stage.story_to_scene import quick_monologue
        doc = quick_monologue("onyx", ["Line one.", "Line two."])
        # Serialize and deserialize
        from face.stage.scene_document import SceneDocument
        data = doc.to_dict()
        doc2 = SceneDocument.from_dict(data)
        assert doc2.clip_count == 2
        assert doc2.clips[0].beats[0].dialogue == "Line one."

    def test_quick_dialogue_validate(self):
        from face.stage.story_to_scene import quick_dialogue
        doc = quick_dialogue(
            "onyx", "xyno",
            [("onyx", "Hello"), ("xyno", "Hi")],
        )
        issues = doc.validate()
        assert len(issues) == 0


class TestStoryToSceneHelpers:
    """Test story_to_scene internal helpers (no LLM needed)."""

    def test_extract_json_clean(self):
        from face.stage.story_to_scene import _extract_json
        data = _extract_json('{"key": "value"}')
        assert data == {"key": "value"}

    def test_extract_json_markdown_fences(self):
        from face.stage.story_to_scene import _extract_json
        raw = '```json\n{"key": "value"}\n```'
        data = _extract_json(raw)
        assert data == {"key": "value"}

    def test_extract_json_with_preamble(self):
        from face.stage.story_to_scene import _extract_json
        raw = 'Here is the scene:\n{"title": "test"}\nDone!'
        data = _extract_json(raw)
        assert data == {"title": "test"}

    def test_extract_json_invalid_raises(self):
        from face.stage.story_to_scene import _extract_json
        with pytest.raises(ValueError):
            _extract_json("not json at all")

    def test_post_process_defaults(self):
        from face.stage.story_to_scene import _post_process, StoryConfig
        from face.stage.scene_document import (
            SceneDocument, CharacterDef, Clip, BeatDef,
        )
        doc = SceneDocument(title="Test")
        doc.characters.append(CharacterDef(id="Onyx"))
        doc.clips.append(Clip(
            beats=[BeatDef(target="Onyx", action="talk", dialogue="Hi")],
        ))
        result = _post_process(doc, StoryConfig(
            default_background="neon_city", style="intense",
        ))
        assert result.background == "neon_city"
        assert result.style == "intense"

    def test_post_process_case_insensitive_char_match(self):
        from face.stage.story_to_scene import _post_process, StoryConfig
        from face.stage.scene_document import (
            SceneDocument, CharacterDef, Clip, BeatDef,
        )
        doc = SceneDocument(title="Case Test")
        doc.characters.append(CharacterDef(id="Onyx"))
        doc.clips.append(Clip(
            beats=[BeatDef(target="onyx", action="talk", dialogue="Hi")],
        ))
        result = _post_process(doc, StoryConfig())
        # Should fix case mismatch
        assert result.clips[0].beats[0].target == "Onyx"


class TestSampleSceneFile:
    """Test the sample .onyx-scene file loads correctly."""

    def test_load_the_awakening(self):
        import os
        from face.stage.scene_document import SceneDocument
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "scenes", "the_awakening.onyx-scene",
        )
        if not os.path.exists(path):
            pytest.skip("Sample scene file not found")
        doc = SceneDocument.load(path)
        assert doc.title == "The Awakening"
        assert len(doc.characters) == 1
        assert doc.characters[0].id == "Onyx"
        assert doc.clip_count == 9
        assert doc.background == "deep_space"
        issues = doc.validate()
        assert len(issues) == 0
        # Check total duration is reasonable
        assert doc.total_duration > 10.0
        assert doc.total_duration < 120.0


class TestSceneFileList:
    """Test scene file listing helpers."""

    def test_list_scene_files(self):
        from face.stage.scene_document import (
            SceneDocument, list_scene_files, CharacterDef, Clip, BeatDef,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test scene file
            doc = SceneDocument(title="List Test")
            doc.characters.append(CharacterDef(id="onyx"))
            doc.clips.append(Clip(beats=[BeatDef(target="onyx")]))
            doc.save(os.path.join(tmpdir, "test1.onyx-scene"))
            doc.title = "List Test 2"
            doc.save(os.path.join(tmpdir, "test2.onyx-scene"))

            files = list_scene_files(tmpdir)
            assert len(files) == 2

    def test_load_scene_meta(self):
        from face.stage.scene_document import (
            SceneDocument, load_scene_meta, CharacterDef, Clip, BeatDef,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            doc = SceneDocument(title="Meta Test", description="Testing")
            doc.characters.append(CharacterDef(id="onyx"))
            doc.clips.append(Clip(beats=[BeatDef(target="onyx")]))
            path = doc.save(os.path.join(tmpdir, "meta.onyx-scene"))
            meta = load_scene_meta(path)
            assert meta["title"] == "Meta Test"
            assert meta["clip_count"] == 1
            assert meta["character_count"] == 1
