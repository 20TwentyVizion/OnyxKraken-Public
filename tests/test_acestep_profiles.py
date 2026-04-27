"""Quick smoke test for the shared ACE-Step profiles module."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.acestep_profiles import (
    QUALITY_PROFILES, get_quality_profile,
    STRUCTURE_TEMPLATES, build_instrumental_structure,
    get_template_for_genre,
)

print("=== Quality Profiles ===")
for name, qp in QUALITY_PROFILES.items():
    print(f"  {name}: model={qp['model']} steps={qp['inference_steps']} cfg={qp['guidance_scale']}")
assert len(QUALITY_PROFILES) == 5
assert get_quality_profile("radio_quality")["inference_steps"] == 60
assert get_quality_profile("nonexistent")["inference_steps"] == 50  # falls back to standard
print("  Profiles OK")

print("\n=== Structure Templates ===")
for name in STRUCTURE_TEMPLATES:
    t = STRUCTURE_TEMPLATES[name]
    print(f"  {name}: {len(t['sections'])} sections — {t['description'][:50]}")
assert len(STRUCTURE_TEMPLATES) >= 8
print("  Templates OK")

print("\n=== Genre Mapping ===")
mappings = {
    "house": "edm_club", "trap": "trap_beat", "jazz": "jazz_smooth",
    "rock": "rock_instrumental", "ambient": "lofi_chill",
    "cinematic": "cinematic", "unknown_genre": "minimal",
}
for genre, expected in mappings.items():
    result = get_template_for_genre(genre)
    assert result == expected, f"{genre} -> {result} (expected {expected})"
    print(f"  {genre} -> {result}")
print("  Mapping OK")

print("\n=== Build: EDM Club 180s ===")
edm = build_instrumental_structure(genre="house", duration=180)
assert "[intro]" in edm
assert "[drop]" in edm
assert "[outro]" in edm
print(edm[:200] + "...")
print("  EDM OK")

print("\n=== Build: Hip-Hop 60s (trimmed) ===")
hh = build_instrumental_structure(genre="hip-hop", duration=60)
assert "[intro]" in hh
lines = [l for l in hh.split("\n") if l.startswith("[")]
assert len(lines) <= 5, f"Too many sections for 60s: {len(lines)}"
print(hh)
print("  Hip-Hop 60s OK")

print("\n=== Build: Jazz 120s ===")
jazz = build_instrumental_structure(genre="jazz", duration=120)
assert "[instrumental]" in jazz
print(jazz[:200] + "...")
print("  Jazz OK")

print("\n=== Build: Custom sections ===")
custom = build_instrumental_structure(custom_sections=[
    "[intro]\n(hand pan intro, ethereal)",
    "[bass drop]\n(heavy sub bass, 808 pattern)",
    "[outro]\n(fade out)",
])
assert "[bass drop]" in custom
print(custom)
print("  Custom OK")

print("\nALL TESTS PASSED")
