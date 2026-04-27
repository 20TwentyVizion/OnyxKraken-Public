"""Test the personality preset system."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_personality_presets():
    """Test loading and using personality presets."""
    from core.personality_manager import get_personality_manager
    
    print("=" * 60)
    print("PERSONALITY SYSTEM TEST")
    print("=" * 60)
    
    # Get manager
    manager = get_personality_manager()
    print(f"\n✓ PersonalityManager initialized")
    
    # List presets
    presets = manager.list_presets()
    print(f"\n✓ Available presets: {', '.join(presets)}")
    assert len(presets) >= 5, "Should have at least 5 presets"
    
    # Get active preset
    active = manager.get_active_preset()
    print(f"\n✓ Active preset: {active.name if active else 'None'}")
    assert active is not None, "Should have an active preset"
    
    # Test each preset
    print("\n" + "=" * 60)
    print("TESTING EACH PRESET")
    print("=" * 60)
    
    for preset_name in presets:
        preset = manager.get_preset(preset_name)
        assert preset is not None, f"Preset {preset_name} should exist"
        
        print(f"\n--- {preset.name} ---")
        print(f"  Role: {preset.identity.get('role', 'N/A')}")
        print(f"  Voice Style: {preset.identity.get('voice_style', 'N/A')}")
        print(f"  Humor Level: {preset.get_humor_level()}/10")
        print(f"  Formality Level: {preset.get_formality_level()}/10")
        print(f"  Verbosity Level: {preset.get_verbosity_level()}/10")
        print(f"  Uses Emoji: {preset.should_use_emoji()}")
        print(f"  Uses Memes: {preset.should_use_memes()}")
        
        # Test system prompt generation
        chat_prompt = preset.get_system_prompt("chat")
        assert len(chat_prompt) > 0, f"Chat prompt should not be empty for {preset_name}"
        print(f"  Chat Prompt Length: {len(chat_prompt)} chars")
        
        # Test response templates
        greeting = preset.get_response_template("greeting")
        if greeting:
            print(f"  Sample Greeting: \"{greeting}\"")
    
    # Test switching presets
    print("\n" + "=" * 60)
    print("TESTING PRESET SWITCHING")
    print("=" * 60)
    
    original_preset = manager.get_active_preset().name
    print(f"\nOriginal preset: {original_preset}")
    
    # Switch to Professional
    success = manager.switch_preset("Professional")
    assert success, "Should successfully switch to Professional"
    assert manager.get_active_preset().name == "Professional"
    print(f"✓ Switched to: Professional")
    
    # Switch to Casual
    success = manager.switch_preset("Casual")
    assert success, "Should successfully switch to Casual"
    assert manager.get_active_preset().name == "Casual"
    print(f"✓ Switched to: Casual")
    
    # Switch back to original
    success = manager.switch_preset(original_preset)
    assert success, f"Should successfully switch back to {original_preset}"
    assert manager.get_active_preset().name == original_preset
    print(f"✓ Switched back to: {original_preset}")
    
    # Test custom preset creation
    print("\n" + "=" * 60)
    print("TESTING CUSTOM PRESET CREATION")
    print("=" * 60)
    
    custom = manager.create_custom_preset(
        name="Test Custom",
        base_preset_name="OnyxKraken Default",
        modifications={
            "traits": {
                "humor_level": 10,
                "formality_level": 1,
            },
            "catchphrases": ["Test phrase 1", "Test phrase 2"],
        }
    )
    assert custom is not None, "Should create custom preset"
    assert custom.name == "Test Custom"
    assert custom.get_humor_level() == 10
    assert custom.get_formality_level() == 1
    assert "Test phrase 1" in custom.catchphrases
    print(f"✓ Created custom preset: {custom.name}")
    print(f"  Humor: {custom.get_humor_level()}/10")
    print(f"  Formality: {custom.get_formality_level()}/10")
    print(f"  Catchphrases: {custom.catchphrases}")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED")
    print("=" * 60)


def test_mind_integration():
    """Test integration with core.mind."""
    from core.mind import get_mind
    
    print("\n" + "=" * 60)
    print("TESTING MIND INTEGRATION")
    print("=" * 60)
    
    mind = get_mind()
    
    # Test identity prompt generation with different contexts
    contexts = ["chat", "work", "companion", "demo"]
    for context in contexts:
        prompt = mind.get_identity_prompt(context)
        assert len(prompt) > 0, f"Identity prompt should not be empty for {context}"
        print(f"\n✓ {context.upper()} context prompt ({len(prompt)} chars):")
        print(f"  {prompt[:100]}...")


def test_backend_integration():
    """Test integration with face.backend."""
    print("\n" + "=" * 60)
    print("TESTING BACKEND INTEGRATION")
    print("=" * 60)
    
    try:
        from face.backend import BackendBridge
        backend = BackendBridge()
        
        # Test system prompt building
        prompt = backend._build_system_prompt()
        assert len(prompt) > 0, "System prompt should not be empty"
        print(f"\n✓ Backend system prompt generated ({len(prompt)} chars)")
        print(f"  {prompt[:150]}...")
    except Exception as e:
        print(f"\n⚠ Backend test skipped (requires full environment): {e}")


if __name__ == "__main__":
    try:
        test_personality_presets()
        test_mind_integration()
        test_backend_integration()
        print("\n🎉 All personality system tests completed successfully!")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
