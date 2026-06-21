"""Video library — CRUD, search, tags, favorites.
Reads from the legacy VR video database via SQLAlchemy async session,
with fallback to the local Odysseus database for migrated videos.
"""

import logging
import sqlite3
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from typing import Optional

from backend.config import settings
from backend.database import get_session, Video, Performer

router = APIRouter()
log = logging.getLogger("video")


def _sync_vr_query(query: str, params: tuple = None) -> list:
    """Run a synchronous query against the VR video database."""
    db_path = settings.VR_DATABASE_PATH
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if params:
            rows = conn.execute(query, params).fetchall()
        else:
            rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _sync_vr_count(query: str, params: tuple = None) -> int:
    """Run a synchronous count query against the VR video database."""
    db_path = settings.VR_DATABASE_PATH
    if not Path(db_path).exists():
        return 0
    conn = sqlite3.connect(db_path)
    try:
        if params:
            row = conn.execute(query, params).fetchone()
        else:
            row = conn.execute(query).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


@router.get("/")
async def list_videos(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    source: Optional[str] = None,
    category: Optional[str] = None,
    projection: Optional[str] = None,
    sort: str = Query("created_at", regex="^(created_at|title|views|likes|duration)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    session: AsyncSession = Depends(get_session),
):
    """List videos with pagination, search, and filters.
    Reads from the legacy VR video database for full content,
    enriches with performer data.
    """
    db_path = settings.VR_DATABASE_PATH
    if not Path(db_path).exists():
        raise HTTPException(503, "VR video database not found")

    # Build the query
    conditions = []
    params = []

    if search:
        conditions.append("(v.title LIKE ? OR v.id LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if source:
        conditions.append("v.source_type = ?")
        params.append(source)
    if category:
        conditions.append("v.category LIKE ?")
        params.append(f"%{category}%")
    if projection:
        conditions.append("v.projection = ?")
        params.append(projection)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    # Validate sort column
    valid_sorts = {"created_at": "v.created_at", "title": "v.title", "views": "v.views", "likes": "v.likes", "duration": "v.duration"}
    sort_col = valid_sorts.get(sort, "v.created_at")
    sort_dir = "DESC" if order == "desc" else "ASC"

    # Count total
    count_query = f"SELECT COUNT(*) FROM videos v {where}"
    total = await session.execute(text(f"SELECT 1"))  # Placeholder
    # Use sync query for count since VR DB is sync-only
    import asyncio
    loop = asyncio.get_event_loop()
    total = await loop.run_in_executor(None, _sync_vr_count, count_query, tuple(params) if params else None)

    # Fetch videos
    offset = (page - 1) * limit
    query = f"""
        SELECT v.id, v.title, v.external_url, v.source_type, v.category,
               v.duration, v.thumbnail_url, v.embed_url, v.resolved_stream_url,
               v.projection, v.views, v.likes, v.dead_count, v.created_at, v.updated_at
        FROM videos v
        {where}
        ORDER BY {sort_col} {sort_dir}
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    videos = await loop.run_in_executor(None, _sync_vr_query, query, tuple(params))

    # Enrich with performer data
    video_ids = [v["id"] for v in videos]
    performer_map = {}
    if video_ids:
        placeholders = ",".join("?" * len(video_ids))
        performer_query = f"""
            SELECT pv.video_id, p.id as performer_id, p.name as performer_name,
                   p.thumbnail_url as performer_thumbnail
            FROM performer_videos pv
            JOIN performers p ON p.id = pv.performer_id
            WHERE pv.video_id IN ({placeholders})
        """
        performer_rows = await loop.run_in_executor(
            None, _sync_vr_query, performer_query, tuple(video_ids)
        )
        for pr in performer_rows:
            vid = pr["video_id"]
            if vid not in performer_map:
                performer_map[vid] = []
            performer_map[vid].append({
                "id": pr["performer_id"],
                "name": pr["performer_name"],
                "thumbnail": pr.get("performer_thumbnail", ""),
            })

    # Build response
    video_list = []
    for v in videos:
        vid = v["id"]
        # Format duration from "MM:SS" or integer seconds
        duration = v.get("duration", 0)
        if isinstance(duration, str) and ":" in duration:
            parts = duration.split(":")
            try:
                duration = int(parts[0]) * 60 + int(parts[1])
            except (ValueError, IndexError):
                duration = 0

        # Build thumbnail path
        thumbnail = v.get("thumbnail_url", "")

        video_list.append({
            "id": vid,
            "title": v.get("title", ""),
            "url": v.get("external_url", ""),
            "source": v.get("source_type", ""),
            "category": v.get("category", ""),
            "duration": duration,
            "thumbnail": thumbnail,
            "thumbnail_local": f"/api/videos/thumb/{vid}",
            "embed_url": v.get("embed_url", ""),
            "stream_url": v.get("resolved_stream_url", ""),
            "projection": v.get("projection", "flat"),
            "views": v.get("views", 0),
            "likes": v.get("likes", 0),
            "performers": performer_map.get(vid, []),
            "created_at": v.get("created_at"),
            "updated_at": v.get("updated_at"),
        })

    return {
        "videos": video_list,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if total > 0 else 0,
    }


@router.get("/{video_id}")
async def get_video(video_id: str, session: AsyncSession = Depends(get_session)):
    """Get a single video by ID with full details."""
    import asyncio
    loop = asyncio.get_event_loop()

    video = await loop.run_in_executor(
        None,
        _sync_vr_query,
        "SELECT * FROM videos WHERE id = ?",
        (video_id,),
    )

    if not video:
        raise HTTPException(404, "Video not found")

    v = video[0]

    # Get performers
    performers = await loop.run_in_executor(
        None,
        _sync_vr_query,
        """
        SELECT p.id, p.name, p.thumbnail_url, pv.confidence
        FROM performer_videos pv
        JOIN performers p ON p.id = pv.performer_id
        WHERE pv.video_id = ?
        ORDER BY pv.confidence DESC
        """,
        (video_id,),
    )

    # Get face clusters for this video
    clusters = await loop.run_in_executor(
        None,
        _sync_vr_query,
        """
        SELECT fc.id, fc.face_count, fc.performer_id, fcv.quality, fcv.thumbnail
        FROM face_cluster_videos fcv
        JOIN face_clusters fc ON fc.id = fcv.cluster_id
        WHERE fcv.video_id = ?
        ORDER BY fcv.quality DESC
        """,
        (video_id,),
    )

    # Get tags
    tags = await loop.run_in_executor(
        None,
        _sync_vr_query,
        """
        SELECT t.name
        FROM video_tags vt
        JOIN tags t ON t.id = vt.tag_id
        WHERE vt.video_id = ?
        """,
        (video_id,),
    )

    # Get favorites
    favorite = await loop.run_in_executor(
        None,
        _sync_vr_query,
        "SELECT 1 FROM favorites WHERE video_id = ?",
        (video_id,),
    )

    # Get watch history
    watch = await loop.run_in_executor(
        None,
        _sync_vr_query,
        "SELECT progress, watched_at FROM watches WHERE video_id = ? ORDER BY watched_at DESC LIMIT 1",
        (video_id,),
    )

    duration = v.get("duration", 0)
    if isinstance(duration, str) and ":" in duration:
        parts = duration.split(":")
        try:
            duration = int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            duration = 0

    return {
        "id": v["id"],
        "title": v.get("title", ""),
        "url": v.get("external_url", ""),
        "source": v.get("source_type", ""),
        "category": v.get("category", ""),
        "duration": duration,
        "thumbnail": v.get("thumbnail_url", ""),
        "thumbnail_local": f"/api/videos/thumb/{video_id}",
        "embed_url": v.get("embed_url", ""),
        "stream_url": v.get("resolved_stream_url", ""),
        "projection": v.get("projection", "flat"),
        "views": v.get("views", 0),
        "likes": v.get("likes", 0),
        "performers": [
            {
                "id": p["id"],
                "name": p["name"],
                "thumbnail": p.get("thumbnail_url", ""),
                "confidence": p.get("confidence", 0),
            }
            for p in performers
        ],
        "face_clusters": [
            {
                "id": c["id"],
                "face_count": c.get("face_count", 0),
                "performer_id": c.get("performer_id"),
                "quality": c.get("quality", 0),
                "thumbnail": c.get("thumbnail", ""),
            }
            for c in clusters
        ],
        "tags": [t["name"] for t in tags],
        "is_favorite": len(favorite) > 0,
        "last_watched": watch[0] if watch else None,
        "created_at": v.get("created_at"),
        "updated_at": v.get("updated_at"),
    }


@router.get("/thumb/{video_id}")
async def get_thumbnail(video_id: str):
    """Get video thumbnail — checks local cache first, then falls back to URL."""
    import os
    from fastapi.responses import FileResponse

    # Check for locally cached thumbnails
    thumb_dir = Path(settings.VR_THUMBNAIL_DIR)
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        thumb_path = thumb_dir / f"{video_id}{ext}"
        if thumb_path.exists():
            return FileResponse(str(thumb_path), media_type="image/jpeg")

    # Check snapshots directory
    snapshot_dir = Path(settings.VR_BACKEND_DIR) / "data" / "snapshots"
    for ext in [".jpg", ".jpeg", ".png"]:
        snap_path = snapshot_dir / f"{video_id}{ext}"
        if snap_path.exists():
            return FileResponse(str(snap_path), media_type="image/jpeg")

    # Fall back to redirecting to the URL
    import asyncio
    loop = asyncio.get_event_loop()
    video = await loop.run_in_executor(
        None,
        _sync_vr_query,
        "SELECT thumbnail_url FROM videos WHERE id = ?",
        (video_id,),
    )

    if video and video[0].get("thumbnail_url"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=video[0]["thumbnail_url"])

    raise HTTPException(404, "Thumbnail not found")


@router.post("/{video_id}/favorite")
async def toggle_favorite(video_id: str, session: AsyncSession = Depends(get_session)):
    """Toggle favorite status."""
    import asyncio
    loop = asyncio.get_event_loop()

    # Check if already favorited
    result = await loop.run_in_executor(
        None,
        _sync_vr_query,
        "SELECT 1 FROM favorites WHERE video_id = ?",
        (video_id,),
    )

    if result:
        await loop.run_in_executor(
            None,
            lambda: _sync_vr_query("DELETE FROM favorites WHERE video_id = ?", (video_id,)),
        )
        is_fav = False
    else:
        await loop.run_in_executor(
            None,
            lambda: _sync_vr_query(
                "INSERT INTO favorites (video_id) VALUES (?)", (video_id,)
            ),
        )
        is_fav = True

    return {"id": video_id, "is_favorite": is_fav}


@router.get("/sources/list")
async def list_sources(session: AsyncSession = Depends(get_session)):
    """List all unique video sources with counts."""
    import asyncio
    loop = asyncio.get_event_loop()

    sources = await loop.run_in_executor(
        None,
        _sync_vr_query,
        "SELECT source_type as name, COUNT(*) as count FROM videos GROUP BY source_type ORDER BY count DESC",
    )

    return {"sources": sources}


@router.get("/projections/list")
async def list_projections():
    """List all available projection types."""
    import asyncio
    loop = asyncio.get_event_loop()

    projections = await loop.run_in_executor(
        None,
        _sync_vr_query,
        "SELECT DISTINCT projection FROM videos WHERE projection IS NOT NULL ORDER BY projection",
    )

    return {"projections": [p["projection"] for p in projections if p["projection"]]}


@router.post("/{video_id}/play")
async def record_play(video_id: str):
    """Record a play event (increments view count, adds to watch history)."""
    import asyncio
    loop = asyncio.get_event_loop()

    # Check video exists
    video = await loop.run_in_executor(
        None,
        _sync_vr_query,
        "SELECT id FROM videos WHERE id = ?",
        (video_id,),
    )
    if not video:
        raise HTTPException(404, "Video not found")

    # Increment views
    await loop.run_in_executor(
        None,
        lambda: _sync_vr_query("UPDATE videos SET views = views + 1 WHERE id = ?", (video_id,)),
    )

    # Add to watch history
    await loop.run_in_executor(
        None,
        lambda: _sync_vr_query(
            "INSERT INTO watches (video_id, progress) VALUES (?, 0)", (video_id,)
        ),
    )

    return {"id": video_id, "status": "recorded"}
