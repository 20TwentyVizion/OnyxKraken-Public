"""OnyxKraken API Server — FastAPI layer for programmatic access.

Route modules are in routes/:
  routes/agent.py       — goal, status, history, run, queue, skills, memory
  routes/daemon.py      — daemon control, focus, improve
  routes/analytics.py   — /api/learning, benchmarks, meta-metric
  routes/blender.py     — review, curriculum, research
  routes/knowledge.py   — knowledge CRUD + search
  routes/voice_mind.py  — voice I/O + mind state/reflection

Usage:
  uvicorn server:app --host 0.0.0.0 --port 8420 --reload

Security:
  Set ONYX_API_TOKEN in .env to require Bearer token auth on all endpoints.
  If not set, auth is skipped (local development mode).
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routes.agent import router as agent_router
from routes.daemon import router as daemon_router
from routes.analytics import router as analytics_router
from routes.blender import router as blender_router
from routes.knowledge import router as knowledge_router
from routes.voice_mind import router as voice_mind_router
from routes.ecosystem import router as ecosystem_router
from routes.face_packs import router as face_packs_router
from routes.face_customize import router as face_customize_router
from routes.drive import router as drive_router


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_API_TOKEN = os.environ.get("ONYX_API_TOKEN", "")

_ALLOWED_ORIGINS = [
    "http://localhost:5173",       # Vite dev server
    "http://localhost:4173",       # Vite preview
    "http://127.0.0.1:5173",
    "http://127.0.0.1:4173",
    "https://onyxkraken-face.netlify.app",
]


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    if _API_TOKEN:
        print("[Server] OnyxKraken API starting (token auth ENABLED)...")
    else:
        print("[Server] OnyxKraken API starting (no auth — set ONYX_API_TOKEN to secure)...")
    yield
    print("[Server] OnyxKraken API shutting down.")


app = FastAPI(
    title="OnyxKraken API",
    description="Programmatic interface to the OnyxKraken desktop automation agent",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Bearer token auth when ONYX_API_TOKEN is set."""
    if not _API_TOKEN:
        return await call_next(request)
    if request.url.path in ("/docs", "/openapi.json", "/redoc"):
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {_API_TOKEN}":
        return await call_next(request)
    return JSONResponse(status_code=401, content={"detail": "Unauthorized"})


@app.get("/health")
async def health_check():
    """Health check endpoint — always returns 200."""
    return {"status": "ok"}


# Include all route modules
app.include_router(agent_router)
app.include_router(daemon_router)
app.include_router(analytics_router)
app.include_router(blender_router)
app.include_router(knowledge_router)
app.include_router(voice_mind_router)
app.include_router(ecosystem_router)
app.include_router(face_packs_router)
app.include_router(face_customize_router)
app.include_router(drive_router)
