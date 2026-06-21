"""Database — async SQLAlchemy with SQLite.
Supports two databases:
  1. Main Odysseus DB (odysseus.db) — tasks, chat, settings, video library, face clusters
  2. VR Video DB (videos.db) — read-only connection to the legacy VR video database
"""

import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from backend.config import settings

log = logging.getLogger("db")

# ── Main Odysseus DB ────────────────────────────────────────────────────
engine = None
async_session = None

# ── VR Video Read-Only DB ──────────────────────────────────────────────
vr_engine = None
vr_async_session = None


class Base(DeclarativeBase):
    pass


# ── Models ──────────────────────────────────────────────────────────────

class Video(Base):
    __tablename__ = "videos"
    id = Column(String, primary_key=True)
    title = Column(String)
    source = Column(String)
    url = Column(String)
    thumbnail = Column(String)
    duration = Column(Float, default=0)
    file_size = Column(Integer, default=0)
    resolution = Column(String, default="")
    fps = Column(Float, default=0)
    codec = Column(String, default="")
    tags = Column(JSON, default=list)
    rating = Column(Float, default=0)
    play_count = Column(Integer, default=0)
    last_played = Column(DateTime, nullable=True)
    is_favorite = Column(Boolean, default=False)
    projection = Column(String, default="flat")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VideoSource(Base):
    """Maps videos from the legacy VR video database (read-only view)."""
    __tablename__ = "vr_videos"
    id = Column(String, primary_key=True)
    title = Column(String)
    external_url = Column(String)
    source_type = Column(String)
    category = Column(String)
    duration = Column(Integer, default=0)
    thumbnail_url = Column(String)
    embed_url = Column(String)
    resolved_stream_url = Column(String)
    projection = Column(String, default="flat")
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    dead_count = Column(Integer, default=0)
    created_at = Column(String)
    updated_at = Column(String)


class Performer(Base):
    __tablename__ = "performers"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    thumbnail = Column(String, default="")
    video_count = Column(Integer, default=0)
    cluster_count = Column(Integer, default=0)
    categories = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FaceCluster(Base):
    __tablename__ = "face_clusters"
    id = Column(String, primary_key=True)
    performer_id = Column(String, ForeignKey("performers.id"), nullable=True)
    face_count = Column(Integer, default=0)
    video_ids = Column(JSON, default=list)
    thumbnail = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FaceClusterVideo(Base):
    __tablename__ = "face_cluster_videos"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster_id = Column(String, ForeignKey("face_clusters.id"))
    video_id = Column(String)
    distance = Column(Float, default=0)
    quality = Column(Float, default=0)
    detector = Column(String, default="ssd")
    thumbnail = Column(String, default="")
    title = Column(String, default="")
    source = Column(String, default="")
    scanned_at = Column(String, default="")


class PerformerVideo(Base):
    __tablename__ = "performer_videos"
    performer_id = Column(String, ForeignKey("performers.id"), primary_key=True)
    video_id = Column(String, primary_key=True)
    confidence = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    body = Column(Text, default="")
    assignee = Column(String, default="default")
    priority = Column(String, default="normal")
    status = Column(String, default="ready")  # ready, running, done, failed
    result = Column(Text, nullable=True)
    dispatch_method = Column(String, default="")
    parents = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class CronJob(Base):
    __tablename__ = "cron_jobs"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    agent_id = Column(String, default="")
    schedule = Column(String, default="every 1h")
    task = Column(Text, default="")
    enabled = Column(Boolean, default=True)
    status = Column(String, default="idle")
    last_run = Column(DateTime, nullable=True)
    last_result = Column(JSON, nullable=True)
    run_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(String, primary_key=True)
    title = Column(String, default="New Chat")
    model = Column(String, default="")
    provider = Column(String, default="")
    messages = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"))
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Lifecycle ──────────────────────────────────────────────────────────

async def init_db():
    global engine, async_session, vr_engine, vr_async_session

    # Main Odysseus database
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Main database initialized: %s", settings.DATABASE_URL)

    # VR Video read-only database
    vr_db_path = settings.VR_DATABASE_PATH
    vr_db_url = f"sqlite+aiosqlite:///{vr_db_path}"
    vr_engine = create_async_engine(vr_db_url, echo=False)
    vr_async_session = async_sessionmaker(vr_engine, class_=AsyncSession, expire_on_commit=False)
    log.info("VR Video database connected (read-only): %s", vr_db_path)


async def close_db():
    global engine, vr_engine
    if engine:
        await engine.dispose()
        engine = None
    if vr_engine:
        await vr_engine.dispose()
        vr_engine = None


from typing import AsyncGenerator


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def get_vr_session() -> AsyncGenerator[AsyncSession, None]:
    async with vr_async_session() as session:
        yield session
