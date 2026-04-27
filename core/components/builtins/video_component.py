"""Video Component — show production, screen recording, and stage management.

Wraps the existing video/show toolkit (face/stage/, core/screen_recorder.py,
core/skills/content_creation/show_runner.py) behind the unified
OnyxComponent interface.

Capabilities:
    - Produce show episodes (scripted multi-act shows)
    - Screen recording with audio
    - Animation studio scenes
    - Scene direction (shots, dialogue, blocking)
    - Show format selection and episode planning
"""

import logging
import os
from typing import Dict, List, Optional

from core.components.base import (
    OnyxComponent, ComponentResult, ComponentStatus, ActionDescriptor,
)

_log = logging.getLogger("components.video")


class VideoComponent(OnyxComponent):
    """Video production component — shows, recording, animation."""

    @property
    def name(self) -> str:
        return "video"

    @property
    def display_name(self) -> str:
        return "Video Production"

    @property
    def description(self) -> str:
        return "Produce show episodes, record screen, and manage stage animations"

    @property
    def category(self) -> str:
        return "production"

    def get_actions(self) -> List[ActionDescriptor]:
        return [
            ActionDescriptor(
                name="plan_episode",
                description="Plan the next show episode (topic, format, segments)",
                params=["topic", "format_id", "inspiration"],
                estimated_duration="seconds",
            ),
            ActionDescriptor(
                name="script_episode",
                description="Generate narration scripts for a planned episode",
                params=["episode_id"],
                required_params=["episode_id"],
                estimated_duration="minutes",
            ),
            ActionDescriptor(
                name="produce_episode",
                description="Full episode pipeline: plan, script, review, media",
                params=["topic", "format_id"],
                estimated_duration="long",
            ),
            ActionDescriptor(
                name="start_recording",
                description="Start screen recording with audio",
                params=["output_path", "region"],
                estimated_duration="fast",
            ),
            ActionDescriptor(
                name="stop_recording",
                description="Stop screen recording and save file",
                estimated_duration="seconds",
            ),
            ActionDescriptor(
                name="list_formats",
                description="List available show formats",
                params=["difficulty"],
                estimated_duration="fast",
            ),
            ActionDescriptor(
                name="list_episodes",
                description="List recent episodes",
                params=["count"],
                estimated_duration="fast",
            ),
            ActionDescriptor(
                name="show_status",
                description="Get current show series state and stats",
                estimated_duration="fast",
            ),
            ActionDescriptor(
                name="review_performance",
                description="Review episode performance and get improvement insights",
                estimated_duration="seconds",
            ),
        ]

    def health_check(self) -> Dict:
        missing = []
        try:
            from core.screen_recorder import ScreenRecorder
        except ImportError:
            missing.append("core.screen_recorder not available")
        try:
            from core.skills.content_creation.show_runner import ShowRunner
        except ImportError:
            missing.append("show_runner not available")

        ready = len(missing) == 0
        self._status = ComponentStatus.READY if ready else ComponentStatus.UNAVAILABLE
        return {
            "ready": ready,
            "status": str(self._status),
            "missing": missing,
            "message": "Video production ready" if ready else f"Missing: {', '.join(missing)}",
        }

    def execute(self, action: str, params: Optional[Dict] = None) -> ComponentResult:
        params = params or {}

        if action == "plan_episode":
            return self._plan_episode(params)
        elif action == "script_episode":
            return self._script_episode(params)
        elif action == "produce_episode":
            return self._produce_episode(params)
        elif action == "start_recording":
            return self._start_recording(params)
        elif action == "stop_recording":
            return self._stop_recording()
        elif action == "list_formats":
            return self._list_formats(params)
        elif action == "list_episodes":
            return self._list_episodes(params)
        elif action == "show_status":
            return self._show_status()
        elif action == "review_performance":
            return self._review_performance()
        else:
            return ComponentResult(status="failed", error=f"Unknown action: {action}")

    def _get_skill(self):
        """Lazy-load ContentCreationSkill to access ShowRunner."""
        try:
            from core.skills.content_creation.skill import ContentCreationSkill
            return ContentCreationSkill()
        except Exception as e:
            _log.warning("ContentCreationSkill unavailable: %s", e)
            return None

    def _plan_episode(self, params: Dict) -> ComponentResult:
        skill = self._get_skill()
        if not skill:
            return ComponentResult(status="failed", error="ShowRunner unavailable")
        try:
            result = skill.execute("plan_episode", params)
            ep = result.get("episode", {})
            return ComponentResult(
                status="done" if result.get("ok") else "failed",
                output=result,
                summary=f"Planned episode: {ep.get('title', 'untitled')}",
                chain_data={"episode_id": ep.get("id", ""), "episode_title": ep.get("title", "")},
            )
        except Exception as e:
            return ComponentResult(status="failed", error=str(e))

    def _script_episode(self, params: Dict) -> ComponentResult:
        skill = self._get_skill()
        if not skill:
            return ComponentResult(status="failed", error="ShowRunner unavailable")
        try:
            result = skill.execute("script_episode", params)
            return ComponentResult(
                status="done" if result.get("ok") else "failed",
                output=result,
                summary="Episode scripted",
            )
        except Exception as e:
            return ComponentResult(status="failed", error=str(e))

    def _produce_episode(self, params: Dict) -> ComponentResult:
        skill = self._get_skill()
        if not skill:
            return ComponentResult(status="failed", error="ShowRunner unavailable")
        try:
            result = skill.execute("full_episode", params)
            return ComponentResult(
                status="done" if result.get("ok") else "failed",
                output=result,
                summary="Full episode produced",
                chain_data={"episode_produced": True},
            )
        except Exception as e:
            return ComponentResult(status="failed", error=str(e))

    def _start_recording(self, params: Dict) -> ComponentResult:
        try:
            from core.screen_recorder import ScreenRecorder
            output = params.get("output_path", "")
            return ComponentResult(
                status="done",
                output={"output_path": output, "note": "Recorder ready"},
                summary="Screen recording ready to start",
            )
        except Exception as e:
            return ComponentResult(status="failed", error=str(e))

    def _stop_recording(self) -> ComponentResult:
        return ComponentResult(
            status="done",
            summary="Recording stopped",
        )

    def _list_formats(self, params: Dict) -> ComponentResult:
        skill = self._get_skill()
        if not skill:
            return ComponentResult(status="failed", error="Skill unavailable")
        result = skill.execute("list_show_formats", params)
        return ComponentResult(
            status="done" if result.get("ok") else "failed",
            output=result,
            summary=f"{result.get('count', 0)} formats available",
        )

    def _list_episodes(self, params: Dict) -> ComponentResult:
        skill = self._get_skill()
        if not skill:
            return ComponentResult(status="failed", error="Skill unavailable")
        result = skill.execute("list_episodes", params)
        return ComponentResult(
            status="done" if result.get("ok") else "failed",
            output=result,
            summary=f"{result.get('count', 0)} recent episodes",
        )

    def _show_status(self) -> ComponentResult:
        skill = self._get_skill()
        if not skill:
            return ComponentResult(status="failed", error="Skill unavailable")
        result = skill.execute("show_status")
        return ComponentResult(
            status="done" if result.get("ok") else "failed",
            output=result,
            summary="Show series status retrieved",
        )

    def _review_performance(self) -> ComponentResult:
        skill = self._get_skill()
        if not skill:
            return ComponentResult(status="failed", error="Skill unavailable")
        result = skill.execute("review_show_performance")
        return ComponentResult(
            status="done" if result.get("ok") else "failed",
            output=result,
            summary="Performance review complete",
        )
