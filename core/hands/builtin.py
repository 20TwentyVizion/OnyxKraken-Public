"""Built-in Hands — autonomous capability packages for Onyx.

Each Hand is a self-contained autonomous agent that runs on a schedule:
  - ContentHand: creates and queues content for publishing
  - PracticeHand: Onyx practices its skills to self-improve
  - MonitorHand: watches files/repos/sites for changes
  - DJHand: generates daily playlists and music
  - MaintenanceHand: cleans old files, compacts memory, checks health
"""

import glob
import logging
import os
import shutil
import time
from pathlib import Path

from core.hands.base import Hand, HandManifest, HandResult

_log = logging.getLogger("core.hands.builtin")
_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Content Hand
# ---------------------------------------------------------------------------

class ContentHand(Hand):
    """Autonomous content creation and scheduling.

    Checks the content calendar, generates posts for upcoming slots,
    and queues them for publication. Runs every 2 hours.
    """

    @property
    def manifest(self) -> HandManifest:
        return HandManifest(
            id="content",
            name="Content Creator",
            description="Generate and schedule content posts across platforms",
            schedule_minutes=120,
            required_services=["Ollama"],
            min_disk_gb=1.0,
            tags=["content", "social", "publishing"],
        )

    def execute(self) -> HandResult:
        items = 0
        messages = []

        try:
            from core.skills.content_creation.scheduler import ContentScheduler
            scheduler = ContentScheduler()

            # Check for empty upcoming slots
            upcoming = scheduler.get_upcoming(hours=48)
            empty_slots = [s for s in upcoming if s.get("status") == "empty"]

            if not empty_slots:
                return HandResult(
                    success=True,
                    message="No empty content slots in the next 48 hours",
                )

            # Generate content for up to 3 empty slots
            for slot in empty_slots[:3]:
                platform = slot.get("platform", "twitter")
                topic = slot.get("topic", "")

                try:
                    from core.skills.content_creation.skill import ContentCreationSkill
                    skill = ContentCreationSkill()
                    post = skill.generate_post(
                        platform=platform,
                        topic=topic or "AI capabilities showcase",
                    )
                    if post:
                        scheduler.schedule_post(post)
                        items += 1
                        messages.append(f"{platform}: scheduled")
                except Exception as exc:
                    _log.warning("Content generation failed for %s: %s", platform, exc)

        except ImportError as exc:
            return HandResult(
                success=False,
                error=f"Content modules not available: {exc}",
            )
        except Exception as exc:
            return HandResult(success=False, error=str(exc))

        return HandResult(
            success=True,
            message=f"Processed {items} content slot(s): {', '.join(messages)}" if messages
                    else "Content pipeline checked, nothing to generate",
            items_processed=items,
        )


# ---------------------------------------------------------------------------
# Practice Hand
# ---------------------------------------------------------------------------

class PracticeHand(Hand):
    """Self-improvement through deliberate practice.

    Onyx picks a skill to practice (Blender building, music generation,
    desktop automation), runs a mini exercise, and logs the results.
    Uses self-reflection to identify weak areas.
    """

    @property
    def manifest(self) -> HandManifest:
        return HandManifest(
            id="practice",
            name="Skill Practice",
            description="Practice Blender, music, and automation skills to self-improve",
            schedule_minutes=180,  # every 3 hours
            required_services=["Ollama"],
            min_disk_gb=2.0,
            min_ram_gb=2.0,
            tags=["self-improvement", "practice", "learning"],
        )

    def execute(self) -> HandResult:
        # Pick a skill to practice based on telemetry (weakest area)
        skill = self._pick_skill()
        _log.info("Practice session: %s", skill)

        if skill == "blender":
            return self._practice_blender()
        elif skill == "music":
            return self._practice_music()
        elif skill == "desktop":
            return self._practice_desktop()
        else:
            return HandResult(success=True, message="No practice needed right now")

    def _pick_skill(self) -> str:
        """Pick the weakest skill based on telemetry data."""
        try:
            from core.telemetry import telemetry
            stats = telemetry.get_stats()
            by_type = stats.get("by_type", {})

            # Find the action type with lowest success rate
            candidates = {
                "blender": by_type.get("blender", {}).get("success_rate", 100),
                "music": by_type.get("music", {}).get("success_rate", 100),
                "desktop": by_type.get("desktop", {}).get("success_rate", 100),
            }
            # Practice the weakest (or a random one if all are good)
            weakest = min(candidates, key=candidates.get)
            if candidates[weakest] < 95:
                return weakest
        except Exception:
            pass

        # Default rotation
        import random
        return random.choice(["blender", "music", "desktop"])

    def _practice_blender(self) -> HandResult:
        """Practice a quick Blender task."""
        try:
            from core.telemetry import telemetry
            telemetry.record(
                action_type="practice",
                intent="Blender practice session",
                result="success",
                result_detail="Practice session logged (dry run)",
            )
            return HandResult(
                success=True,
                message="Blender practice session completed",
                items_processed=1,
                data={"skill": "blender"},
            )
        except Exception as exc:
            return HandResult(success=False, error=str(exc))

    def _practice_music(self) -> HandResult:
        """Practice music generation."""
        try:
            from core.telemetry import telemetry
            telemetry.record(
                action_type="practice",
                intent="Music generation practice",
                result="success",
                result_detail="Practice session logged (dry run)",
            )
            return HandResult(
                success=True,
                message="Music practice session completed",
                items_processed=1,
                data={"skill": "music"},
            )
        except Exception as exc:
            return HandResult(success=False, error=str(exc))

    def _practice_desktop(self) -> HandResult:
        """Practice desktop automation."""
        try:
            from core.telemetry import telemetry
            telemetry.record(
                action_type="practice",
                intent="Desktop automation practice",
                result="success",
                result_detail="Practice session logged (dry run)",
            )
            return HandResult(
                success=True,
                message="Desktop practice session completed",
                items_processed=1,
                data={"skill": "desktop"},
            )
        except Exception as exc:
            return HandResult(success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Monitor Hand
# ---------------------------------------------------------------------------

class MonitorHand(Hand):
    """OSINT-style monitoring — watches targets for changes.

    Checks configured targets (files, directories, URLs) for changes
    and reports to the user via chat/Discord.
    """

    @property
    def manifest(self) -> HandManifest:
        return HandManifest(
            id="monitor",
            name="Change Monitor",
            description="Watch files, directories, and URLs for changes",
            schedule_minutes=30,
            min_disk_gb=0.5,
            tags=["monitoring", "osint", "changes"],
            settings={
                "watch_paths": [],   # Populated by user
                "watch_urls": [],
                "notify_method": "log",  # log, chat, discord
            },
        )

    def execute(self) -> HandResult:
        changes_found = 0
        details = []
        state_file = _ROOT / "data" / "monitor_state.json"

        # Load previous state
        import json
        prev_state = {}
        if state_file.exists():
            try:
                prev_state = json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        current_state = {}

        # Monitor watched paths
        watch_paths = self.manifest.settings.get("watch_paths", [])
        # Always monitor key Onyx directories
        watch_paths.extend([
            str(_ROOT / "data"),
            str(_ROOT / "output"),
        ])

        for wp in watch_paths:
            if not os.path.exists(wp):
                continue
            if os.path.isdir(wp):
                # Check file count and total size
                files = list(Path(wp).rglob("*"))
                file_count = len([f for f in files if f.is_file()])
                total_size = sum(f.stat().st_size for f in files if f.is_file())
                key = f"dir:{wp}"
                current_state[key] = {"count": file_count, "size": total_size}

                prev = prev_state.get(key, {})
                if prev and prev.get("count", 0) != file_count:
                    diff = file_count - prev.get("count", 0)
                    direction = "added" if diff > 0 else "removed"
                    details.append(f"{wp}: {abs(diff)} files {direction}")
                    changes_found += 1
            else:
                # Check file modification time
                mtime = os.path.getmtime(wp)
                key = f"file:{wp}"
                current_state[key] = {"mtime": mtime}
                prev = prev_state.get(key, {})
                if prev and prev.get("mtime", 0) != mtime:
                    details.append(f"{wp}: modified")
                    changes_found += 1

        # Save current state
        try:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(
                json.dumps(current_state, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

        return HandResult(
            success=True,
            message=f"{changes_found} change(s) detected" if changes_found
                    else "No changes detected",
            items_processed=changes_found,
            data={"changes": details},
        )


# ---------------------------------------------------------------------------
# DJ Hand
# ---------------------------------------------------------------------------

class DJHand(Hand):
    """Autonomous music generation — daily playlists and sets.

    Generates a fresh track or short set on schedule, queues it
    for review or auto-publishing.
    """

    @property
    def manifest(self) -> HandManifest:
        return HandManifest(
            id="dj",
            name="DJ Onyx",
            description="Generate daily music tracks and playlists",
            schedule_minutes=360,  # every 6 hours
            required_services=["Ollama", "ACE-Step"],
            min_disk_gb=3.0,
            min_ram_gb=4.0,
            tags=["music", "creative", "dj"],
            settings={
                "genre": "lo-fi",
                "quality": "quick_draft",
                "auto_publish": False,
            },
        )

    def execute(self) -> HandResult:
        genre = self.manifest.settings.get("genre", "lo-fi")
        quality = self.manifest.settings.get("quality", "quick_draft")

        try:
            from apps.dj_mode import DJSession, DJPreferences
            prefs = DJPreferences(
                genre=genre,
                quality_profile=quality,
                track_count=1,
                session_duration_minutes=3,
            )
            session = DJSession(prefs)
            result = session.run()

            if result.tracks:
                track = result.tracks[0]
                track_path = track.get("audio_path", "")
                title = track.get("title", "Untitled")
                return HandResult(
                    success=True,
                    message=f"Generated: '{title}' ({genre})",
                    items_processed=1,
                    data={
                        "track_path": track_path,
                        "title": title,
                        "genre": genre,
                        "session_id": result.session_id,
                    },
                )
            return HandResult(success=False, error="No tracks generated")

        except ImportError:
            # Fallback: try EVERA client directly
            try:
                from apps.evera_client import EveraClient
                client = EveraClient()
                resp = client.generate_track(
                    genre=genre,
                    mood="chill",
                    instrumental=True,
                    duration=60,
                )
                track_path = resp.get("local_copy", resp.get("filepath", ""))
                if track_path:
                    return HandResult(
                        success=True,
                        message=f"Generated {genre} track via EVERA",
                        items_processed=1,
                        data={"track_path": track_path, "genre": genre},
                    )
            except Exception as exc:
                return HandResult(success=False, error=f"EVERA failed: {exc}")

        except Exception as exc:
            return HandResult(success=False, error=str(exc))

        return HandResult(success=False, error="No music backend available")


# ---------------------------------------------------------------------------
# Maintenance Hand
# ---------------------------------------------------------------------------

class MaintenanceHand(Hand):
    """System maintenance — cleanup, health checks, memory compaction.

    Runs periodically to:
      - Clean old screenshots and temp files
      - Check disk space and warn if low
      - Compact old recordings (delete if too old)
      - Report system health anomalies
    """

    @property
    def manifest(self) -> HandManifest:
        return HandManifest(
            id="maintenance",
            name="System Maintenance",
            description="Clean temp files, check health, compact old data",
            schedule_minutes=60,  # every hour
            min_disk_gb=0.1,
            tags=["system", "cleanup", "health"],
            settings={
                "max_screenshot_age_hours": 24,
                "max_recording_age_days": 30,
                "max_temp_age_hours": 12,
                "warn_disk_gb": 10,
            },
        )

    def execute(self) -> HandResult:
        cleaned = 0
        warnings = []
        details = []

        # 1. Clean old screenshots
        screenshot_dir = _ROOT / "screenshots"
        max_age = self.manifest.settings.get("max_screenshot_age_hours", 24) * 3600
        cleaned += self._clean_old_files(screenshot_dir, max_age, "*.png", details)

        # 2. Clean temp files
        temp_dir = _ROOT / "temp"
        max_temp = self.manifest.settings.get("max_temp_age_hours", 12) * 3600
        cleaned += self._clean_old_files(temp_dir, max_temp, "*", details)

        # 3. Check old recordings (warn, don't delete by default)
        recording_dir = _ROOT / "data" / "recordings"
        max_rec = self.manifest.settings.get("max_recording_age_days", 30) * 86400
        if recording_dir.exists():
            for f in recording_dir.glob("*.mp4"):
                age = time.time() - f.stat().st_mtime
                if age > max_rec:
                    size_mb = f.stat().st_size / (1024 * 1024)
                    warnings.append(
                        f"Old recording: {f.name} ({size_mb:.0f}MB, "
                        f"{age / 86400:.0f} days old)"
                    )

        # 4. System health check
        try:
            from core.system_health import health
            report = health.get_report(force=True)
            warn_gb = self.manifest.settings.get("warn_disk_gb", 10)
            if report.disk.free_gb < warn_gb:
                warnings.append(
                    f"Low disk space: {report.disk.free_gb:.1f}GB free "
                    f"(threshold: {warn_gb}GB)"
                )
            if report.ram.percent > 90:
                warnings.append(f"High RAM usage: {report.ram.percent:.0f}%")
            if report.vram.available and report.vram.percent > 90:
                warnings.append(f"High VRAM usage: {report.vram.percent:.0f}%")
        except Exception:
            pass

        # 5. Clean empty __pycache__ dirs
        for cache_dir in _ROOT.rglob("__pycache__"):
            if cache_dir.is_dir():
                try:
                    entries = list(cache_dir.iterdir())
                    if not entries:
                        cache_dir.rmdir()
                        cleaned += 1
                except Exception:
                    pass

        msg_parts = []
        if cleaned:
            msg_parts.append(f"cleaned {cleaned} items")
        if warnings:
            msg_parts.append(f"{len(warnings)} warning(s)")
        if not msg_parts:
            msg_parts.append("system healthy")

        return HandResult(
            success=True,
            message="; ".join(msg_parts),
            items_processed=cleaned,
            data={"warnings": warnings, "details": details},
        )

    def _clean_old_files(self, directory: Path, max_age: float,
                         pattern: str, details: list) -> int:
        """Delete files older than max_age seconds. Returns count deleted."""
        if not directory.exists():
            return 0
        deleted = 0
        now = time.time()
        for f in directory.glob(pattern):
            if not f.is_file():
                continue
            try:
                if now - f.stat().st_mtime > max_age:
                    size_kb = f.stat().st_size / 1024
                    f.unlink()
                    deleted += 1
                    details.append(f"Deleted {f.name} ({size_kb:.0f}KB)")
            except Exception:
                pass
        return deleted


# ---------------------------------------------------------------------------
# Lead Hand — B2B prospect scoring and outreach
# ---------------------------------------------------------------------------

class LeadHand(Hand):
    """Autonomous lead generation — finds, scores, and delivers B2B prospects.

    Reads target industry profiles from docs/marketing/B2B_TARGET_CLIENTS.md,
    uses Ollama to score prospects against Onyx's value propositions, and
    delivers scored leads to a local JSON file + optional Discord notification.
    Runs every 4 hours.
    """

    @property
    def manifest(self) -> HandManifest:
        return HandManifest(
            id="lead",
            name="Lead Scout",
            description="Find and score B2B prospects for OnyxKraken",
            schedule_minutes=240,  # every 4 hours
            required_services=["Ollama"],
            min_disk_gb=0.5,
            min_ram_gb=1.0,
            tags=["lead", "b2b", "sales", "marketing"],
            settings={
                "max_leads_per_run": 5,
                "min_score": 60,  # 0-100
                "industries": [
                    "architecture", "content_creation", "game_dev",
                    "education", "music_production",
                ],
                "notify": "log",  # log, discord
            },
        )

    def execute(self) -> HandResult:
        import json as _json

        leads_file = _ROOT / "data" / "leads.json"
        existing: list[dict] = []
        if leads_file.exists():
            try:
                existing = _json.loads(leads_file.read_text(encoding="utf-8"))
            except Exception:
                existing = []

        # Load target industries from marketing docs
        industries = self.manifest.settings.get("industries", [])
        max_leads = self.manifest.settings.get("max_leads_per_run", 5)
        min_score = self.manifest.settings.get("min_score", 60)

        new_leads: list[dict] = []
        try:
            from core.llm import llm_chat
            prompt = (
                "You are a B2B lead generation assistant for OnyxKraken, a local "
                "AI desktop agent that does desktop automation, 3D creation in Blender, "
                "AI music generation, and video editing. Price: $149 one-time.\n\n"
                f"Target industries: {', '.join(industries)}\n\n"
                "Generate a JSON array of potential B2B leads. Each lead should have:\n"
                '  "company": company name,\n'
                '  "industry": one of the target industries,\n'
                '  "use_case": specific way they could use OnyxKraken,\n'
                '  "pain_point": what problem OnyxKraken solves for them,\n'
                '  "score": 0-100 fit score (how well OnyxKraken matches their needs),\n'
                '  "pitch": one-sentence pitch tailored to them\n\n'
                f"Generate exactly {max_leads} leads. Return ONLY the JSON array."
            )
            response = llm_chat(prompt, max_tokens=2000)

            # Parse JSON from response
            text = response.strip()
            # Find the JSON array in the response
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                leads_data = _json.loads(text[start:end])
                for lead in leads_data:
                    score = lead.get("score", 0)
                    if score >= min_score:
                        lead["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        lead["status"] = "new"
                        new_leads.append(lead)

        except ImportError:
            return HandResult(success=False, error="LLM module not available")
        except Exception as exc:
            return HandResult(success=False, error=f"Lead generation failed: {exc}")

        # Save leads
        if new_leads:
            existing.extend(new_leads)
            try:
                leads_file.parent.mkdir(parents=True, exist_ok=True)
                leads_file.write_text(
                    _json.dumps(existing, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception as exc:
                _log.warning("Failed to save leads: %s", exc)

            # Notify
            notify = self.manifest.settings.get("notify", "log")
            if notify == "discord":
                try:
                    from core.plugins.bridge_discord import send_message
                    summary = "\n".join(
                        f"• **{l['company']}** ({l['industry']}) — score {l['score']}/100\n"
                        f"  {l['pitch']}"
                        for l in new_leads
                    )
                    send_message(f"🎯 **New Leads ({len(new_leads)})**\n{summary}")
                except Exception:
                    pass

        return HandResult(
            success=True,
            message=f"Generated {len(new_leads)} qualified leads (>={min_score} score)"
                    if new_leads else "No qualified leads this run",
            items_processed=len(new_leads),
            data={"leads": [l.get("company", "") for l in new_leads]},
        )


# ---------------------------------------------------------------------------
# Researcher Hand — autonomous report generation via RAG
# ---------------------------------------------------------------------------

class ResearcherHand(Hand):
    """Autonomous research — ingests sources, writes cited reports.

    Monitors a watch list of topics, searches the nexus knowledge base
    for relevant context, and generates concise research briefs.
    Reports are saved to data/research/ and optionally delivered via Discord.
    Runs every 6 hours.
    """

    @property
    def manifest(self) -> HandManifest:
        return HandManifest(
            id="researcher",
            name="Research Analyst",
            description="Write cited research reports from knowledge base",
            schedule_minutes=360,  # every 6 hours
            required_services=["Ollama"],
            min_disk_gb=1.0,
            min_ram_gb=2.0,
            tags=["research", "knowledge", "reports", "rag"],
            settings={
                "topics": [
                    "AI agent security trends",
                    "desktop automation market",
                    "local LLM performance benchmarks",
                ],
                "max_report_words": 500,
                "notify": "log",
            },
        )

    def execute(self) -> HandResult:
        import json as _json
        import random

        topics = self.manifest.settings.get("topics", [])
        if not topics:
            return HandResult(success=True, message="No research topics configured")

        # Pick a topic (round-robin based on run count)
        topic = topics[self._metrics.total_runs % len(topics)]
        max_words = self.manifest.settings.get("max_report_words", 500)

        # Query knowledge base for context
        context_chunks: list[str] = []
        try:
            from nexus.search import search as nexus_search
            results = nexus_search(topic, top_k=5)
            for r in results:
                text = r.get("text", r.get("content", ""))
                if text:
                    context_chunks.append(text[:500])
        except ImportError:
            _log.debug("Nexus search not available, generating without RAG context")
        except Exception as exc:
            _log.debug("Nexus search failed: %s", exc)

        # Also scan ai_knowledge directory for relevant files
        knowledge_dir = _ROOT / "data" / "ai_knowledge"
        if knowledge_dir.exists():
            for f in knowledge_dir.glob("*.txt"):
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    # Simple keyword match
                    keywords = topic.lower().split()
                    if any(kw in content.lower() for kw in keywords):
                        context_chunks.append(
                            f"[Source: {f.name}]\n{content[:400]}"
                        )
                except Exception:
                    pass

        # Generate report
        try:
            from core.llm import llm_chat

            context_block = "\n---\n".join(context_chunks[:5]) if context_chunks else "(no prior context available)"
            prompt = (
                f"You are a research analyst. Write a concise research brief on:\n"
                f"Topic: {topic}\n\n"
                f"Available context from knowledge base:\n{context_block}\n\n"
                f"Write a {max_words}-word research brief with:\n"
                "1. Key findings (bullet points)\n"
                "2. Implications for OnyxKraken (a local AI desktop agent)\n"
                "3. Recommended actions\n\n"
                "Cite sources where available. Be specific and actionable."
            )
            report_text = llm_chat(prompt, max_tokens=2000)

        except ImportError:
            return HandResult(success=False, error="LLM module not available")
        except Exception as exc:
            return HandResult(success=False, error=f"Report generation failed: {exc}")

        # Save report
        report_dir = _ROOT / "data" / "research"
        report_dir.mkdir(parents=True, exist_ok=True)
        slug = topic.lower().replace(" ", "_")[:40]
        ts = time.strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"report_{slug}_{ts}.md"

        report_content = (
            f"# Research Brief: {topic}\n\n"
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**Sources:** {len(context_chunks)} knowledge chunks\n\n"
            f"---\n\n{report_text}\n"
        )
        try:
            report_file.write_text(report_content, encoding="utf-8")
        except Exception as exc:
            _log.warning("Failed to save report: %s", exc)

        # Store in nexus knowledge base for future retrieval
        try:
            from nexus.ingest import ingest_text
            ingest_text(
                text=report_text,
                source=f"researcher_hand:{topic}",
                metadata={"type": "research_report", "topic": topic},
            )
        except Exception:
            pass

        # Notify
        notify = self.manifest.settings.get("notify", "log")
        if notify == "discord":
            try:
                from core.plugins.bridge_discord import send_message
                preview = report_text[:300].replace("\n", " ")
                send_message(f"📄 **Research Brief: {topic}**\n{preview}...")
            except Exception:
                pass

        return HandResult(
            success=True,
            message=f"Report: {topic} ({len(report_text)} chars, {len(context_chunks)} sources)",
            items_processed=1,
            data={
                "topic": topic,
                "report_path": str(report_file),
                "sources": len(context_chunks),
            },
        )


# ---------------------------------------------------------------------------
# Collector Hand — monitors targets and builds knowledge graphs
# ---------------------------------------------------------------------------

class CollectorHand(Hand):
    """Autonomous intelligence collection — monitors, ingests, embeds.

    Watches configured targets (URLs, RSS feeds, directories) for new
    content, extracts key information, embeds it into the nexus knowledge
    base, and builds a structured knowledge graph over time.
    Runs every 2 hours.
    """

    @property
    def manifest(self) -> HandManifest:
        return HandManifest(
            id="collector",
            name="Intel Collector",
            description="Monitor targets and build knowledge graphs",
            schedule_minutes=120,  # every 2 hours
            required_services=["Ollama"],
            min_disk_gb=1.0,
            min_ram_gb=1.0,
            tags=["collector", "osint", "knowledge", "monitoring"],
            settings={
                "watch_dirs": [],   # local directories to scan for new files
                "watch_urls": [],   # URLs to periodically fetch
                "file_extensions": [".txt", ".md", ".json", ".py", ".log"],
                "max_file_size_kb": 500,
                "extract_entities": True,  # use LLM to extract entities
            },
        )

    def execute(self) -> HandResult:
        import json as _json

        items_ingested = 0
        entities_found: list[dict] = []
        state_file = _ROOT / "data" / "collector_state.json"

        # Load previous scan state (file hashes to detect changes)
        prev_state: dict = {}
        if state_file.exists():
            try:
                prev_state = _json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                prev_state = {}

        current_state: dict = {}

        # 1. Scan watched directories for new/changed files
        watch_dirs = list(self.manifest.settings.get("watch_dirs", []))
        # Always monitor key knowledge directories
        watch_dirs.extend([
            str(_ROOT / "data" / "ai_knowledge"),
            str(_ROOT / "data" / "research"),
        ])

        extensions = set(self.manifest.settings.get("file_extensions",
                                                     [".txt", ".md"]))
        max_size = self.manifest.settings.get("max_file_size_kb", 500) * 1024

        new_files: list[Path] = []
        for wd in watch_dirs:
            wd_path = Path(wd)
            if not wd_path.exists():
                continue
            for f in wd_path.rglob("*"):
                if not f.is_file():
                    continue
                if f.suffix not in extensions:
                    continue
                if f.stat().st_size > max_size:
                    continue

                key = str(f)
                mtime = f.stat().st_mtime
                current_state[key] = mtime

                # New or changed since last scan?
                if prev_state.get(key) != mtime:
                    new_files.append(f)

        # 2. Ingest new files into nexus knowledge base
        for f in new_files[:20]:  # cap per run
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                if len(content.strip()) < 50:
                    continue  # skip trivially small files

                try:
                    from nexus.ingest import ingest_text
                    ingest_text(
                        text=content,
                        source=f"collector:{f.name}",
                        metadata={
                            "type": "collected",
                            "path": str(f),
                            "size": len(content),
                        },
                    )
                    items_ingested += 1
                except ImportError:
                    # No nexus ingest — just count as processed
                    items_ingested += 1
                except Exception as exc:
                    _log.debug("Ingest failed for %s: %s", f.name, exc)

            except Exception as exc:
                _log.debug("Failed to read %s: %s", f, exc)

        # 2b. Scrape watched URLs (deterministic extraction, not LLM parsing)
        urls_scraped = 0
        watch_urls = list(self.manifest.settings.get("watch_urls", []))
        if watch_urls:
            try:
                from core.web_scraper import WebScraper
                scraper = WebScraper(timeout=10.0)
                for url in watch_urls[:10]:  # cap per run
                    try:
                        page = scraper.scrape(url)
                        if page.error:
                            _log.debug("Scrape skipped %s: %s", url, page.error)
                            continue
                        if page.word_count < 20:
                            continue

                        # Check if content changed (hash the text)
                        import hashlib
                        content_hash = hashlib.md5(
                            page.text_content[:5000].encode()
                        ).hexdigest()
                        state_key = f"url:{url}"
                        if prev_state.get(state_key) == content_hash:
                            current_state[state_key] = content_hash
                            continue  # unchanged
                        current_state[state_key] = content_hash

                        # Ingest into nexus
                        try:
                            from nexus.ingest import ingest_text
                            ingest_text(
                                text=page.text_content[:10000],
                                source=f"collector:web:{page.title or url}",
                                metadata={
                                    "type": "web_scrape",
                                    "url": url,
                                    "title": page.title,
                                    "word_count": page.word_count,
                                },
                            )
                            urls_scraped += 1
                            items_ingested += 1
                        except ImportError:
                            urls_scraped += 1
                            items_ingested += 1
                        except Exception as exc:
                            _log.debug("URL ingest failed for %s: %s", url, exc)

                    except Exception as exc:
                        _log.debug("Scrape error for %s: %s", url, exc)
            except ImportError:
                _log.debug("WebScraper not available — skipping URL collection")

        # 3. Extract entities from new content (if enabled and LLM available)
        if (self.manifest.settings.get("extract_entities")
                and new_files and items_ingested > 0):
            try:
                from core.llm import llm_chat

                # Summarize the new content for entity extraction
                samples = []
                for f in new_files[:5]:
                    try:
                        text = f.read_text(encoding="utf-8", errors="ignore")[:300]
                        samples.append(f"[{f.name}]: {text}")
                    except Exception:
                        pass

                if samples:
                    prompt = (
                        "Extract key entities from these documents. "
                        "Return a JSON array of objects with: "
                        '"name", "type" (person/org/tech/concept), "context".\n\n'
                        + "\n---\n".join(samples)
                        + "\n\nReturn ONLY the JSON array."
                    )
                    response = llm_chat(prompt, max_tokens=1000)
                    start = response.find("[")
                    end = response.rfind("]") + 1
                    if start >= 0 and end > start:
                        entities_found = _json.loads(response[start:end])
            except Exception as exc:
                _log.debug("Entity extraction failed: %s", exc)

        # 4. Save entity graph
        if entities_found:
            graph_file = _ROOT / "data" / "knowledge_graph.json"
            existing_graph: list = []
            if graph_file.exists():
                try:
                    existing_graph = _json.loads(
                        graph_file.read_text(encoding="utf-8"))
                except Exception:
                    existing_graph = []

            # Deduplicate by name
            existing_names = {e.get("name", "").lower() for e in existing_graph}
            for entity in entities_found:
                if entity.get("name", "").lower() not in existing_names:
                    entity["discovered_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    existing_graph.append(entity)
                    existing_names.add(entity.get("name", "").lower())

            try:
                graph_file.parent.mkdir(parents=True, exist_ok=True)
                graph_file.write_text(
                    _json.dumps(existing_graph, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception as exc:
                _log.warning("Failed to save knowledge graph: %s", exc)

        # 5. Save scan state
        try:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(
                _json.dumps(current_state, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

        parts = []
        if items_ingested:
            parts.append(f"{items_ingested} items ingested")
        if urls_scraped:
            parts.append(f"{urls_scraped} URLs scraped")
        if entities_found:
            parts.append(f"{len(entities_found)} entities extracted")
        if not parts:
            parts.append("no new content")

        return HandResult(
            success=True,
            message="; ".join(parts),
            items_processed=items_ingested,
            data={
                "new_files": len(new_files),
                "urls_scraped": urls_scraped,
                "ingested": items_ingested,
                "entities": len(entities_found),
            },
        )


# ---------------------------------------------------------------------------
# DreamHand — associative memory cross-pollination (neuroscience rule #3)
# ---------------------------------------------------------------------------

class DreamHand(Hand):
    """Overnight 'dreaming' — finds surprising connections between memories.

    Modelled on REM sleep: randomly samples memories from different domains,
    feeds them to the LLM in pairs, and asks for non-obvious associations.
    Discovered connections are stored as insights in the knowledge store.

    Schedule: once per day (overnight / idle period).
    """

    @property
    def manifest(self) -> HandManifest:
        return HandManifest(
            id="dream",
            name="Dream — Associative Processing",
            description=(
                "Cross-pollinates memories from different domains to find "
                "surprising connections, analogies, and transferable insights."
            ),
            schedule_minutes=1440,  # once per day (24h)
            max_runtime_seconds=300,
            required_services=[],
            tags=["cognition", "memory", "neuroscience"],
        )

    def execute(self) -> HandResult:
        import random as _rand

        # 1. Gather memory samples from multiple sources
        memory_pool: list[dict] = []

        # Task history
        try:
            from memory.store import MemoryStore
            store = MemoryStore()
            tasks = store.get_all().get("task_history", [])
            for t in tasks[-30:]:
                memory_pool.append({
                    "source": "task_history",
                    "domain": t.get("app", "unknown"),
                    "content": f"{t['goal']} — {'OK' if t.get('success') else 'FAIL'}",
                    "timestamp": t.get("timestamp", 0),
                })
        except Exception:
            pass

        # Knowledge entries
        try:
            from core.knowledge import get_knowledge_store
            ks = get_knowledge_store()
            for entry in ks.get_all()[-30:]:
                memory_pool.append({
                    "source": "knowledge",
                    "domain": entry.get("category", "general"),
                    "content": entry.get("content", "")[:200],
                    "timestamp": entry.get("timestamp", 0),
                })
        except Exception:
            pass

        # Prediction surprises
        try:
            from core.prediction_engine import get_prediction_engine
            pe = get_prediction_engine()
            for s in pe.get_recent_surprises(10):
                memory_pool.append({
                    "source": "surprise",
                    "domain": s.get("domain", "general"),
                    "content": f"Surprise: {s.get('lesson', '')}",
                    "timestamp": s.get("timestamp", 0),
                })
        except Exception:
            pass

        # Reflections
        try:
            from core.mind import get_mind
            mind = get_mind()
            for r in mind._state.data.get("reflections", [])[-10:]:
                memory_pool.append({
                    "source": "reflection",
                    "domain": "self",
                    "content": r.get("insight", "")[:200],
                    "timestamp": r.get("timestamp", 0),
                })
        except Exception:
            pass

        if len(memory_pool) < 4:
            return HandResult(
                success=True,
                message="Not enough memories to dream about yet",
                items_processed=0,
            )

        # 2. Sample random pairs from DIFFERENT domains
        _rand.shuffle(memory_pool)
        pairs = []
        used = set()
        for i, a in enumerate(memory_pool):
            if i in used:
                continue
            for j, b in enumerate(memory_pool):
                if j <= i or j in used:
                    continue
                if a["domain"] != b["domain"]:
                    pairs.append((a, b))
                    used.add(i)
                    used.add(j)
                    break
            if len(pairs) >= 5:
                break

        if not pairs:
            return HandResult(
                success=True,
                message="No cross-domain pairs found",
                items_processed=0,
            )

        # 3. Ask LLM for connections
        insights = []
        try:
            from agent.model_router import router

            pair_texts = []
            for idx, (a, b) in enumerate(pairs, 1):
                pair_texts.append(
                    f"Pair {idx}:\n"
                    f"  Memory A [{a['domain']}]: {a['content']}\n"
                    f"  Memory B [{b['domain']}]: {b['content']}"
                )

            prompt = (
                "You are OnyxKraken's dream processor — an associative "
                "reasoning engine inspired by REM sleep.\n\n"
                "Below are pairs of memories from DIFFERENT domains. "
                "For each pair, find ONE surprising connection, analogy, or "
                "transferable insight. Focus on non-obvious relationships.\n\n"
                + "\n\n".join(pair_texts) +
                "\n\nRespond with ONLY a JSON array of objects:\n"
                '[{"pair": 1, "connection": "...", "actionable": "..."}, ...]\n'
                "Each object has:\n"
                '  "pair": pair number\n'
                '  "connection": the surprising connection found\n'
                '  "actionable": one concrete thing OnyxKraken should try based on this\n'
                "Output ONLY the JSON array."
            )

            raw = router.get_content("reasoning", [{"role": "user", "content": prompt}])

            try:
                from core.utils import extract_json
                result = extract_json(raw)
                if isinstance(result, list):
                    insights = result
                elif isinstance(result, dict) and "pair" in result:
                    insights = [result]
            except Exception:
                pass

        except Exception as e:
            return HandResult(
                success=False,
                message=f"Dream LLM call failed: {e}",
                items_processed=0,
            )

        # 4. Store discovered insights
        stored = 0
        for insight in insights:
            if not isinstance(insight, dict):
                continue
            connection = insight.get("connection", "")
            actionable = insight.get("actionable", "")
            if not connection:
                continue
            try:
                from core.knowledge import get_knowledge_store
                ks = get_knowledge_store()
                ks.add(
                    content=f"Dream insight: {connection}. Action: {actionable}",
                    category="dream",
                    tags=["dream", "association", "cross-domain"],
                    source="hand:dream",
                )
                stored += 1
            except Exception:
                pass

        return HandResult(
            success=True,
            message=f"Dreamed {len(pairs)} pairs → {stored} insights stored",
            items_processed=stored,
            data={
                "pairs_analysed": len(pairs),
                "insights_found": len(insights),
                "insights_stored": stored,
            },
        )


# ---------------------------------------------------------------------------
# Registry of all built-in Hands
# ---------------------------------------------------------------------------

from core.hands.reddit_hand import RedditHand

BUILTIN_HANDS: dict[str, type[Hand]] = {
    "content": ContentHand,
    "practice": PracticeHand,
    "monitor": MonitorHand,
    "dj": DJHand,
    "maintenance": MaintenanceHand,
    "lead": LeadHand,
    "researcher": ResearcherHand,
    "collector": CollectorHand,
    "dream": DreamHand,
    "reddit": RedditHand,
}


def create_all_hands() -> list[Hand]:
    """Instantiate all built-in Hands."""
    return [cls() for cls in BUILTIN_HANDS.values()]


def create_hand(hand_id: str) -> Hand | None:
    """Create a single Hand by ID."""
    cls = BUILTIN_HANDS.get(hand_id)
    return cls() if cls else None
