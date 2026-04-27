"""Tests for face.stage.production — full 2D animation production pipeline."""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from face.stage.production import (
    LayerCompositor, RenderLayer, LayerItem,
    SceneProp, PropLibrary,
    VideoExporter, ExportSettings,
    IntroOutroBuilder, IntroSequence, SequenceStep,
    SFXLibrary, SFXClip, SFXEvent,
    CreditsRoll, CreditEntry,
    EpisodeProject,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="onyx_test_prod_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_png(tmp_dir):
    """Create a tiny valid PNG file for testing."""
    from PIL import Image
    p = os.path.join(tmp_dir, "test_prop.png")
    img = Image.new("RGBA", (64, 48), (255, 0, 0, 200))
    img.save(p)
    return p


@pytest.fixture
def sample_wav(tmp_dir):
    """Create a tiny valid WAV file for testing."""
    import struct
    p = os.path.join(tmp_dir, "test_sfx.wav")
    # Minimal WAV header + 100 samples of silence
    samples = b'\x00\x00' * 100
    with open(p, 'wb') as f:
        # RIFF header
        data_size = len(samples)
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + data_size))
        f.write(b'WAVE')
        # fmt chunk
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))  # chunk size
        f.write(struct.pack('<HHIIHH', 1, 1, 22050, 44100, 2, 16))
        # data chunk
        f.write(b'data')
        f.write(struct.pack('<I', data_size))
        f.write(samples)
    return p


# ===================================================================
# LayerCompositor
# ===================================================================

class TestRenderLayer:
    def test_ordering(self):
        assert RenderLayer.BACKGROUND < RenderLayer.CHARACTERS
        assert RenderLayer.CHARACTERS < RenderLayer.EFFECTS
        assert RenderLayer.EFFECTS < RenderLayer.OVERLAY

    def test_all_layers_defined(self):
        assert len(RenderLayer) == 9


class TestLayerCompositor:
    def test_add_and_get(self):
        comp = LayerCompositor()
        item = comp.add("bg_image", RenderLayer.BACKGROUND, data="test")
        assert item.name == "bg_image"
        assert comp.get("bg_image") is item
        assert comp.get("nonexistent") is None

    def test_render_order(self):
        comp = LayerCompositor()
        comp.add("fg", RenderLayer.FOREGROUND, z_index=0)
        comp.add("bg", RenderLayer.BACKGROUND, z_index=0)
        comp.add("char", RenderLayer.CHARACTERS, z_index=0)
        names = [i.name for i in comp.items]
        assert names == ["bg", "char", "fg"]

    def test_z_index_within_layer(self):
        comp = LayerCompositor()
        comp.add("prop_a", RenderLayer.PROPS_BACK, z_index=5)
        comp.add("prop_b", RenderLayer.PROPS_BACK, z_index=1)
        comp.add("prop_c", RenderLayer.PROPS_BACK, z_index=10)
        items = comp.items_on_layer(RenderLayer.PROPS_BACK)
        names = [i.name for i in items]
        assert names == ["prop_b", "prop_a", "prop_c"]

    def test_remove(self):
        comp = LayerCompositor()
        comp.add("item1", RenderLayer.BACKGROUND)
        assert comp.remove("item1")
        assert not comp.remove("item1")  # already removed
        assert len(comp.items) == 0

    def test_move_to_layer(self):
        comp = LayerCompositor()
        comp.add("item1", RenderLayer.PROPS_BACK)
        comp.move_to_layer("item1", RenderLayer.PROPS_FRONT, z_index=5)
        item = comp.get("item1")
        assert item.layer == RenderLayer.PROPS_FRONT
        assert item.z_index == 5

    def test_set_z_index(self):
        comp = LayerCompositor()
        comp.add("item1", RenderLayer.PROPS_BACK, z_index=0)
        comp.set_z_index("item1", 99)
        assert comp.get("item1").z_index == 99

    def test_render_all_calls_callbacks(self):
        comp = LayerCompositor()
        calls = []
        comp.add("a", RenderLayer.BACKGROUND,
                 render_callback=lambda c, cam: calls.append("a"))
        comp.add("b", RenderLayer.FOREGROUND,
                 render_callback=lambda c, cam: calls.append("b"))
        comp.render_all(None)
        assert calls == ["a", "b"]

    def test_invisible_items_not_rendered(self):
        comp = LayerCompositor()
        calls = []
        item = comp.add("a", RenderLayer.BACKGROUND,
                        render_callback=lambda c, cam: calls.append("a"))
        item.visible = False
        comp.render_all(None)
        assert calls == []

    def test_clear(self):
        comp = LayerCompositor()
        comp.add("a", RenderLayer.BACKGROUND)
        comp.add("b", RenderLayer.FOREGROUND)
        comp.clear()
        assert len(comp.items) == 0

    def test_summary(self):
        comp = LayerCompositor()
        comp.add("sky", RenderLayer.BACKGROUND)
        comp.add("hero", RenderLayer.CHARACTERS)
        s = comp.summary()
        assert "sky" in s
        assert "hero" in s

    def test_to_dict(self):
        comp = LayerCompositor()
        comp.add("item1", RenderLayer.PROPS_BACK, z_index=3)
        d = comp.to_dict()
        assert len(d) == 1
        assert d[0]["name"] == "item1"
        assert d[0]["layer"] == "PROPS_BACK"
        assert d[0]["z_index"] == 3


# ===================================================================
# SceneProp
# ===================================================================

class TestSceneProp:
    def test_create(self):
        prop = SceneProp(name="donut", image_path="/test.png",
                         x=100, y=200, scale=0.5)
        assert prop.name == "donut"
        assert prop.scale == 0.5
        assert prop.layer == RenderLayer.PROPS_BACK

    def test_serialization(self):
        prop = SceneProp(name="taco", image_path="/taco.png",
                         x=50, y=75, scale=1.5, rotation=45,
                         flip_h=True, layer=RenderLayer.PROPS_FRONT,
                         tags=["food", "hero"])
        d = prop.to_dict()
        assert d["name"] == "taco"
        assert d["flip_h"] is True
        assert d["layer"] == "PROPS_FRONT"

        prop2 = SceneProp.from_dict(d)
        assert prop2.name == "taco"
        assert prop2.flip_h is True
        assert prop2.layer == RenderLayer.PROPS_FRONT
        assert prop2.tags == ["food", "hero"]

    def test_unknown_layer_fallback(self):
        d = {"name": "x", "image_path": "", "layer": "INVALID"}
        prop = SceneProp.from_dict(d)
        assert prop.layer == RenderLayer.PROPS_BACK


# ===================================================================
# PropLibrary
# ===================================================================

class TestPropLibrary:
    def test_scan_directory(self, sample_png, tmp_dir):
        lib = PropLibrary()
        lib.scan_directory(tmp_dir, "test_category")
        assert "test_category" in lib.categories()
        props = lib.list_props("test_category")
        assert "test_prop" in props

    def test_find(self, sample_png, tmp_dir):
        lib = PropLibrary()
        lib.scan_directory(tmp_dir, "food")
        results = lib.find("test")
        assert len(results) == 1
        assert results[0][0] == "food"

    def test_count(self, sample_png, tmp_dir):
        lib = PropLibrary()
        lib.scan_directory(tmp_dir, "cat1")
        assert lib.count() == 1

    def test_empty_directory(self, tmp_dir):
        lib = PropLibrary()
        empty_dir = os.path.join(tmp_dir, "empty")
        os.makedirs(empty_dir)
        lib.scan_directory(empty_dir)
        assert lib.count() == 0

    def test_all_props(self, sample_png, tmp_dir):
        lib = PropLibrary()
        lib.scan_directory(tmp_dir, "props")
        all_p = lib.all_props()
        assert "props" in all_p


# ===================================================================
# ExportSettings
# ===================================================================

class TestExportSettings:
    def test_defaults(self):
        s = ExportSettings()
        assert s.width == 1920
        assert s.height == 1080
        assert s.fps == 30
        assert s.codec == "libx264"

    def test_output_path(self, tmp_dir):
        s = ExportSettings(output_dir=tmp_dir, filename="test_video")
        p = s.output_path()
        assert p.endswith("test_video.mp4")
        assert tmp_dir in p

    def test_auto_filename(self, tmp_dir):
        s = ExportSettings(output_dir=tmp_dir)
        p = s.output_path()
        assert p.endswith(".mp4")
        assert "export_" in p


# ===================================================================
# VideoExporter
# ===================================================================

class TestVideoExporter:
    def test_ffmpeg_check(self):
        # Just verify it doesn't crash
        result = VideoExporter.ffmpeg_available()
        assert isinstance(result, bool)

    def test_cancel(self):
        exp = VideoExporter()
        exp.cancel()
        assert exp._cancel is True

    def test_progress_callback(self):
        calls = []
        exp = VideoExporter()
        exp.set_progress_callback(lambda f, t, m: calls.append((f, t, m)))
        exp._report_progress(5, 100, "test")
        assert calls == [(5, 100, "test")]


# ===================================================================
# IntroSequence
# ===================================================================

class TestSequenceStep:
    def test_serialization(self):
        step = SequenceStep(kind="title", text="HELLO",
                            duration_frames=60, font_size=48)
        d = step.to_dict()
        step2 = SequenceStep.from_dict(d)
        assert step2.text == "HELLO"
        assert step2.duration_frames == 60
        assert step2.font_size == 48


class TestIntroSequence:
    def test_compute_total_frames(self):
        seq = IntroSequence(name="Test")
        seq.steps = [
            SequenceStep(duration_frames=30),
            SequenceStep(duration_frames=60),
            SequenceStep(duration_frames=90),
        ]
        total = seq.compute_total_frames()
        assert total == 180
        assert seq.total_frames == 180

    def test_serialization(self):
        seq = IntroSequence(name="My Intro", music_path="/music.mp3")
        seq.steps = [SequenceStep(kind="title", text="SHOW", duration_frames=90)]
        seq.compute_total_frames()
        d = seq.to_dict()
        seq2 = IntroSequence.from_dict(d)
        assert seq2.name == "My Intro"
        assert len(seq2.steps) == 1
        assert seq2.total_frames == 90


class TestIntroOutroBuilder:
    def test_create_standard_intro(self):
        seq = IntroOutroBuilder.create_standard_intro(
            show_title="DONUT/TACO",
            episode_title="Pilot",
            creator="OnyxKraken")
        assert seq.name == "DONUT/TACO Intro"
        assert len(seq.steps) >= 3
        assert seq.total_frames > 0
        # Check show title step exists
        titles = [s.text for s in seq.steps if s.kind == "title"]
        assert "DONUT/TACO" in titles

    def test_create_standard_outro(self):
        seq = IntroOutroBuilder.create_standard_outro(
            show_title="DONUT/TACO",
            next_episode="Episode 2")
        assert "Outro" in seq.name
        assert seq.total_frames > 0

    def test_save_and_load(self, tmp_dir):
        seq = IntroOutroBuilder.create_standard_intro("TEST")
        path = os.path.join(tmp_dir, "intro.json")
        IntroOutroBuilder.save_sequence(seq, path)
        assert os.path.exists(path)

        loaded = IntroOutroBuilder.load_sequence(path)
        assert loaded.name == seq.name
        assert len(loaded.steps) == len(seq.steps)


# ===================================================================
# SFXLibrary
# ===================================================================

class TestSFXClip:
    def test_serialization(self):
        clip = SFXClip(name="whoosh", file_path="/sfx/whoosh.wav",
                       category="movement", tags=["fast", "air"])
        d = clip.to_dict()
        clip2 = SFXClip.from_dict(d)
        assert clip2.name == "whoosh"
        assert clip2.category == "movement"
        assert clip2.tags == ["fast", "air"]


class TestSFXEvent:
    def test_serialization(self):
        ev = SFXEvent(clip_name="whoosh", frame=42, volume=0.8, pan=-0.5)
        d = ev.to_dict()
        ev2 = SFXEvent.from_dict(d)
        assert ev2.frame == 42
        assert ev2.volume == 0.8
        assert ev2.pan == -0.5


class TestSFXLibrary:
    def test_add_clip(self):
        lib = SFXLibrary()
        lib.add_clip(SFXClip("ding", "/sfx/ding.wav", "ui"))
        assert lib.get_clip("ding") is not None

    def test_scan_directory(self, sample_wav, tmp_dir):
        lib = SFXLibrary()
        lib.scan_directory(tmp_dir)
        assert lib.get_clip("test_sfx") is not None

    def test_list_clips(self):
        lib = SFXLibrary()
        lib.add_clip(SFXClip("a", "/a.wav", "ui"))
        lib.add_clip(SFXClip("b", "/b.wav", "impact"))
        lib.add_clip(SFXClip("c", "/c.wav", "ui"))
        all_clips = lib.list_clips()
        assert len(all_clips) == 3
        ui_clips = lib.list_clips("ui")
        assert len(ui_clips) == 2

    def test_categories(self):
        lib = SFXLibrary()
        lib.add_clip(SFXClip("a", "/a.wav", "ui"))
        lib.add_clip(SFXClip("b", "/b.wav", "impact"))
        cats = lib.categories()
        assert "ui" in cats
        assert "impact" in cats

    def test_search(self):
        lib = SFXLibrary()
        lib.add_clip(SFXClip("whoosh_fast", "/a.wav", "movement",
                              tags=["air"]))
        lib.add_clip(SFXClip("ding", "/b.wav", "ui"))
        assert len(lib.search("whoosh")) == 1
        assert len(lib.search("air")) == 1
        assert len(lib.search("ui")) == 1

    def test_events(self):
        lib = SFXLibrary()
        lib.add_clip(SFXClip("ding", "/ding.wav"))
        ev = lib.add_event("ding", frame=10)
        assert ev is not None
        assert len(lib.events) == 1
        assert lib.events_at_frame(10) == [ev]
        assert lib.events_at_frame(11) == []

    def test_add_event_unknown_clip(self):
        lib = SFXLibrary()
        ev = lib.add_event("nonexistent", frame=5)
        assert ev is None

    def test_remove_event(self):
        lib = SFXLibrary()
        lib.add_clip(SFXClip("ding", "/ding.wav"))
        lib.add_event("ding", frame=10)
        lib.remove_event(0)
        assert len(lib.events) == 0

    def test_events_sorted(self):
        lib = SFXLibrary()
        lib.add_clip(SFXClip("a", "/a.wav"))
        lib.add_event("a", frame=30)
        lib.add_event("a", frame=10)
        lib.add_event("a", frame=20)
        frames = [e.frame for e in lib.events]
        assert frames == [10, 20, 30]

    def test_serialization(self):
        lib = SFXLibrary()
        lib.add_clip(SFXClip("boom", "/boom.wav", "impact"))
        lib.add_event("boom", frame=50, volume=0.9)
        d = lib.to_dict()

        lib2 = SFXLibrary.from_dict(d)
        assert lib2.get_clip("boom") is not None
        assert len(lib2.events) == 1
        assert lib2.events[0].frame == 50


# ===================================================================
# CreditsRoll
# ===================================================================

class TestCreditEntry:
    def test_serialization(self):
        e = CreditEntry(role="Director", name="Onyx", section="Crew")
        d = e.to_dict()
        e2 = CreditEntry.from_dict(d)
        assert e2.role == "Director"
        assert e2.section == "Crew"


class TestCreditsRoll:
    def test_add_entries(self):
        cr = CreditsRoll(show_title="DONUT/TACO")
        cr.add_section("CAST")
        cr.add_entry("Onyx", "Robot Host", "CAST")
        cr.add_entry("TacoBot", "Line Cook", "CAST")
        cr.add_section("CREW")
        cr.add_entry("Director", "The User")
        assert len(cr.entries) == 5

    def test_estimate_duration(self):
        cr = CreditsRoll()
        for i in range(20):
            cr.add_entry(f"Role {i}", f"Name {i}")
        frames = cr.estimate_duration_frames()
        assert frames > 0

    def test_serialization(self):
        cr = CreditsRoll(show_title="TEST", scroll_speed=2.0,
                         accent_color="#ff0000")
        cr.add_entry("Director", "User")
        d = cr.to_dict()
        cr2 = CreditsRoll.from_dict(d)
        assert cr2.show_title == "TEST"
        assert cr2.scroll_speed == 2.0
        assert cr2.accent_color == "#ff0000"
        assert len(cr2.entries) == 1


# ===================================================================
# EpisodeProject
# ===================================================================

class TestEpisodeProject:
    def test_code(self):
        ep = EpisodeProject(season=2, episode=5)
        assert ep.code == "S02E05"

    def test_project_dir(self):
        ep = EpisodeProject(series_name="donut_taco", season=1, episode=1)
        d = ep.project_dir
        assert "donut_taco" in str(d)
        assert "S01" in str(d)
        assert "E01" in str(d)

    def test_save_and_load(self, tmp_dir):
        ep = EpisodeProject(
            series_name="test_series",
            season=1, episode=1,
            episode_title="Pilot",
            episode_description="The first episode",
        )
        # Override projects dir for test
        import face.stage.production as prod
        orig_dir = prod._PROJECTS_DIR
        prod._PROJECTS_DIR = Path(tmp_dir) / "projects"
        try:
            ep.save()
            assert (ep.project_dir / "episode.json").exists()

            loaded = EpisodeProject.load(str(ep.project_dir))
            assert loaded.episode_title == "Pilot"
            assert loaded.code == "S01E01"
        finally:
            prod._PROJECTS_DIR = orig_dir

    def test_save_with_credits(self, tmp_dir):
        ep = EpisodeProject(
            series_name="test_series", season=1, episode=2,
            episode_title="Episode 2",
        )
        ep.credits = CreditsRoll(show_title="TEST")
        ep.credits.add_entry("Dir", "User")

        import face.stage.production as prod
        orig_dir = prod._PROJECTS_DIR
        prod._PROJECTS_DIR = Path(tmp_dir) / "projects"
        try:
            ep.save()
            loaded = EpisodeProject.load(str(ep.project_dir))
            assert loaded.credits is not None
            assert loaded.credits.show_title == "TEST"
        finally:
            prod._PROJECTS_DIR = orig_dir

    def test_list_series(self, tmp_dir):
        import face.stage.production as prod
        orig_dir = prod._PROJECTS_DIR
        prod._PROJECTS_DIR = Path(tmp_dir) / "projects"
        try:
            # Create two series
            ep1 = EpisodeProject(series_name="show_a", season=1, episode=1,
                                 episode_title="A1")
            ep1.save()
            ep2 = EpisodeProject(series_name="show_b", season=1, episode=1,
                                 episode_title="B1")
            ep2.save()

            series = EpisodeProject.list_series()
            assert "show_a" in series
            assert "show_b" in series
        finally:
            prod._PROJECTS_DIR = orig_dir

    def test_list_episodes(self, tmp_dir):
        import face.stage.production as prod
        orig_dir = prod._PROJECTS_DIR
        prod._PROJECTS_DIR = Path(tmp_dir) / "projects"
        try:
            for i in range(1, 4):
                ep = EpisodeProject(series_name="my_show", season=1,
                                    episode=i, episode_title=f"Ep {i}")
                ep.save()

            episodes = EpisodeProject.list_episodes("my_show")
            assert len(episodes) == 3
            assert episodes[0]["title"] == "Ep 1"
            assert episodes[2]["episode"] == 3
        finally:
            prod._PROJECTS_DIR = orig_dir

    def test_ensure_dirs(self, tmp_dir):
        import face.stage.production as prod
        orig_dir = prod._PROJECTS_DIR
        prod._PROJECTS_DIR = Path(tmp_dir) / "projects"
        try:
            ep = EpisodeProject(series_name="s", season=1, episode=1)
            d = ep.ensure_dirs()
            assert (d / "assets").is_dir()
            assert (d / "exports").is_dir()
        finally:
            prod._PROJECTS_DIR = orig_dir


# ===================================================================
# Integration: ShapeNode image rendering
# ===================================================================

class TestShapeNodeImage:
    def test_make_image(self, sample_png):
        from face.stage.engine.shapes import make_image
        s = make_image("Test", sample_png)
        assert s.shape_type == "image"
        assert s.image_path == sample_png
        assert s.width == 64
        assert s.height == 48

    def test_load_image(self, sample_png):
        from face.stage.engine.shapes import ShapeNode
        s = ShapeNode("test", "rectangle")
        s.load_image(sample_png)
        assert s.shape_type == "image"
        assert s.width == 64
        assert s._pil_image is not None

    def test_load_nonexistent(self):
        from face.stage.engine.shapes import ShapeNode
        s = ShapeNode("test", "rectangle")
        s.load_image("/nonexistent/path.png")
        assert s.shape_type == "rectangle"  # unchanged

    def test_make_image_custom_size(self, sample_png):
        from face.stage.engine.shapes import make_image
        s = make_image("Test", sample_png, width=200, height=150)
        assert s.width == 200
        assert s.height == 150
