#!/usr/bin/env python3
"""
seed_performers.py
──────────────────
Seed script to bootstrap the performers table with top performers.
Extracts initial face data from existing video metadata and creates
performer records with clustered descriptors.

Usage:
    python seed_performers.py --db /path/to/app.db --data-dir /path/to/data --top 50
    python seed_performers.py --db /path/to/app.db --from-csv performers.csv

The script:
1. Scans existing video metadata for performer names (from scraper tags)
2. Extracts thumbnails from video files
3. Calls the face-service to get initial descriptors
4. Creates performer records with computed centroids
5. Generates virtual folder structure
"""

import argparse
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


FACE_SERVICE_URL = os.getenv("FACE_SERVICE_URL", "http://127.0.0.1:8050")
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))


def get_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_tables(conn: sqlite3.Connection):
    """Run migration if tables don't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS performers (
            id TEXT PRIMARY KEY,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            aliases TEXT DEFAULT '[]',
            gender TEXT,
            thumbnail TEXT,
            face_count INTEGER DEFAULT 0,
            video_count INTEGER DEFAULT 0,
            detection_count INTEGER DEFAULT 0,
            quality REAL DEFAULT 0,
            descriptor BLOB,
            categories TEXT DEFAULT '[]',
            tags TEXT DEFAULT '[]',
            favorite INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            folder_path TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_seen_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS performer_videos (
            id TEXT PRIMARY KEY,
            performer_id TEXT NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
            video_id TEXT NOT NULL,
            confidence REAL DEFAULT 0,
            face_count INTEGER DEFAULT 0,
            first_seen_sec REAL DEFAULT 0,
            last_seen_sec REAL DEFAULT 0,
            projections TEXT DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(performer_id, video_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS face_clusters (
            id TEXT PRIMARY KEY,
            cluster_index INTEGER NOT NULL,
            face_count INTEGER DEFAULT 0,
            representative_face_id TEXT,
            centroid_descriptor BLOB,
            avg_confidence REAL DEFAULT 0,
            avg_quality REAL DEFAULT 0,
            performer_id TEXT REFERENCES performers(id) ON DELETE SET NULL,
            scan_session_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS face_detections (
            id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL,
            frame_number INTEGER,
            timestamp_sec REAL,
            bbox_x1 REAL, bbox_y1 REAL, bbox_x2 REAL, bbox_y2 REAL,
            landmarks TEXT,
            confidence REAL NOT NULL,
            quality REAL DEFAULT 0,
            descriptor BLOB,
            cluster_id TEXT REFERENCES face_clusters(id) ON DELETE SET NULL,
            performer_id TEXT REFERENCES performers(id) ON DELETE SET NULL,
            source_image TEXT,
            scan_session_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_performers_slug ON performers(slug)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_performers_name ON performers(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_face_detections_video ON face_detections(video_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_face_detections_performer ON face_detections(performer_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_performer_videos_performer ON performer_videos(performer_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_performer_videos_video ON performer_videos(video_id)")
    conn.commit()


def scan_video_performers(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """
    Extract performer names from existing video metadata.
    Looks for performer tags in the categories/tags JSON fields.
    Returns: { performer_name: [video_id, ...] }
    """
    performers: dict[str, list[str]] = {}

    # Try to get videos with performer metadata
    try:
        rows = conn.execute("""
            SELECT id, title, categories, tags, source_type
            FROM videos
            WHERE categories IS NOT NULL OR tags IS NOT NULL
            LIMIT 5000
        """).fetchall()
    except sqlite3.OperationalError:
        # Fallback: videos table might have different schema
        try:
            rows = conn.execute("""
                SELECT id, title, '[]' as categories, '[]' as tags, '' as source_type
                FROM videos LIMIT 5000
            """).fetchall()
        except sqlite3.OperationalError:
            print("WARNING: Could not query videos table. Is the schema correct?")
            return performers

    for row in rows:
        video_id = row["id"]
        # Parse categories and tags
        for field in ("categories", "tags"):
            try:
                items = json.loads(row[field] or "[]")
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, str) and len(item) > 1:
                            name = item.strip().title()
                            if name not in performers:
                                performers[name] = []
                            if video_id not in performers[name]:
                                performers[name].append(video_id)
            except (json.JSONDecodeError, TypeError):
                continue

    return performers


def slugify(name: str) -> str:
    """Create URL-safe slug from performer name."""
    return (
        name.lower()
        .replace("'", "")
        .replace(" ", "-")
        .replace("--", "-")
        .strip("-")[:64]
    )


def check_face_service() -> bool:
    """Check if the face recognition service is reachable."""
    try:
        resp = httpx.get(f"{FACE_SERVICE_URL}/api/health", timeout=5)
        data = resp.json()
        return data.get("model_loaded", False)
    except Exception:
        return False


def seed_from_database(conn: sqlite3.Connection, top_n: int = 50, data_dir: Path = DATA_DIR):
    """
    Seed performers from existing video metadata.
    Creates performer records linked to their videos.
    """
    print(f"Scanning video metadata for performers...")
    video_performers = scan_video_performers(conn)

    if not video_performers:
        print("No performer data found in video metadata.")
        print("You can use --from-csv to import from a CSV file instead.")
        return

    # Sort by video count (most videos first)
    sorted_performors = sorted(video_performers.items(), key=lambda x: len(x[1]), reverse=True)
    top = sorted_performors[:top_n]

    print(f"Found {len(video_performers)} unique performer names. Seeding top {len(top)}...")

    service_available = check_face_service()
    if service_available:
        print("Face service available — will attempt descriptor extraction.")
    else:
        print("Face service unavailable — creating performer records without descriptors.")

    performer_dir = data_dir / "performers"
    performer_dir.mkdir(parents=True, exist_ok=True)

    seeded = 0
    for name, video_ids in top:
        slug = slugify(name)
        performer_id = str(uuid.uuid4())
        folder_path = str(performer_dir / slug)

        # Check if already exists
        existing = conn.execute("SELECT id FROM performers WHERE slug = ?", (slug,)).fetchone()
        if existing:
            print(f"  SKIP: {name} (already exists)")
            continue

        # Create performer record
        now = utcnow()
        conn.execute("""
            INSERT INTO performers (id, slug, name, video_count, folder_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (performer_id, slug, name, len(video_ids), folder_path, now, now))

        # Link videos
        for vid in video_ids:
            link_id = str(uuid.uuid4())
            conn.execute("""
                INSERT OR IGNORE INTO performer_videos (id, performer_id, video_id, confidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (link_id, performer_id, vid, 0.5, now, now))

        # Create folder
        Path(folder_path).mkdir(parents=True, exist_ok=True)

        seeded += 1
        print(f"  OK: {name} ({len(video_ids)} videos)")

    conn.commit()
    print(f"\nSeeded {seeded} performers.")


def seed_from_csv(conn: sqlite3.Connection, csv_path: str, data_dir: Path = DATA_DIR):
    """
    Seed performers from a CSV file.
    Expected columns: name, [gender], [aliases], [video_count], [thumbnail]
    """
    import csv

    performer_dir = data_dir / "performers"
    performer_dir.mkdir(parents=True, exist_ok=True)

    seeded = 0
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "").strip()
            if not name:
                continue

            slug = slugify(name)
            existing = conn.execute("SELECT id FROM performers WHERE slug = ?", (slug,)).fetchone()
            if existing:
                continue

            performer_id = str(uuid.uuid4())
            now = utcnow()
            aliases = json.dumps([a.strip() for a in row.get("aliases", "").split(";") if a.strip()])
            folder_path = str(performer_dir / slug)

            conn.execute("""
                INSERT INTO performers (id, slug, name, gender, aliases, video_count, thumbnail, folder_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                performer_id, slug, name,
                row.get("gender") or None,
                aliases,
                int(row.get("video_count", 0)),
                row.get("thumbnail") or None,
                folder_path, now, now,
            ))

            Path(folder_path).mkdir(parents=True, exist_ok=True)
            seeded += 1

    conn.commit()
    print(f"Seeded {seeded} performers from {csv_path}")


def generate_sample_csv(output_path: str):
    """Generate a sample CSV template for manual performer entry."""
    sample = [
        "name,gender,aliases,video_count,thumbnail",
        "Jane Doe,female,'JD;J.Doe',0,",
        "Alex Smith,non-binary,'A.Smith;Alex',0,",
    ]
    with open(output_path, "w") as f:
        f.write("\n".join(sample))
    print(f"Sample CSV written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Seed performer database")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--data-dir", default=str(DATA_DIR), help="Data directory")
    parser.add_argument("--top", type=int, default=50, help="Top N performers by video count")
    parser.add_argument("--from-csv", help="Import from CSV file")
    parser.add_argument("--generate-csv", help="Generate sample CSV template")
    args = parser.parse_args()

    if args.generate_csv:
        generate_sample_csv(args.generate_csv)
        return

    conn = get_db(args.db)
    ensure_tables(conn)
    data_dir = Path(args.data_dir)

    if args.from_csv:
        seed_from_csv(conn, args.from_csv, data_dir)
    else:
        seed_from_database(conn, args.top, data_dir)

    conn.close()


if __name__ == "__main__":
    main()
