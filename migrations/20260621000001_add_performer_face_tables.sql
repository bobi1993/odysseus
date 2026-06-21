-- migrations/20260621000001_add_performer_face_tables.sql
-- Phase 1-2: Add face recognition + performer tracking tables
-- Compatible with existing Odysseus SQLite schema (SQLAlchemy-managed)

-- ─────────────────────────────────────────────────────────
-- performers: Named performer identity
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS performers (
    id TEXT PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,                          -- URL-safe name: "jane-doe"
    name TEXT NOT NULL,                                  -- Display name
    aliases TEXT DEFAULT '[]',                           -- JSON array of alternate names
    gender TEXT,                                           -- 'female', 'male', 'non-binary', or NULL
    thumbnail TEXT,                                        -- Path to best face image
    face_count INTEGER DEFAULT 0,                          -- Total detected face instances
    video_count INTEGER DEFAULT 0,                         -- Number of distinct videos
    detection_count INTEGER DEFAULT 0,                     -- Total faces matched to this performer
    quality REAL DEFAULT 0,                                -- Avg image quality score (0-1)

    -- Canonical descriptor: averaged L2-normalized 512-dim embedding
    descriptor BLOB,                                       -- 512 x float32 = 2048 bytes

    -- Metadata
    categories TEXT DEFAULT '[]',                          -- JSON array of auto-detected categories
    tags TEXT DEFAULT '[]',                                -- JSON array of user tags
    favorite INTEGER DEFAULT 0,                            -- 0 or 1
    notes TEXT DEFAULT '',

    -- Folder integration
    folder_path TEXT,                                      -- Virtual path: /library/performers/{slug}/

    -- Timestamps (naive UTC, matching existing schema)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT                                      -- Last video timestamp where detected
);

CREATE INDEX IF NOT EXISTS idx_performers_slug ON performers(slug);
CREATE INDEX IF NOT EXISTS idx_performers_name ON performers(name);
CREATE INDEX IF NOT EXISTS idx_performers_video_count ON performers(video_count DESC);
CREATE INDEX IF NOT EXISTS idx_performers_quality ON performers(quality DESC);
CREATE INDEX IF NOT EXISTS idx_performers_favorite ON performers(favorite);

-- ─────────────────────────────────────────────────────────
-- face_clusters: Unnamed face clusters (pre-naming)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS face_clusters (
    id TEXT PRIMARY KEY,
    cluster_index INTEGER NOT NULL,                        -- Sequential within a scan session
    face_count INTEGER DEFAULT 0,                          -- Number of face instances in cluster
    representative_face_id TEXT,                           -- FK to face_detections

    -- Cluster centroid descriptor (512-dim, L2-normalized)
    centroid_descriptor BLOB,                              -- 512 x float32 = 2048 bytes

    -- Quality metrics
    avg_confidence REAL DEFAULT 0,
    avg_quality REAL DEFAULT 0,

    -- Link to named performer (NULL = unnamed cluster)
    performer_id TEXT REFERENCES performers(id) ON DELETE SET NULL,

    -- Scan session tracking
    scan_session_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_face_clusters_performer ON face_clusters(performer_id);
CREATE INDEX IF NOT EXISTS idx_face_clusters_scan ON face_clusters(scan_session_id);

-- ─────────────────────────────────────────────────────────
-- face_detections: Individual face detection instances
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS face_detections (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,                                -- FK to videos table
    frame_number INTEGER,
    timestamp_sec REAL,                                    -- Position in video (seconds)

    -- Bounding box
    bbox_x1 REAL,
    bbox_y1 REAL,
    bbox_x2 REAL,
    bbox_y2 REAL,

    -- 5-point landmarks (stored as JSON: [[x,y], ...])
    landmarks TEXT,

    -- Detection metadata
    confidence REAL NOT NULL,                              -- RetinaFace detection score
    quality REAL DEFAULT 0,                                -- Image quality estimate

    -- ArcFace 512-dim descriptor (L2-normalized)
    descriptor BLOB,                                       -- 512 x float32 = 2048 bytes

    -- Cluster assignment
    cluster_id TEXT REFERENCES face_clusters(id) ON DELETE SET NULL,
    performer_id TEXT REFERENCES performers(id) ON DELETE SET NULL,

    -- Source
    source_image TEXT,                                     -- Path to keyframe/thumbnail
    scan_session_id TEXT,

    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_face_detections_video ON face_detections(video_id);
CREATE INDEX IF NOT EXISTS idx_face_detections_cluster ON face_detections(cluster_id);
CREATE INDEX IF NOT EXISTS idx_face_detections_performer ON face_detections(performer_id);
CREATE INDEX IF NOT EXISTS idx_face_detections_scan ON face_detections(scan_session_id);

-- ─────────────────────────────────────────────────────────
-- performer_videos: Many-to-many link with confidence
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS performer_videos (
    id TEXT PRIMARY KEY,
    performer_id TEXT NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,
    confidence REAL DEFAULT 0,                             -- Avg match confidence
    face_count INTEGER DEFAULT 0,                          -- Faces matched in this video
    first_seen_sec REAL,                                   -- First detection timestamp
    last_seen_sec REAL,                                    -- Last detection timestamp

    -- Projection types found in this performer's videos
    projections TEXT DEFAULT '[]',                         -- JSON: ["180_sbs", "360_tb", ...]

    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(performer_id, video_id)
);

CREATE INDEX IF NOT EXISTS idx_performer_videos_performer ON performer_videos(performer_id);
CREATE INDEX IF NOT EXISTS idx_performer_videos_video ON performer_videos(video_id);
CREATE INDEX IF NOT EXISTS idx_performer_videos_confidence ON performer_videos(confidence DESC);

-- ─────────────────────────────────────────────────────────
-- performer_training_examples: User-verified face samples
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS performer_training_examples (
    id TEXT PRIMARY KEY,
    performer_id TEXT NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    face_detection_id TEXT REFERENCES face_detections(id) ON DELETE SET NULL,

    -- Image data
    image_path TEXT,                                       -- Path to cropped face image
    image_hash TEXT,                                       -- SHA-256 for dedup

    -- Descriptor at time of training (may differ from current centroid)
    descriptor BLOB,                                       -- 512 x float32

    -- Verification
    is_positive INTEGER DEFAULT 1,                         -- 1 = confirmed, 0 = rejected
    verified_by TEXT DEFAULT 'user',                       -- 'user', 'auto', 'ollama'

    -- Quality
    quality REAL DEFAULT 0,
    confidence REAL DEFAULT 0,

    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_training_performer ON performer_training_examples(performer_id);
CREATE INDEX IF NOT EXISTS idx_training_hash ON performer_training_examples(image_hash);

-- ─────────────────────────────────────────────────────────
-- face_scan_queue: Background job tracking
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS face_scan_queue (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',                -- 'pending', 'processing', 'done', 'error'
    priority INTEGER DEFAULT 0,                            -- Higher = process first
    source TEXT DEFAULT 'manual',                          -- 'manual', 'auto_ingest', 'recluster'

    -- Processing metadata
    worker_id TEXT,                                        -- Which worker picked this up
    started_at TEXT,
    completed_at TEXT,
    error_message TEXT,

    -- Results summary
    faces_found INTEGER DEFAULT 0,
    performers_matched INTEGER DEFAULT 0,
    clusters_created INTEGER DEFAULT 0,

    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_scan_queue_status ON face_scan_queue(status, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_scan_queue_video ON face_scan_queue(video_id);

-- ─────────────────────────────────────────────────────────
-- face_scan_sessions: Track batch scan operations
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS face_scan_sessions (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'running',                -- 'running', 'completed', 'cancelled', 'error'
    total_videos INTEGER DEFAULT 0,
    processed_videos INTEGER DEFAULT 0,
    total_faces_found INTEGER DEFAULT 0,
    total_clusters_created INTEGER DEFAULT 0,
    total_performers_matched INTEGER DEFAULT 0,

    -- Config snapshot
    config TEXT,                                           -- JSON: thresholds, model, etc.

    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_scan_sessions_status ON face_scan_sessions(status);

-- ─────────────────────────────────────────────────────────
-- Trigger: Update performer video_count on link changes
-- ─────────────────────────────────────────────────────────
CREATE TRIGGER IF NOT EXISTS trg_performer_videos_count_insert
AFTER INSERT ON performer_videos
BEGIN
    UPDATE performers SET
        video_count = (SELECT COUNT(DISTINCT video_id) FROM performer_videos WHERE performer_id = NEW.performer_id),
        updated_at = datetime('now')
    WHERE id = NEW.performer_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_performer_videos_count_delete
AFTER DELETE ON performer_videos
BEGIN
    UPDATE performers SET
        video_count = (SELECT COUNT(DISTINCT video_id) FROM performer_videos WHERE performer_id = OLD.performer_id),
        updated_at = datetime('now')
    WHERE id = OLD.performer_id;
END;

-- ─────────────────────────────────────────────────────────
-- Trigger: Update performer detection_count
-- ─────────────────────────────────────────────────────────
CREATE TRIGGER IF NOT EXISTS trg_face_detections_count_insert
AFTER INSERT ON face_detections
WHEN NEW.performer_id IS NOT NULL
BEGIN
    UPDATE performers SET
        detection_count = (SELECT COUNT(*) FROM face_detections WHERE performer_id = NEW.performer_id),
        updated_at = datetime('now')
    WHERE id = NEW.performer_id;
END;
