"""Smoke test: verify youtube_strategy.py loads knowledge from youtube.json."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.skills.content_creation.youtube_strategy import (
    DEMONETIZATION_TRIGGERS, AI_CHANNEL_SPECIFIC_RISKS, AD_FRIENDLY_GUIDELINES,
    ALGORITHM_SIGNALS, GROWTH_PHASES, CONTENT_PILLARS,
    SEO_KNOWLEDGE, THUMBNAIL_STRATEGY, RETENTION_OPTIMIZATION,
    SHORTS_STRATEGY, UPLOAD_TIMING, COMMUNITY_ENGAGEMENT,
    MONETIZATION_STREAMS, CHANNEL_MISSION, TOOL_INVENTORY, COMPETITOR_AWARENESS,
    YouTubeStrategyEngine, assess_content_risk, ChannelState,
)

passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name}")
        failed += 1

print("=== Knowledge loaded from youtube.json ===")
check("demonetization high_risk loaded", len(DEMONETIZATION_TRIGGERS["high_risk"]) >= 5)
check("demonetization medium_risk loaded", len(DEMONETIZATION_TRIGGERS["medium_risk"]) >= 3)
check("AI channel risks loaded", len(AI_CHANNEL_SPECIFIC_RISKS) >= 3)
check("ad_friendly_guidelines loaded", bool(AD_FRIENDLY_GUIDELINES))
check("algorithm positive signals", len(ALGORITHM_SIGNALS["positive"]) >= 5)
check("algorithm negative signals", len(ALGORITHM_SIGNALS["negative"]) >= 3)

print("\n=== Growth phases ===")
check("growth phases loaded", len(GROWTH_PHASES) >= 4)
phase_names = [p.name for p in GROWTH_PHASES]
print(f"  Phases: {phase_names}")
check("launch phase exists", "launch" in phase_names)
check("growth phase exists", "growth" in phase_names)
check("phases sorted by subs", all(
    GROWTH_PHASES[i].subscriber_range[0] <= GROWTH_PHASES[i+1].subscriber_range[0]
    for i in range(len(GROWTH_PHASES)-1)
))
check("phases have content_mix", all(p.content_mix for p in GROWTH_PHASES))
check("phases have tactics", all(p.tactics for p in GROWTH_PHASES))

print("\n=== Content pillars ===")
check("content pillars loaded", len(CONTENT_PILLARS) >= 4)
pillar_ids = [p.id for p in CONTENT_PILLARS]
print(f"  Pillars: {pillar_ids}")
check("showcase pillar exists", "showcase" in pillar_ids)
check("educational pillar exists", "educational" in pillar_ids)
check("pillars have formats", all(p.formats for p in CONTENT_PILLARS))
check("pillars have example_topics", all(p.example_topics for p in CONTENT_PILLARS))

print("\n=== Enriched knowledge sections ===")
check("SEO knowledge loaded", bool(SEO_KNOWLEDGE))
check("SEO has title_formulas", "title_formulas" in SEO_KNOWLEDGE)
check("SEO has tag_strategy", "tag_strategy" in SEO_KNOWLEDGE)
check("SEO has pillar_title_templates", "pillar_title_templates" in SEO_KNOWLEDGE)
pillar_templates = SEO_KNOWLEDGE["pillar_title_templates"]
check("pillar templates for showcase", len(pillar_templates.get("showcase", [])) >= 3)
check("pillar templates for educational", len(pillar_templates.get("educational", [])) >= 3)
check("pillar templates for entertainment", len(pillar_templates.get("entertainment", [])) >= 3)
check("SEO has power_words", "power_words" in SEO_KNOWLEDGE)
pw = SEO_KNOWLEDGE["power_words"]
check("power_words has curiosity", len(pw.get("curiosity", [])) >= 3)
check("power_words has emotion", len(pw.get("emotion", [])) >= 3)
check("SEO has ab_testing", "ab_testing" in SEO_KNOWLEDGE)
ab = SEO_KNOWLEDGE["ab_testing"]
check("ab_testing has variant_types", len(ab.get("variant_types", [])) >= 3)
check("title formulas >= 10", len(SEO_KNOWLEDGE["title_formulas"]) >= 10)
check("thumbnail strategy loaded", bool(THUMBNAIL_STRATEGY))
check("thumbnail has design_rules", "design_rules" in THUMBNAIL_STRATEGY)
check("thumbnail has text_overlay_patterns", "text_overlay_patterns" in THUMBNAIL_STRATEGY)
check("thumbnail has color_palette", "color_palette" in THUMBNAIL_STRATEGY)
# Enriched per-pillar approach should be dicts now
ppa = THUMBNAIL_STRATEGY.get("per_pillar_approach", {})
check("thumbnail showcase is dict", isinstance(ppa.get("showcase"), dict))
check("thumbnail showcase has composition", "composition" in ppa.get("showcase", {}))
check("thumbnail showcase has text_overlay", "text_overlay" in ppa.get("showcase", {}))
check("thumbnail showcase has emotion", "emotion" in ppa.get("showcase", {}))
check("thumbnail educational has composition", "composition" in ppa.get("educational", {}))
check("retention optimization loaded", bool(RETENTION_OPTIMIZATION))
check("retention has hook_rules", "hook_rules" in RETENTION_OPTIMIZATION)
check("shorts strategy loaded", bool(SHORTS_STRATEGY))
check("upload timing loaded", bool(UPLOAD_TIMING))
check("community engagement loaded", bool(COMMUNITY_ENGAGEMENT))
check("monetization streams loaded", bool(MONETIZATION_STREAMS))
check("channel mission loaded", bool(CHANNEL_MISSION))
check("competitor awareness loaded", bool(COMPETITOR_AWARENESS))

print("\n=== Tool inventory ===")
tools = [k for k in TOOL_INVENTORY if not k.startswith("_")]
print(f"  Tools: {tools}")
check("tool inventory has entries", len(tools) >= 8)
check("blender_3d in tools", "blender_3d" in tools)
check("music_production in tools", "music_production" in tools)
check("animation_studio in tools", "animation_studio" in tools)
check("desktop_automation in tools", "desktop_automation" in tools)
check("tools have content_it_enables", all(
    "content_it_enables" in TOOL_INVENTORY[t] for t in tools
))

print("\n=== ChannelState + growth phase mapping ===")
cs = ChannelState(subscribers=500)
phase = cs.growth_phase()
check("500 subs -> traction phase", phase.name == "traction")

cs2 = ChannelState(subscribers=2000)
phase2 = cs2.growth_phase()
check("2000 subs -> monetization_push", phase2.name == "monetization_push")

cs3 = ChannelState(subscribers=50)
phase3 = cs3.growth_phase()
check("50 subs -> launch", phase3.name == "launch")

cs4 = ChannelState(subscribers=100000)
phase4 = cs4.growth_phase()
check("100K subs -> scale", phase4.name == "scale")

check("monetization not eligible (2000 subs, 0 hours)", not cs2.monetization_eligible())
cs5 = ChannelState(subscribers=1500, total_watch_hours=5000)
check("monetization eligible (1500 subs, 5000 hours)", cs5.monetization_eligible())

print("\n=== Risk assessment ===")
risk = assess_content_risk("AI builds a house", "Watch an AI construct a 3D house", ["AI", "Blender"])
check("safe topic is low risk", risk.overall_risk == "low")
check("safe topic is safe_to_publish", risk.safe_to_publish)

risk2 = assess_content_risk("Violence in games", "graphic violence gore discussion", ["violence", "gore"])
check("risky topic has flags", len(risk2.flags) > 0)
check("risky topic score > 0", risk2.score > 0)

print("\n=== Engine instantiation ===")
engine = YouTubeStrategyEngine()
check("engine created", engine is not None)
check("tool context summary non-empty", len(engine._tool_context_summary()) > 100)
check("mission context non-empty", len(engine._mission_context()) > 50)

report = engine.get_channel_report()
check("report has channel_state", "channel_state" in report)
check("report has growth_phase", "growth_phase" in report)
check("report has monetization", "monetization" in report)
check("report has available_tools", "available_tools" in report)
check("report available_tools non-empty", len(report["available_tools"]) >= 8)
check("report has shorts_strategy_available", report.get("shorts_strategy_available", False))
check("report has recommended_cadence", "recommended_cadence" in report["growth_phase"])

mix = engine.get_content_mix_analysis()
check("content mix has phase", "phase" in mix)
check("content mix has ideal_mix", "ideal_mix" in mix)

print("\n=== Shorts planning ===")
from core.skills.content_creation.youtube_strategy import StrategicShortPlan
short = engine.plan_short(short_type="standalone", tool="blender_3d")
check("short planned", short is not None)
check("short has id", bool(short.id))
check("short has concept", bool(short.concept))
check("short has tool_used", short.tool_used == "blender_3d")
check("short has short_type", short.short_type == "standalone")
check("short has hashtags", len(short.hashtags) >= 1)
check("short duration in range", 30 <= short.target_duration_seconds <= 60)
check("short has hook", bool(short.hook_first_2_seconds))
check("short has text_overlay", bool(short.text_overlay))
check("short has funnel", bool(short.funnel_to_long_form))
check("short has risk", short.risk_assessment is not None)
check("short in shorts_calendar", len(engine._shorts_calendar) >= 1)

batch = engine.plan_shorts_batch(count=3)
check("batch planned", len(batch) == 3)
check("batch has variety", len(set(s.tool_used for s in batch)) >= 2)
check("shorts calendar grew", len(engine._shorts_calendar) >= 4)

report = engine.get_shorts_report()
check("shorts report has total", report["total_planned"] >= 4)
check("shorts report has cadence", bool(report["recommended_cadence"]))
check("shorts report has by_type", "by_type" in report["recent_20"])
check("shorts report has by_tool", "by_tool" in report["recent_20"])

print("\n=== Content Calendar ===")
# Phase cadence parsing
lf, sh = engine._parse_phase_cadence()
check("cadence long-form > 0", lf >= 1)
check("cadence shorts > 0", sh >= 1)

# Plan a week
week = engine.plan_week(start_date="2025-07-07")
check("week has week_start", week["week_start"] == "2025-07-07")
check("week has week_end", week["week_end"] == "2025-07-13")
check("week has phase", bool(week["phase"]))
check("week has cadence", "long_form_per_week" in week["cadence"])
check("week long_form planned", len(week["long_form"]) >= 1)
check("week shorts planned", len(week["shorts"]) >= 1)
check("week total_slots > 0", week["total_slots"] >= 2)
# Each long-form slot has required fields
if week["long_form"]:
    slot = week["long_form"][0]
    check("lf slot has scheduled_date", bool(slot["scheduled_date"]))
    check("lf slot has title", bool(slot["title"]))
    check("lf slot has pillar", bool(slot["pillar"]))
    check("lf slot has scheduled_day", bool(slot["scheduled_day"]))
# Each shorts slot has required fields
if week["shorts"]:
    slot = week["shorts"][0]
    check("sh slot has scheduled_date", bool(slot["scheduled_date"]))
    check("sh slot has tool", bool(slot["tool"]))

# Calendar view
view = engine.get_calendar_view(days=30)
check("calendar has as_of", bool(view["as_of"]))
check("calendar has cadence_target", "long_form_per_week" in view["cadence_target"])
check("calendar has warnings (list)", isinstance(view["warnings"], list))
check("calendar has total_in_calendar", view["total_in_calendar"] >= 1)
check("calendar has stale_pillars", isinstance(view["stale_pillars"], list))

print("\n=== Capability Map — music & animation ===")
from core.skills.content_creation.capability_map import CapabilityMap, CAPABILITIES, SHOW_FORMATS
cm = CapabilityMap()
check("capabilities loaded", len(CAPABILITIES) >= 20)
check("music category exists", "music" in cm.get_categories())
music_caps = cm.list_capabilities(category="music")
check("music capabilities >= 6", len(music_caps) >= 6)
music_ids = [c["id"] for c in music_caps]
check("beat_making exists", "beat_making" in music_ids)
check("beat_battle exists", "beat_battle" in music_ids)
check("dj_set exists", "dj_set" in music_ids)
check("song_creation exists", "song_creation" in music_ids)
check("music_review exists", "music_review" in music_ids)
check("live_production exists", "live_production" in music_ids)
check("animation_studio exists", cm.can_do("animation_studio"))

check("show formats >= 15", len(SHOW_FORMATS) >= 15)
check("beat_session format", "beat_session" in SHOW_FORMATS)
check("beat_battle_show format", "beat_battle_show" in SHOW_FORMATS)
check("music_video format", "music_video" in SHOW_FORMATS)
check("dj_set_show format", "dj_set_show" in SHOW_FORMATS)
check("song_premiere format", "song_premiere" in SHOW_FORMATS)

# Topic matching
fmt = cm._match_format_to_topic("produce a trap beat")
check("topic 'produce a trap beat' -> beat_session", fmt and fmt["name"] == "Beat Production Session")
fmt2 = cm._match_format_to_topic("beat battle vs phantom")
check("topic 'beat battle' -> beat_battle_show", fmt2 and fmt2["name"] == "Beat Battle Show")
fmt3 = cm._match_format_to_topic("write a song about space")
check("topic 'write a song' -> song_premiere", fmt3 and fmt3["name"] == "Song Premiere")
fmt4 = cm._match_format_to_topic("1 hour dj set")
check("topic 'dj set' -> dj_set_show", fmt4 and fmt4["name"] == "DJ Set Episode")

# Music content ideas
music_ideas = cm.get_content_ideas(category="music", count=50)
check("music ideas available", len(music_ideas) >= 10)

print(f"\n{'='*50}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed+failed}")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
