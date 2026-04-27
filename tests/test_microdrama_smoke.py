"""Smoke tests for the microdrama pipeline components."""

import tempfile
import shutil
from pathlib import Path


def test_actor_registry():
    """Test ActorRegistry CRUD and persistence."""
    from apps.microdrama.actor_registry import ActorRegistry

    td = tempfile.mkdtemp()
    try:
        reg = ActorRegistry(td)

        # Create
        actor = reg.create_actor(
            name="Naia Chen",
            gender="female",
            body_type="slim",
            age_range="20s",
            ethnicity="East Asian",
            appearance="Sharp cheekbones, intense dark eyes, late 20s",
            hair_default="black straight hair",
            tags=["leading", "protagonist"],
        )
        assert actor.name == "Naia Chen"
        assert actor.gender == "female"
        print(f"  Created: {actor.name} (id={actor.actor_id})")

        # List
        actors = reg.list_actors()
        assert len(actors) == 1

        # Filter by tag
        assert len(reg.list_actors(tag="leading")) == 1
        assert len(reg.list_actors(tag="villain")) == 0

        # Update
        updated = reg.update_actor(actor.actor_id, notes="Test note")
        assert updated.notes == "Test note"

        # Reload from disk (new registry instance)
        reg2 = ActorRegistry(td)
        loaded = reg2.get_actor(actor.actor_id)
        assert loaded is not None
        assert loaded.name == "Naia Chen"
        assert loaded.tags == ["leading", "protagonist"]

        # Delete
        assert reg.delete_actor(actor.actor_id)
        assert len(reg.list_actors()) == 0

        print("  ActorRegistry: PASSED")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_casting_director():
    """Test CastingDirector inference logic."""
    from apps.microdrama.producer import CastingDirector
    from apps.microdrama.actor_registry import ActorRegistry

    td = tempfile.mkdtemp()
    try:
        reg = ActorRegistry(td)
        cd = CastingDirector(reg)

        chars = [
            {
                "name": "Naia Chen",
                "role": "protagonist",
                "archetype": "The Hidden Heir",
                "appearance": "Sharp cheekbones, calloused hands from second jobs, a thrift-store blazer",
            },
            {
                "name": "Victor Hale",
                "role": "antagonist",
                "archetype": "The Usurper",
                "appearance": "Silver hair, tailored suits, a smile that never reaches his eyes",
            },
            {
                "name": "Serena Okafor",
                "role": "supporting",
                "archetype": "The Insider",
                "appearance": "Tall, commanding, wears red like armor",
            },
        ]

        for ch in chars:
            gender = cd._infer_gender(ch)
            body = cd._infer_body_type(ch)
            age = cd._infer_age(ch)
            eth = cd._infer_ethnicity(ch)
            hair = cd._extract_hair(ch)
            print(f"  {ch['name']}: gender={gender}, body={body}, age={age}, eth={eth}, hair={hair!r}")

        # Victor should be male with silver hair
        assert cd._infer_gender(chars[1]) == "male"
        assert cd._infer_age(chars[1]) == "50s"  # silver hair → older
        assert "silver hair" in cd._extract_hair(chars[1]).lower()

        # Naia should be female
        assert cd._infer_gender(chars[0]) == "female"

        # Serena Okafor should detect ethnicity from surname
        assert cd._infer_ethnicity(chars[2]) == "Black"

        print("  CastingDirector: PASSED")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_visual_director():
    """Test VisualDirector moment extraction."""
    from apps.microdrama.prompt_engine import VisualDirector

    director = VisualDirector(moments_per_chapter=2)

    scene = {
        "title": "Fired in the Glass Room",
        "setting": "Apex Dynamics boardroom, 47th floor",
        "pov": "Naia Chen",
        "emotional_shift": "shame -> cold determination",
        "goal": "Naia tries to defend herself",
        "conflict": "Victor has fabricated evidence",
        "disaster": "She is escorted out in front of the entire floor",
    }

    moments = director.extract_moments_from_scene_data(1, scene)
    assert len(moments) == 2
    assert moments[0].emotional_beat == "shame"
    assert moments[1].emotional_beat == "determination"
    assert moments[0].camera_angle == "high_angle"  # shame → high angle
    assert moments[1].camera_angle == "low_angle"   # determination → low angle
    print(f"  Extracted {len(moments)} moments with correct emotion→camera mapping")

    # Test full story planning
    scenes = [
        {"chapter_number": 1, "title": "Ch1", "setting": "Boardroom", "pov": "Naia",
         "emotional_shift": "shame -> determination", "goal": "Defend", "conflict": "Evidence", "disaster": "Fired"},
        {"chapter_number": 2, "title": "Ch2", "setting": "Apartment", "pov": "Naia",
         "emotional_shift": "confusion -> fury", "goal": "Read envelope", "conflict": "Heritage", "disaster": "Text"},
    ]
    all_moments = director.plan_full_story(scenes, moments_per_chapter=3)
    assert len(all_moments) == 6  # 3 per chapter × 2 chapters
    print(f"  Full story plan: {len(all_moments)} moments across {len(scenes)} scenes")

    print("  VisualDirector: PASSED")


def test_prompt_engine():
    """Test StoryToPrompt generation across styles."""
    from apps.microdrama.prompt_engine import StoryToPrompt, VisualMoment

    moment = VisualMoment(
        chapter_number=1, moment_index=0,
        title="The Humiliation",
        description="Naia is escorted out by security",
        setting="Glass boardroom, 47th floor, city below",
        characters_present=["Naia Chen"],
        pov_character="Naia Chen",
        emotional_beat="shame",
        camera_angle="high_angle",
        lighting_mood="cold",
    )

    char_desc = {"Naia Chen": "East Asian woman, late 20s, sharp cheekbones, thrift-store blazer"}

    for style in ["photorealistic", "anime", "illustration", "painted"]:
        engine = StoryToPrompt(style=style)
        prompt = engine.build_scene_prompt(moment, character_descriptions=char_desc)
        assert len(prompt.positive_prompt) > 50
        assert len(prompt.negative_prompt) > 20
        assert prompt.style == style
        print(f"  {style}: {prompt.width}x{prompt.height}, prompt={len(prompt.positive_prompt)} chars")

    # Environment prompt
    engine = StoryToPrompt("photorealistic")
    env = engine.build_environment_prompt(
        setting="Glass-and-steel tower in Manhattan",
        atmosphere="Sleek, cold, menacing",
        time_of_day="dusk",
    )
    assert env.width == 1344  # wide landscape
    assert "no people" in env.positive_prompt
    print(f"  Environment: {env.width}x{env.height}")

    print("  PromptEngine: PASSED")


def test_command_router():
    """Test microdrama patterns in command router."""
    from core.command_router import route_command

    # Production commands
    r = route_command("make a microdrama")
    assert r.handled, "Should match 'make a microdrama'"
    assert "microdrama:produce" in r.response
    print(f"  'make a microdrama' → {r.response[:60]}")

    r = route_command("produce an illustrated micro-drama")
    assert r.handled, "Should match 'produce an illustrated micro-drama'"
    print(f"  'produce an illustrated micro-drama' → {r.response[:60]}")

    r = route_command("microdrama from secret_billionaire template")
    assert r.handled
    assert "secret_billionaire" in r.response
    print(f"  'microdrama from secret_billionaire' → {r.response[:60]}")

    # Actor commands
    r = route_command("create actor Naia Chen")
    assert r.handled
    assert "Naia Chen" in r.response
    print(f"  'create actor Naia Chen' → {r.response[:60]}")

    r = route_command("list actors")
    assert r.handled
    print(f"  'list actors' → {r.response[:60]}")

    # Shouldn't match random text
    r = route_command("what's the weather like?")
    assert not r.handled
    r = route_command("hello")
    assert not r.handled

    print("  CommandRouter: PASSED")


def test_producer_init():
    """Test MicroDramaProducer can be instantiated."""
    from apps.microdrama.producer import MicroDramaProducer

    td = tempfile.mkdtemp()
    try:
        producer = MicroDramaProducer(output_dir=td)
        assert producer.registry is not None
        assert producer.casting_director is not None
        assert producer.visual_director is not None
        assert producer.state is None  # no production started

        prods = producer.list_productions()
        assert prods == []

        print("  MicroDramaProducer: PASSED")
    finally:
        shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    print("=== Microdrama Pipeline Smoke Tests ===\n")

    tests = [
        ("ActorRegistry", test_actor_registry),
        ("CastingDirector", test_casting_director),
        ("VisualDirector", test_visual_director),
        ("PromptEngine", test_prompt_engine),
        ("CommandRouter", test_command_router),
        ("ProducerInit", test_producer_init),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            print(f"[{name}]")
            fn()
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()

    print(f"=== Results: {passed} passed, {failed} failed out of {len(tests)} ===")
    if failed:
        exit(1)
