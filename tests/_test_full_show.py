"""Test: Full show pipeline — beginning to end.

Runs the complete autonomous content creation pipeline:
  1. Initialize all show systems
  2. Plan an episode (format + topic selection)
  3. Script the episode (generate narration per segment)
  4. Run pre-show checklist (10-step evaluation)
  5. Produce ShowEngine cues
  6. Simulate recording (walk through each cue)
  7. Mark recorded + review performance
  8. Print full summary
"""
import sys, os, time, json, logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
# Quiet down noisy loggers
logging.getLogger("urllib3").setLevel(logging.WARNING)

from core.skills.content_creation.onyx_persona import OnyxPersona
from core.skills.content_creation.meme_expression import MemeExpression
from core.skills.content_creation.capability_map import CapabilityMap
from core.skills.content_creation.show_runner import ShowRunner
from core.skills.content_creation.pre_show_director import PreShowDirector
from core.skills.content_creation.meme_downloader import MemeDownloader


# ===================================================================
# Helpers
# ===================================================================

W = 60  # banner width

def banner(text, char="="):
    print(f"\n{char * W}")
    print(f"  {text}")
    print(f"{char * W}")

def step(label):
    print(f"\n{'─' * W}")
    print(f"  STEP: {label}")
    print(f"{'─' * W}")

def show_dict(d, indent=4, max_depth=2, _depth=0):
    """Pretty-print a dict with controlled depth."""
    prefix = " " * indent * _depth
    if _depth >= max_depth:
        print(f"{prefix}  ...")
        return
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, (dict, list)):
                print(f"{prefix}  {k}:")
                show_dict(v, indent, max_depth, _depth + 1)
            else:
                val_str = str(v)
                if len(val_str) > 100:
                    val_str = val_str[:97] + "..."
                print(f"{prefix}  {k}: {val_str}")
    elif isinstance(d, list):
        for i, item in enumerate(d[:8]):
            if isinstance(item, dict):
                print(f"{prefix}  [{i}]:")
                show_dict(item, indent, max_depth, _depth + 1)
            else:
                val_str = str(item)
                if len(val_str) > 100:
                    val_str = val_str[:97] + "..."
                print(f"{prefix}  [{i}] {val_str}")
        if len(d) > 8:
            print(f"{prefix}  ... and {len(d) - 8} more")


# ===================================================================
# MAIN
# ===================================================================

banner("THE ONYX SHOW — FULL PIPELINE TEST")
print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  CWD:  {os.getcwd()}")

t_total = time.time()


# -------------------------------------------------------------------
# 1. INITIALIZE
# -------------------------------------------------------------------

step("1. INITIALIZE ALL SYSTEMS")

t0 = time.time()
persona = OnyxPersona()
print(f"  ✓ OnyxPersona loaded  (mood: {persona.mood})")

memes = MemeExpression()
meme_stats = memes.get_stats()
print(f"  ✓ MemeExpression loaded  ({meme_stats['total_memes']} memes in library)")

cap_map = CapabilityMap()
cap_stats = cap_map.get_stats()
print(f"  ✓ CapabilityMap loaded  ({cap_stats['total_capabilities']} capabilities, "
      f"{cap_stats['total_content_ideas']} content ideas)")

show_runner = ShowRunner(
    persona=persona,
    capability_map=cap_map,
    meme_expression=memes,
)
series = show_runner.get_series_state()
print(f"  ✓ ShowRunner loaded  (series: '{series['series_name']}', "
      f"episodes: {series['episode_count']})")

pre_show = PreShowDirector(
    persona=persona,
    capability_map=cap_map,
    meme_expression=memes,
    show_runner=show_runner,
)
print(f"  ✓ PreShowDirector loaded")

meme_dl = MemeDownloader()
api_status = meme_dl.get_api_key_status()
print(f"  ✓ MemeDownloader loaded  (reddit: {api_status['reddit']}, "
      f"imgflip: {api_status['imgflip']}, "
      f"giphy: {api_status['giphy']}, tenor: {api_status['tenor']})")

print(f"\n  All systems initialized in {time.time() - t0:.2f}s")


# -------------------------------------------------------------------
# 2. PERSONA CHECK — Who is Onyx today?
# -------------------------------------------------------------------

step("2. PERSONA CHECK — Who is Onyx today?")

persona.set_mood("excited", "about to film the first episode!")
mood_display = persona.get_mood_for_display()
print(f"  Mood: {mood_display['mood']} {mood_display['emoji']} "
      f"(energy: {mood_display['energy']}, humor: {mood_display['humor']})")
print(f"  Character: {persona.character['name']} — {persona.character['tagline']}")
print(f"  Voice: {persona.character['voice_style'][:80]}...")

catchphrase = persona.get_catchphrase()
print(f"  Catchphrase: \"{catchphrase}\"")

greeting = persona.react("greeting")
print(f"  Greeting: \"{greeting}\"")


# -------------------------------------------------------------------
# 3. CAPABILITY CHECK — What can Onyx do?
# -------------------------------------------------------------------

step("3. CAPABILITY CHECK — What can Onyx do?")

print("  Available show formats:")
formats = cap_map.get_show_formats()
for fmt in formats:
    can = "✓" if fmt["can_execute"] else "✗"
    print(f"    {can} {fmt['name']} ({fmt['difficulty']}) — {fmt.get('audience_appeal', '')[:50]}")

print(f"\n  Content ideas (random 5):")
ideas = cap_map.get_content_ideas(count=5)
for idea in ideas:
    print(f"    • [{idea['category']}/{idea['difficulty']}] {idea['idea']}")


# -------------------------------------------------------------------
# 4. PLAN EPISODE
# -------------------------------------------------------------------

step("4. PLAN EPISODE")

t0 = time.time()
# Let Onyx plan autonomously — or use a specific format for the test
episode = show_runner.plan_next_episode(
    topic="exploring the desktop for the first time",
    format_id="chaos_hour",
)

from dataclasses import asdict
ep_data = asdict(episode)

print(f"  Episode ID:    {episode.id}")
print(f"  Title:         {episode.title}")
print(f"  Format:        {episode.format_id}")
print(f"  Topic:         {episode.topic}")
print(f"  Mood:          {episode.mood}")
print(f"  Difficulty:    {episode.difficulty}")
print(f"  Duration:      {episode.estimated_duration}s ({episode.estimated_duration // 60}min)")
print(f"  Segments:      {len(episode.segments)}")
print(f"  Hashtags:      {episode.hashtags[:5]}")
print(f"  Planned in:    {time.time() - t0:.2f}s")

print(f"\n  Segment outline:")
for i, seg in enumerate(episode.segments):
    seg_type = seg.get("type", "?")
    emotion = seg.get("emotion", "")
    dur = seg.get("duration_seconds", 0)
    print(f"    {i+1:2d}. [{seg_type}] emotion={emotion}, {dur}s")


# -------------------------------------------------------------------
# 5. SCRIPT EPISODE
# -------------------------------------------------------------------

step("5. SCRIPT EPISODE — Generate narration")

t0 = time.time()
episode = show_runner.script_episode(episode)
print(f"  Scripted in: {time.time() - t0:.2f}s")
print(f"  Status:      {episode.status}")

print(f"\n  Narration per segment:")
for i, seg in enumerate(episode.segments):
    narration = seg.get("narration", "")
    seg_type = seg.get("type", "?")
    preview = narration[:120] + "..." if len(narration) > 120 else narration
    if narration:
        print(f"    {i+1:2d}. [{seg_type}] \"{preview}\"")
    else:
        print(f"    {i+1:2d}. [{seg_type}] (no narration)")


# -------------------------------------------------------------------
# 6. PRE-SHOW CHECK — 10-step evaluation
# -------------------------------------------------------------------

step("6. PRE-SHOW CHECK — Full evaluation")

t0 = time.time()
ep_data = asdict(episode)
checklist = pre_show.run_pre_show(ep_data)
print(f"  Completed in: {time.time() - t0:.2f}s")
print(f"  Overall score: {checklist['overall_score']:.1%}")
print(f"  GREENLIT:      {'YES ✓' if checklist['greenlit'] else 'NO ✗'}")

print(f"\n  Checklist items:")
for item in checklist.get("items", []):
    status_icon = {"passed": "✓", "warning": "⚠", "failed": "✗", "skipped": "—"}.get(
        item.get("status", ""), "?")
    print(f"    {status_icon} [{item['step']}] score={item['score']:.1%} — {item.get('details', '')[:80]}")
    for sug in item.get("suggestions", [])[:2]:
        print(f"      → {sug[:80]}")

print(f"\n  Stage setup:")
print(f"    Background preset: {checklist.get('background_preset', 'N/A')}")
print(f"    Backdrop image:    {checklist.get('backdrop_path', 'none')}")
print(f"    Face position:     {checklist.get('face_position', 'N/A')}")
print(f"    Mood set:          {checklist.get('mood_set', 'N/A')}")
print(f"    Memes prepped:     {checklist.get('memes_prepped', 0)}")


# -------------------------------------------------------------------
# 7. PRODUCE CUES — Generate ShowEngine cue sequence
# -------------------------------------------------------------------

step("7. PRODUCE CUES — ShowEngine sequence")

t0 = time.time()
cues = show_runner.produce_cues(episode)
print(f"  Generated {len(cues)} cues in {time.time() - t0:.2f}s")

print(f"\n  Cue sequence:")
for i, cue in enumerate(cues):
    kind = cue.get("kind", "?")
    dur = cue.get("duration", 0)
    if kind == "narrate":
        text_preview = cue.get("text", "")[:60]
        print(f"    {i+1:3d}. NARRATE ({dur:.1f}s) \"{text_preview}...\"")
    elif kind == "emotion":
        print(f"    {i+1:3d}. EMOTION → {cue.get('emotion', '?')} ({dur:.1f}s)")
    elif kind == "callback":
        print(f"    {i+1:3d}. CALLBACK [meme popup] ({dur:.1f}s)")
    elif kind == "pause":
        print(f"    {i+1:3d}. PAUSE ({dur:.1f}s)")
    else:
        print(f"    {i+1:3d}. {kind} ({dur:.1f}s)")


# -------------------------------------------------------------------
# 8. SIMULATE RECORDING — Walk through cues
# -------------------------------------------------------------------

step("8. SIMULATE RECORDING — Execute show")

print("  [RECORDING STARTED]")
print()

sim_time = 0.0
for i, cue in enumerate(cues):
    kind = cue.get("kind", "?")
    dur = cue.get("duration", 0)

    if kind == "narrate":
        text = cue.get("text", "")
        emotion = cue.get("emotion", "")
        # Simulate TTS timing
        print(f"  [{sim_time:6.1f}s] 🎤 NARRATE ({emotion}): \"{text[:100]}\"")
    elif kind == "emotion":
        emo = cue.get("emotion", "?")
        print(f"  [{sim_time:6.1f}s] 😊 FACE → {emo}")
    elif kind == "callback":
        print(f"  [{sim_time:6.1f}s] 🖼️  MEME POPUP")
    elif kind == "pause":
        pass  # silent pause, don't print

    sim_time += dur

print()
print(f"  [RECORDING COMPLETE]")
print(f"  Total show time: {sim_time:.1f}s ({sim_time/60:.1f} min)")


# -------------------------------------------------------------------
# 9. POST-PRODUCTION — Thumbnail + diary entry
# -------------------------------------------------------------------

step("9. POST-PRODUCTION")

# Diary entry about filming
diary = persona.write_diary_entry(
    f"Just filmed my first episode! Topic: {episode.topic}. "
    f"Format: {episode.format_id}. It went great!",
    use_llm=False,
)
print(f"  Diary entry: \"{diary.get('entry', '')[:120]}...\"")

# Reaction to finishing
reaction = persona.react("success", f"filmed episode about {episode.topic}")
print(f"  Reaction: \"{reaction}\"")

# Mark as recorded
episode = show_runner.mark_recorded(
    episode.id,
    video_path=f"data/recordings/show_ep1_{episode.format_id}.mp4",
)
print(f"  Episode status: {episode.status}")
print(f"  Video path: {episode.recorded_path}")

# Thumbnail prompt
print(f"  Thumbnail prompt: \"{episode.thumbnail_prompt[:100]}...\"")


# -------------------------------------------------------------------
# 10. REVIEW PERFORMANCE
# -------------------------------------------------------------------

step("10. PERFORMANCE REVIEW")

# Simulate some metrics
show_runner.update_episode_performance(
    episode.id,
    views=1,  # it's a test :)
    likes=1,
    comments=0,
    engagement_rate=1.0,
)

review = show_runner.review_performance()
print(f"  Review OK: {review.get('ok', False)}")
if review.get("insights"):
    print(f"  Insights:")
    show_dict(review["insights"], max_depth=1)

series = show_runner.get_series_state()
print(f"\n  Series state after episode:")
print(f"    Episodes:        {series['episode_count']}")
print(f"    Total views:     {series['total_views']}")
print(f"    Avg engagement:  {series['avg_engagement']:.1%}")
print(f"    Best format:     {series['best_format']}")


# -------------------------------------------------------------------
# FINAL SUMMARY
# -------------------------------------------------------------------

banner("TEST COMPLETE — FULL PIPELINE SUMMARY")

total_time = time.time() - t_total
print(f"""
  Pipeline stages completed:
    1. ✓ System initialization
    2. ✓ Persona check (mood: {persona.mood})
    3. ✓ Capability check ({cap_stats['total_capabilities']} capabilities)
    4. ✓ Episode planned: "{episode.title}"
    5. ✓ Script generated ({len(episode.segments)} segments with narration)
    6. ✓ Pre-show check ({'GREENLIT' if checklist['greenlit'] else 'NOT READY'} — {checklist['overall_score']:.0%})
    7. ✓ Cues produced ({len(cues)} cues)
    8. ✓ Show simulated ({sim_time:.0f}s runtime)
    9. ✓ Post-production (diary + reaction)
   10. ✓ Performance review

  Total pipeline time: {total_time:.2f}s
  Episode status:      {episode.status}
""")

# Final catchphrase
print(f"  Onyx says: \"{persona.get_catchphrase()}\"")
print()
banner("END", "=")
