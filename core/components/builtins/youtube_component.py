"""YouTube Component — strategic content creation and publishing.

Wraps the YouTube Strategy Engine and content creation skill behind
the unified OnyxComponent interface. Handles the full YouTube lifecycle:
plan → create → risk-check → publish → analyze.

Capabilities:
    - Strategic episode planning (growth-phase aware)
    - Demonetization risk assessment
    - Content mix analysis
    - Channel health reporting
    - Full autonomous publish pipeline
    - Platform upload via API or UI automation
"""

import logging
from typing import Dict, List, Optional

from core.components.base import (
    OnyxComponent, ComponentResult, ComponentStatus, ActionDescriptor,
)

_log = logging.getLogger("components.youtube")


class YouTubeComponent(OnyxComponent):
    """YouTube strategy and publishing component."""

    @property
    def name(self) -> str:
        return "youtube"

    @property
    def display_name(self) -> str:
        return "YouTube"

    @property
    def description(self) -> str:
        return "Strategic YouTube content planning, risk assessment, and publishing"

    @property
    def category(self) -> str:
        return "platform"

    def get_actions(self) -> List[ActionDescriptor]:
        return [
            ActionDescriptor(
                name="strategic_episode",
                description="Plan an episode using calculated strategy (not random)",
                params=["pillar", "topic"],
                estimated_duration="seconds",
            ),
            ActionDescriptor(
                name="strategic_pipeline",
                description="Full autonomous pipeline: research → plan → create → verify → publish",
                params=["pillar", "topic", "dry_run"],
                estimated_duration="long",
                risk_level="medium",
            ),
            ActionDescriptor(
                name="risk_check",
                description="Check content for demonetization risk before publishing",
                params=["title", "description", "topics", "has_profanity",
                        "controversial", "copyrighted"],
                required_params=["title"],
                estimated_duration="fast",
            ),
            ActionDescriptor(
                name="channel_report",
                description="Get strategic channel report (growth phase, health, tactics)",
                params=["metrics"],
                estimated_duration="fast",
            ),
            ActionDescriptor(
                name="content_mix",
                description="Analyze content mix vs ideal for current growth phase",
                estimated_duration="fast",
            ),
            ActionDescriptor(
                name="upload",
                description="Upload a video to YouTube",
                params=["video_path", "title", "description", "tags", "thumbnail"],
                required_params=["video_path", "title"],
                risk_level="high",
                estimated_duration="minutes",
            ),
            ActionDescriptor(
                name="fetch_analytics",
                description="Fetch latest YouTube analytics",
                estimated_duration="seconds",
            ),
        ]

    def health_check(self) -> Dict:
        missing = []
        try:
            from core.skills.content_creation.youtube_strategy import YouTubeStrategyEngine
        except ImportError:
            missing.append("youtube_strategy module not available")

        ready = len(missing) == 0
        self._status = ComponentStatus.READY if ready else ComponentStatus.UNAVAILABLE
        return {
            "ready": ready,
            "status": str(self._status),
            "missing": missing,
            "message": "YouTube component ready" if ready else f"Missing: {', '.join(missing)}",
        }

    def execute(self, action: str, params: Optional[Dict] = None) -> ComponentResult:
        params = params or {}

        if action == "strategic_episode":
            return self._strategic_episode(params)
        elif action == "strategic_pipeline":
            return self._strategic_pipeline(params)
        elif action == "risk_check":
            return self._risk_check(params)
        elif action == "channel_report":
            return self._channel_report(params)
        elif action == "content_mix":
            return self._content_mix()
        elif action == "upload":
            return self._upload(params)
        elif action == "fetch_analytics":
            return self._fetch_analytics()
        else:
            return ComponentResult(status="failed", error=f"Unknown action: {action}")

    def _get_skill(self):
        try:
            from core.skills.content_creation.skill import ContentCreationSkill
            return ContentCreationSkill()
        except Exception as e:
            _log.warning("ContentCreationSkill unavailable: %s", e)
            return None

    def _strategic_episode(self, params: Dict) -> ComponentResult:
        skill = self._get_skill()
        if not skill:
            return ComponentResult(status="failed", error="YouTube strategy unavailable")
        result = skill.execute("strategic_episode", params)
        plan = result.get("plan", {})
        return ComponentResult(
            status="done" if result.get("ok") else "failed",
            output=result,
            summary=f"Strategic episode planned: {plan.get('title', 'untitled')} [{plan.get('pillar', '')}]",
            chain_data={
                "episode_title": plan.get("title", ""),
                "episode_topic": plan.get("topic", ""),
                "episode_pillar": plan.get("pillar", ""),
            },
        )

    def _strategic_pipeline(self, params: Dict) -> ComponentResult:
        skill = self._get_skill()
        if not skill:
            return ComponentResult(status="failed", error="YouTube strategy unavailable")
        result = skill.execute("strategic_pipeline", params)
        return ComponentResult(
            status="done" if result.get("ok") else "failed",
            output=result,
            summary="Full strategic pipeline executed" if result.get("ok") else "Pipeline failed",
        )

    def _risk_check(self, params: Dict) -> ComponentResult:
        skill = self._get_skill()
        if not skill:
            return ComponentResult(status="failed", error="Strategy unavailable")
        result = skill.execute("risk_check", params)
        return ComponentResult(
            status="done",
            output=result,
            summary=f"Risk: {result.get('overall_risk', '?')} (score={result.get('score', 0):.2f}, safe={result.get('safe_to_publish', '?')})",
            chain_data={"risk_level": result.get("overall_risk", ""),
                        "safe_to_publish": result.get("safe_to_publish", False)},
        )

    def _channel_report(self, params: Dict) -> ComponentResult:
        skill = self._get_skill()
        if not skill:
            return ComponentResult(status="failed", error="Strategy unavailable")
        result = skill.execute("channel_report", params)
        phase = result.get("growth_phase", {})
        return ComponentResult(
            status="done" if result.get("ok") else "failed",
            output=result,
            summary=f"Channel: {phase.get('name', '?')} phase, health={result.get('health_score', 0):.0f}/100",
        )

    def _content_mix(self) -> ComponentResult:
        skill = self._get_skill()
        if not skill:
            return ComponentResult(status="failed", error="Strategy unavailable")
        result = skill.execute("content_mix", {})
        return ComponentResult(
            status="done" if result.get("ok") else "failed",
            output=result,
            summary=f"Content mix analysis for {result.get('phase', '?')} phase",
        )

    def _upload(self, params: Dict) -> ComponentResult:
        video_path = params.get("video_path", "")
        title = params.get("title", "")
        if not video_path or not title:
            return ComponentResult(status="failed", error="video_path and title required")

        # Try API first, fall back to UI automation guidance
        try:
            from core.skills.content_creation.platforms.youtube import YouTubePlatform
            yt = YouTubePlatform()
            if yt.is_configured():
                yt.authenticate()
                result = yt.upload_video(
                    video_path=video_path,
                    title=title,
                    description=params.get("description", ""),
                    tags=params.get("tags", []),
                )
                return ComponentResult(
                    status="done",
                    output=result if isinstance(result, dict) else {"url": str(result)},
                    summary=f"Uploaded: {title}",
                    chain_data={"youtube_url": result.get("url", "") if isinstance(result, dict) else ""},
                )
        except Exception as e:
            _log.info("YouTube API unavailable (%s), would need UI automation", e)

        return ComponentResult(
            status="done",
            output={
                "video_path": video_path,
                "title": title,
                "method": "ui_automation_needed",
                "note": "YouTube API not configured. Use TeachMe to learn the upload UI.",
            },
            summary=f"Video ready for upload: {title} (API not configured — use TeachMe for UI)",
        )

    def _fetch_analytics(self) -> ComponentResult:
        skill = self._get_skill()
        if not skill:
            return ComponentResult(status="failed", error="Analytics unavailable")
        result = skill.execute("fetch_analytics")
        return ComponentResult(
            status="done" if result.get("ok") else "failed",
            output=result,
            summary="Analytics fetched",
        )
