"""Content Component — social media content creation and publishing.

Wraps the ContentCreationSkill behind the unified OnyxComponent interface.
Handles research, writing, scheduling, publishing, and analytics across
all platforms (Twitter, Reddit, YouTube, LinkedIn, Blog).

Capabilities:
    - Research trending topics
    - Generate platform-specific content
    - Schedule posts at optimal times
    - Publish to social media APIs
    - Track analytics and learn
    - Repurpose content across platforms
"""

import logging
from typing import Dict, List, Optional

from core.components.base import (
    OnyxComponent, ComponentResult, ComponentStatus, ActionDescriptor,
)

_log = logging.getLogger("components.content")


class ContentComponent(OnyxComponent):
    """Social media content creation and publishing component."""

    @property
    def name(self) -> str:
        return "content"

    @property
    def display_name(self) -> str:
        return "Content Creation"

    @property
    def description(self) -> str:
        return "Research, write, schedule, and publish social media content"

    @property
    def category(self) -> str:
        return "platform"

    def get_actions(self) -> List[ActionDescriptor]:
        return [
            ActionDescriptor(
                name="research_topics",
                description="Research trending topics in a niche",
                params=["niche", "platform", "count", "style"],
                required_params=["niche"],
                estimated_duration="seconds",
            ),
            ActionDescriptor(
                name="create_content",
                description="Generate platform-specific content",
                params=["topic", "platform", "style", "key_points", "brand_voice"],
                required_params=["topic", "platform"],
                estimated_duration="seconds",
            ),
            ActionDescriptor(
                name="create_thread",
                description="Generate a Twitter/X thread",
                params=["topic", "tweet_count"],
                required_params=["topic"],
                estimated_duration="seconds",
            ),
            ActionDescriptor(
                name="schedule",
                description="Schedule a post for publishing",
                params=["post_id", "scheduled_time", "auto_optimal"],
                estimated_duration="fast",
            ),
            ActionDescriptor(
                name="publish_due",
                description="Publish all posts that are due now",
                estimated_duration="seconds",
            ),
            ActionDescriptor(
                name="strategy_report",
                description="Generate a strategy report with insights",
                params=["days", "platform"],
                estimated_duration="seconds",
            ),
            ActionDescriptor(
                name="repurpose",
                description="Adapt content for multiple platforms",
                params=["content", "source_platform", "target_platforms"],
                required_params=["content", "source_platform"],
                estimated_duration="seconds",
            ),
            ActionDescriptor(
                name="pipeline",
                description="Full pipeline: research → create → review → schedule",
                params=["niche", "platform", "count", "auto_schedule", "brand_voice"],
                required_params=["niche", "platform"],
                estimated_duration="minutes",
            ),
        ]

    def health_check(self) -> Dict:
        missing = []
        try:
            from core.skills.content_creation.skill import ContentCreationSkill
        except ImportError:
            missing.append("content_creation skill not available")

        ready = len(missing) == 0
        self._status = ComponentStatus.READY if ready else ComponentStatus.UNAVAILABLE
        return {
            "ready": ready,
            "status": str(self._status),
            "missing": missing,
            "message": "Content creation ready" if ready else f"Missing: {', '.join(missing)}",
        }

    def execute(self, action: str, params: Optional[Dict] = None) -> ComponentResult:
        params = params or {}
        skill = self._get_skill()
        if not skill:
            return ComponentResult(status="failed", error="ContentCreationSkill unavailable")

        try:
            result = skill.execute(action, params)
            ok = result.get("ok", False)
            return ComponentResult(
                status="done" if ok else "failed",
                output=result,
                error=result.get("error", "") if not ok else "",
                summary=self._make_summary(action, result),
            )
        except Exception as e:
            return ComponentResult(status="failed", error=str(e))

    def _get_skill(self):
        try:
            from core.skills.content_creation.skill import ContentCreationSkill
            return ContentCreationSkill()
        except Exception as e:
            _log.warning("ContentCreationSkill unavailable: %s", e)
            return None

    @staticmethod
    def _make_summary(action: str, result: Dict) -> str:
        """Generate a human-readable summary of the result."""
        if action == "research_topics":
            count = len(result.get("topics", []))
            return f"Found {count} topics"
        elif action == "create_content":
            return "Content created"
        elif action == "create_thread":
            return f"Thread created ({result.get('tweet_count', '?')} tweets)"
        elif action == "schedule":
            return "Post scheduled"
        elif action == "publish_due":
            return f"Published {result.get('published_count', 0)} posts"
        elif action == "strategy_report":
            return "Strategy report generated"
        elif action == "repurpose":
            return "Content repurposed"
        elif action == "pipeline":
            return "Full content pipeline completed"
        return f"Action '{action}' completed"
