"""Knowledge routes — CRUD and search for the knowledge store."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class KnowledgeAddRequest(BaseModel):
    content: str
    category: str = "general"
    tags: list[str] = []
    source: str = ""


class KnowledgeSearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    limit: int = 10


@router.post("/knowledge")
async def add_knowledge(req: KnowledgeAddRequest):
    """Add a knowledge entry."""
    from core.knowledge import get_knowledge_store
    store = get_knowledge_store()
    entry_id = store.add(req.content, category=req.category, tags=req.tags, source=req.source)
    return {"id": entry_id, "status": "added"}


@router.post("/knowledge/search")
async def search_knowledge(req: KnowledgeSearchRequest):
    """Search knowledge entries."""
    from core.knowledge import get_knowledge_store
    store = get_knowledge_store()
    results = store.search(req.query, category=req.category, tags=req.tags, limit=req.limit)
    return {"results": results, "count": len(results)}


@router.get("/knowledge/stats")
async def knowledge_stats():
    """Get knowledge store statistics."""
    from core.knowledge import get_knowledge_store
    store = get_knowledge_store()
    return store.get_stats()
