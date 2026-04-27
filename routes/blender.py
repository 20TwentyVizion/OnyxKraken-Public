"""Blender routes — review, curriculum, research."""

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


# ---------------------------------------------------------------------------
# Blender Review endpoints
# ---------------------------------------------------------------------------

@router.get("/review/scan")
async def review_scan():
    """Scan OnyxProjects for .blend files."""
    from addons.blender.review import get_reviewer
    inventory = get_reviewer().scan_projects()
    return {"files": inventory, "count": len(inventory)}


@router.get("/review/stats")
async def review_stats():
    """Get review statistics."""
    from addons.blender.review import get_reviewer
    return get_reviewer().get_stats()


@router.get("/review/worst")
async def review_worst(count: int = 5):
    """Get the lowest-scoring reviewed files."""
    from addons.blender.review import get_reviewer
    return {"files": get_reviewer().get_worst_files(count)}


class ReviewFileRequest(BaseModel):
    blend_path: str = Field(..., description="Path to .blend file to review")


@router.post("/review/file")
async def review_file(req: ReviewFileRequest):
    """Review a single .blend file — render, analyze, score."""
    from addons.blender.review import get_reviewer
    result = await asyncio.to_thread(get_reviewer().review_file, req.blend_path)
    return result


# ---------------------------------------------------------------------------
# Blender Curriculum endpoints
# ---------------------------------------------------------------------------

@router.get("/curriculum")
async def curriculum_progress():
    """Get full curriculum progress — levels, exercises, scores."""
    from addons.blender.curriculum import get_curriculum
    return get_curriculum().get_progress()


@router.get("/curriculum/next")
async def curriculum_next():
    """Get the next exercise to attempt."""
    from addons.blender.curriculum import get_curriculum
    ex = get_curriculum().next_exercise()
    if ex:
        return {"exercise": {"id": ex["id"], "name": ex["name"],
                             "level": ex["level"], "prompt": ex["prompt"]}}
    return {"exercise": None, "message": "All exercises at current level complete!"}


class CurriculumResultRequest(BaseModel):
    exercise_id: str
    score: float
    passed: bool
    feedback: str = ""


@router.post("/curriculum/result")
async def curriculum_record_result(req: CurriculumResultRequest):
    """Record the result of an exercise attempt."""
    from addons.blender.curriculum import get_curriculum
    curr = get_curriculum()
    curr.record_result(req.exercise_id, req.score, req.passed, req.feedback)
    return {"status": "recorded", "progress": curr.get_stats_summary()}


# ---------------------------------------------------------------------------
# Blender Research endpoints
# ---------------------------------------------------------------------------

class YouTubeResearchRequest(BaseModel):
    video_url: str = Field(..., description="YouTube video URL")
    topic: str = Field(default="", description="Research topic for context")


@router.post("/research/youtube")
async def research_youtube(req: YouTubeResearchRequest):
    """Fetch a YouTube transcript, extract Blender techniques, store in knowledge."""
    from addons.blender.research import research_youtube_video
    result = await asyncio.to_thread(
        research_youtube_video, req.video_url, req.topic
    )
    return result


class TopicResearchRequest(BaseModel):
    topic: str = Field(..., description="Blender topic to research")
    video_urls: list[str] = Field(default=[], description="YouTube video URLs to process")
    max_videos: int = Field(default=3, description="Max videos to process")


@router.post("/research/topic")
async def research_topic(req: TopicResearchRequest):
    """Research a Blender topic from multiple YouTube tutorials."""
    from addons.blender.research import research_topic as _research_topic
    result = await asyncio.to_thread(
        _research_topic, req.topic, req.video_urls, req.max_videos
    )
    return result
