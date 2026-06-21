"""
Odysseus — Unified AI Platform
FastAPI Backend

Replaces:
- Flask app.py (1187 lines, 56 route files)
- Node.js VR backend (644 lines)
- Orchestrator Flask dashboard (5618 lines)
- Node.js AI Gateway (standalone)

Single unified backend with:
- FastAPI + async SQLAlchemy + Pydantic
- JWT auth with bcrypt
- LLM gateway (20+ providers via Vercel AI SDK + OpenAI-compatible)
- VR video library with face recognition
- Orchestrator task engine with cron jobs
- System monitoring (CPU, RAM, disk, GPU)
- WebSocket real-time endpoints
"""

import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import init_db, close_db

# Route imports
from backend.llm.gateway import router as llm_router
from backend.llm.chat import router as chat_router
from backend.video.library import router as video_router
from backend.video.faces import router as faces_router
from backend.video.stream import router as stream_router
from backend.agents.tasks import router as tasks_router
from backend.agents.cron import router as cron_router
from backend.agents.agents import router as agents_router
from backend.system.health import router as health_router
from backend.system.monitor import router as monitor_router

# WebSocket handlers
from backend.llm.websocket import ws_chat_endpoint, ws_tasks_endpoint, ws_system_endpoint

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("odysseus")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, models, services. Shutdown: cleanup."""
    log.info("Odysseus starting up...")

    # Initialize database
    await init_db()
    log.info("  Database: initialized")

    log.info(f"  LLM providers: {len(settings.LLM_PROVIDERS)} configured")
    log.info(f"  Default model: {settings.DEFAULT_MODEL}")
    log.info("Odysseus ready!")
    yield
    log.info("Odysseus shutting down...")
    await close_db()


app = FastAPI(
    title="Odysseus",
    version="2.0.0",
    description="Unified AI Platform — LLM Gateway, VR Video Library, Orchestrator",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── Middleware ──────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "internal server error", "detail": str(exc)},
    )


# ── Routes ─────────────────────────────────────────────────────────────

# System
app.include_router(health_router, prefix="/api/health", tags=["system"])
app.include_router(monitor_router, prefix="/api/system", tags=["system"])

# LLM & Chat
app.include_router(llm_router, prefix="/api/llm", tags=["llm"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])

# VR Video Library
app.include_router(video_router, prefix="/api/videos", tags=["video"])
app.include_router(faces_router, prefix="/api/faces", tags=["faces"])
app.include_router(stream_router, prefix="/api/stream", tags=["stream"])

# Orchestrator & Agents
app.include_router(tasks_router, prefix="/api/tasks", tags=["tasks"])
app.include_router(cron_router, prefix="/api/cron", tags=["cron"])
app.include_router(agents_router, prefix="/api/agents", tags=["agents"])

# ── WebSocket Endpoints ────────────────────────────────────────────────

@app.websocket("/api/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket streaming chat endpoint."""
    await ws_chat_endpoint(websocket)


@app.websocket("/api/ws/tasks")
async def websocket_tasks(websocket: WebSocket):
    """WebSocket real-time task status updates."""
    await ws_tasks_endpoint(websocket)


@app.websocket("/api/ws/system")
async def websocket_system(websocket: WebSocket):
    """WebSocket real-time system stats."""
    await ws_system_endpoint(websocket)


# ── Frontend SPA ───────────────────────────────────────────────────────

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@app.get("/api")
async def api_root():
    return {
        "name": "Odysseus API",
        "version": "2.0.0",
        "endpoints": [
            "/api/health",
            "/api/system",
            "/api/llm",
            "/api/llm/health",
            "/api/chat",
            "/api/chat/sessions",
            "/api/videos",
            "/api/faces",
            "/api/stream",
            "/api/tasks",
            "/api/cron",
            "/api/agents",
            "/api/ws/chat",
            "/api/ws/tasks",
            "/api/ws/system",
        ],
    }


# ── Frontend SPA Static Serving ───────────────────────────────────────

if FRONTEND_DIST.exists():
    # Mount static assets at /assets
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")
    # Mount SPA at root — serves index.html for any non-file path
    # This must be mounted LAST so API routes take priority
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="spa")
