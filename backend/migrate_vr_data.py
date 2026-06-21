"""
Data Migration Script — VR Video → Odysseus

Reads from the legacy VR video SQLite database and migrates:
  - Videos
  - Performers
  - Face clusters
  - Face cluster ↔ video mappings
  - Performer ↔ video mappings

Idempotent: safe to run multiple times (uses ON CONFLICT / merge checks).
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Ensure we can import from the odysseus backend package
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR.parent))

import aiosqlite

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.config import settings
from backend.database import Base, Video, Performer, FaceCluster, FaceClusterVideo, PerformerVideo

log = logging.getLogger("migrate")


async def read_old_videos(db_path: str) -> list[dict]:
    """Read all videos from the legacy VR database."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM videos ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def read_old_performers(db_path: str) -> list[dict]:
    """Read all performers from the legacy VR database."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM performers ORDER BY name") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def read_old_face_clusters(db_path: str) -> list[dict]:
    """Read all face clusters from the legacy VR database (v1 + v2 merged)."""
    clusters = {}
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        # v1 clusters
        async with db.execute("SELECT * FROM face_clusters") as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                d = dict(r)
                cid = d["id"]
                if cid not in clusters:
                    clusters[cid] = {
                        "id": cid,
                        "performer_id": d.get("performer_id"),
                        "face_count": d.get("face_count", 0),
                        "created_at": d.get("created_at"),
                        "updated_at": d.get("updated_at"),
                    }

        # v2 clusters (richer data — override v1 if same id exists)
        async with db.execute("SELECT * FROM face_clusters_v2") as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                d = dict(r)
                cid = d["id"]
                clusters[cid] = {
                    "id": cid,
                    "performer_id": d.get("performer_id"),
                    "face_count": d.get("face_count", 0),
                    "created_at": d.get("created_at"),
                    "updated_at": d.get("updated_at"),
                }

    return list(clusters.values())


async def read_old_cluster_videos(db_path: str) -> list[dict]:
    """Read face_cluster_videos mappings from the legacy VR database."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM face_cluster_videos") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def read_old_performer_videos(db_path: str) -> list[dict]:
    """Read performer_videos mappings from the legacy VR database."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM performer_videos") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


def parse_dt(s):
    """Parse a datetime string from SQLite into a Python datetime or None."""
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


async def migrate_videos(async_session, old_videos: list[dict]) -> int:
    """Migrate videos. Returns count of newly inserted rows."""
    inserted = 0
    skipped = 0
    async with async_session() as session:
        for old in old_videos:
            existing = await session.get(Video, old["id"])
            if existing:
                skipped += 1
                continue

            v = Video(
                id=old["id"],
                title=old.get("title", ""),
                source=old.get("source_type", ""),
                url=old.get("external_url", ""),
                thumbnail=old.get("thumbnail_url", ""),
                duration=float(old.get("duration", 0) or 0),
                projection=old.get("projection", "flat"),
                views=old.get("views", 0),
                is_favorite=False,
                created_at=parse_dt(old.get("created_at")) or datetime.utcnow(),
                updated_at=parse_dt(old.get("updated_at")) or datetime.utcnow(),
            )
            session.add(v)
            inserted += 1

        await session.commit()

    log.info("Videos: %d inserted, %d skipped (already exist)", inserted, skipped)
    return inserted


async def migrate_performers(async_session, old_performers: list[dict]) -> int:
    """Migrate performers. Returns count of newly inserted rows."""
    inserted = 0
    skipped = 0
    async with async_session() as session:
        for old in old_performers:
            existing = await session.get(Performer, old["id"])
            if existing:
                skipped += 1
                continue

            p = Performer(
                id=old["id"],
                name=old.get("name", ""),
                thumbnail=old.get("thumbnail_url", ""),
                video_count=old.get("video_count", 0),
                cluster_count=old.get("cluster_count", 0),
                created_at=parse_dt(old.get("created_at")) or datetime.utcnow(),
                updated_at=parse_dt(old.get("updated_at")) or datetime.utcnow(),
            )
            session.add(p)
            inserted += 1

        await session.commit()

    log.info("Performers: %d inserted, %d skipped", inserted, skipped)
    return inserted


async def migrate_face_clusters(async_session, old_clusters: list[dict]) -> int:
    """Migrate face clusters. Returns count of newly inserted rows."""
    inserted = 0
    skipped = 0
    async with async_session() as session:
        for old in old_clusters:
            existing = await session.get(FaceCluster, old["id"])
            if existing:
                skipped += 1
                continue

            fc = FaceCluster(
                id=old["id"],
                performer_id=old.get("performer_id"),
                face_count=old.get("face_count", 0),
                created_at=parse_dt(old.get("created_at")) or datetime.utcnow(),
                updated_at=parse_dt(old.get("updated_at")) or datetime.utcnow(),
            )
            session.add(fc)
            inserted += 1

        await session.commit()

    log.info("Face clusters: %d inserted, %d skipped", inserted, skipped)
    return inserted


async def migrate_cluster_videos(async_session, old_mappings: list[dict]) -> int:
    """Migrate face_cluster_videos mappings. Skip duplicates."""
    inserted = 0
    skipped = 0
    async with async_session() as session:
        for old in old_mappings:
            # Check if this exact mapping already exists
            from sqlalchemy import select, and_
            stmt = select(FaceClusterVideo).where(
                and_(
                    FaceClusterVideo.cluster_id == old["cluster_id"],
                    FaceClusterVideo.video_id == old["video_id"],
                )
            )
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                skipped += 1
                continue

            fcv = FaceClusterVideo(
                cluster_id=old["cluster_id"],
                video_id=old["video_id"],
                distance=old.get("distance", 0),
                quality=old.get("quality", 0),
                detector=old.get("detector", "ssd"),
                thumbnail=old.get("thumbnail", ""),
                title=old.get("title", ""),
                source=old.get("source", ""),
            )
            session.add(fcv)
            inserted += 1

        await session.commit()

    log.info("Face cluster videos: %d inserted, %d skipped", inserted, skipped)
    return inserted


async def migrate_performer_videos(async_session, old_mappings: list[dict]) -> int:
    """Migrate performer_videos mappings. Skip duplicates."""
    inserted = 0
    skipped = 0
    async with async_session() as session:
        for old in old_mappings:
            from sqlalchemy import select, and_
            stmt = select(PerformerVideo).where(
                and_(
                    PerformerVideo.performer_id == old["performer_id"],
                    PerformerVideo.video_id == old["video_id"],
                )
            )
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                skipped += 1
                continue

            pv = PerformerVideo(
                performer_id=old["performer_id"],
                video_id=old["video_id"],
                confidence=old.get("confidence", 0),
            )
            session.add(pv)
            inserted += 1

        await session.commit()

    log.info("Performer videos: %d inserted, %d skipped", inserted, skipped)
    return inserted


async def update_cluster_thumbnails(async_session):
    """Set cluster thumbnails from their best-quality cluster_video entry."""
    from sqlalchemy import select
    async with async_session() as session:
        result = await session.execute(select(FaceCluster))
        clusters = result.scalars().all()

        updated = 0
        for cluster in clusters:
            if cluster.thumbnail:
                continue  # Already has a thumbnail

            # Find the best thumbnail from face_cluster_videos
            stmt = (
                select(FaceClusterVideo)
                .where(FaceClusterVideo.cluster_id == cluster.id)
                .where(FaceClusterVideo.thumbnail.isnot(None))
                .where(FaceClusterVideo.thumbnail != "")
                .order_by(FaceClusterVideo.quality.desc())
                .limit(1)
            )
            thumb_result = await session.execute(stmt)
            best = thumb_result.scalar_one_or_none()
            if best and best.thumbnail:
                cluster.thumbnail = best.thumbnail
                updated += 1

        await session.commit()

    log.info("Updated %d cluster thumbnails", updated)


async def run_migration():
    """Main migration entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    vr_db_path = settings.VR_DATABASE_PATH
    log.info("Starting migration from: %s", vr_db_path)

    # Check source DB exists
    if not Path(vr_db_path).exists():
        log.error("Source database not found: %s", vr_db_path)
        return False

    # Read all data from old DB
    log.info("Reading legacy VR video database...")
    old_videos = await read_old_videos(vr_db_path)
    old_performers = await read_old_performers(vr_db_path)
    old_clusters = await read_old_face_clusters(vr_db_path)
    old_cluster_videos = await read_old_cluster_videos(vr_db_path)
    old_performer_videos = await read_old_performer_videos(vr_db_path)

    log.info(
        "Source: %d videos, %d performers, %d clusters, %d cluster_videos, %d performer_videos",
        len(old_videos),
        len(old_performers),
        len(old_clusters),
        len(old_cluster_videos),
        len(old_performer_videos),
    )

    # Initialize Odysseus DB
    db_url = settings.DATABASE_URL
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Run migration
    v = await migrate_videos(session_factory, old_videos)
    p = await migrate_performers(session_factory, old_performers)
    c = await migrate_face_clusters(session_factory, old_clusters)
    cv = await migrate_cluster_videos(session_factory, old_cluster_videos)
    pv = await migrate_performer_videos(session_factory, old_performer_videos)

    # Post-migration: update thumbnails
    await update_cluster_thumbnails(session_factory)

    await engine.dispose()

    log.info(
        "Migration complete! Inserted: %d videos, %d performers, %d clusters, %d cluster_videos, %d performer_videos",
        v, p, c, cv, pv,
    )
    return True


if __name__ == "__main__":
    success = asyncio.run(run_migration())
    sys.exit(0 if success else 1)
