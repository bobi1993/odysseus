# VR Face Recognition & Auto-Categorization System
# ═════════════════════════════════════════════════

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Odysseus (FastAPI)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  FacesView   │  │  Performer   │  │  faceRecognition     │  │
│  │  .vue        │  │  ProfileView │  │  Service.ts          │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                  │                      │              │
│         └──────────────────┴──────────────────────┘              │
│                          HTTP /api/faces/*                       │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP (localhost:8050)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Face Service (FastAPI + ONNX)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  RetinaFace  │  │  ArcFace     │  │  Agglomerative       │  │
│  │  Detection   │  │  w600k_r50   │  │  Clustering          │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                  │
│  Endpoints:                                                      │
│    POST /api/faces/detect      — Detect + embed faces            │
│    POST /api/faces/match       — Match descriptor to gallery     │
│    POST /api/faces/cluster     — Cluster descriptors             │
│    POST /api/keyframes/extract — Extract video keyframes         │
│    POST /api/faces/describe    — Ollama vision fallback          │
│    GET  /api/health            — Service health + model status   │
└─────────────────────────────────────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
            ┌──────────────┐     ┌──────────────┐
            │   SQLite DB  │     │   Ollama     │
            │  (app.db)    │     │  (fallback)  │
            └──────────────┘     └──────────────┘
```

## Migration Plan

### Phase 1: Enhanced Keyframe Extraction (Week 1)
**Goal**: Improve existing face-api.js with better frame extraction.

1. Deploy the face-service container
2. Use `/api/keyframes/extract` to get better frames from videos
3. Feed keyframes to existing face-api.js for detection
4. Store results in the new `face_detections` table

**Changes**:
- Add `face-service` to `docker-compose.yml`
- Run migration `20260621000001_add_performer_face_tables.sql`
- Update `FacesView.vue` to show scan progress
- Add keyframe extraction to the scan pipeline

### Phase 2: Full ArcFace Migration (Weeks 2-3)
**Goal**: Replace face-api.js recognition with ArcFace ONNX.

1. Download ArcFace model (auto-downloaded on first run by InsightFace)
2. Switch detection endpoint from face-api.js to `/api/faces/detect`
3. Implement performer gallery matching via `/api/faces/match`
4. Add clustering via `/api/faces/cluster` for unnamed faces
5. Build performer naming UI (assign names to clusters)

**Changes**:
- Update `faces.js` store to use new API endpoints
- Add `PerformerProfileView.vue` for detailed performer pages
- Implement face search (upload photo → find matches)
- Add training example collection for self-learning

### Phase 3: Auto-Categorization (Weeks 4-5)
**Goal**: Automatic performer tagging on video ingestion.

1. Hook into video ingestion pipeline
2. On new video: extract keyframes → detect faces → match performers
3. Auto-tag videos with matched performer names
4. Generate virtual folder structure: `/library/performers/{slug}/`
5. Build performer overview stats (best scenes, projection types)

**Changes**:
- Add `performer_videos` linking table updates
- Create folder symlinks or virtual paths
- Add performer stats aggregation queries
- Integrate with existing scraper plugins

### Phase 4: Self-Learning Agent (Weeks 6-7)
**Goal**: Improve recognition over time from user feedback.

1. Collect user confirmations/rejections of face matches
2. Store as `performer_training_examples`
3. Periodically recompute performer centroids from verified examples
4. Use Ollama vision fallback for ambiguous cases
5. Implement periodic re-clustering of unmatched faces

**Changes**:
- Add training example collection UI
- Implement centroid recomputation job
- Add Ollama fallback integration
- Schedule re-clustering cron job

## File Structure

```
odysseus/
├── face-service/                    # Python microservice
│   ├── Dockerfile                   # python:3.11-slim, 5GB cap
│   ├── requirements.txt             # FastAPI + ONNX Runtime + InsightFace
│   ├── .env.example                 # Configuration template
│   ├── main.py                      # FastAPI app with all endpoints
│   ├── PERFORMANCE_TUNING.md        # 16GB RAM tuning guide
│   └── docker-compose.snippet.yml   # Add to main compose
│
├── migrations/
│   └── 20260621000001_add_performer_face_tables.sql
│
├── services/faces/
│   ├── __init__.py
│   └── faceRecognitionService.ts    # Node.js integration layer
│
├── frontend/src/
│   ├── views/
│   │   ├── FacesView.vue            # Main faces & performers view
│   │   └── PerformerProfileView.vue # Detailed performer modal
│   ├── components/
│   │   └── PerformerCard.vue        # Performer grid card
│   └── stores/
│       └── faces.js                 # Pinia store
│
└── scripts/
    └── seed_performers.py           # Bootstrap performer database
```

## Quick Start

```bash
# 1. Add face-service to docker-compose.yml (see docker-compose.snippet.yml)

# 2. Run database migration
sqlite3 data/app.db < migrations/20260621000001_add_performer_face_tables.sql

# 3. Start services
docker-compose up -d face-service

# 4. Check health
curl http://localhost:8050/api/health

# 5. Seed initial performers
python scripts/seed_performers.py --db data/app.db --data-dir data --top 50

# 6. Scan a video
curl -X POST http://localhost:8050/api/keyframes/extract \
  -F "video_path=/app/data/videos/sample.mp4"

# 7. Detect faces in an image
curl -X POST http://localhost:8050/api/faces/detect \
  -F "file=@/path/to/image.jpg"
```

## API Reference

### POST /api/faces/detect
Detect faces in an image. Returns bounding boxes + 512-dim ArcFace descriptors.

**Input**: `multipart/form-data` with `file` (image) + optional `max_faces` (1-50)

**Output**:
```json
{
  "faces": [{
    "bbox": [x1, y1, x2, y2],
    "confidence": 0.95,
    "landmarks": [[x,y], ...],
    "descriptor": [0.012, -0.034, ...]  // 512-dim
  }],
  "image_width": 1920,
  "image_height": 1080,
  "processing_time_ms": 45.2
}
```

### POST /api/faces/match
Match a query descriptor against a gallery.

**Input**:
```json
{
  "descriptor": [0.012, ...],  // 512-dim
  "gallery": [[0.015, ...], ...],  // Nx512
  "threshold": 0.35
}
```

**Output**:
```json
{
  "matches": [
    {"index": 3, "similarity": 0.87},
    {"index": 7, "similarity": 0.72}
  ],
  "query_time_ms": 1.2
}
```

### POST /api/faces/cluster
Agglomerative clustering of face descriptors.

**Input**:
```json
{
  "descriptors": [[0.012, ...], ...],  // Nx512
  "threshold": 0.50
}
```

**Output**:
```json
{
  "clusters": [{
    "cluster_id": 0,
    "representative_idx": 0,
    "member_indices": [0, 3, 5, 7],
    "avg_similarity": 0.78
  }],
  "num_input": 100,
  "num_clusters": 12,
  "processing_time_ms": 23.4
}
```

### POST /api/keyframes/extract
Extract keyframes from a video using ffmpeg.

**Input**: `multipart/form-data` with `video_path`, optional `interval_sec`, `max_frames`

**Output**:
```json
{
  "keyframes": [{
    "timestamp_sec": 0.0,
    "frame_number": 0,
    "width": 1920,
    "height": 1080,
    "temp_path": "/tmp/vrframes_abc/frame_0000.jpg"
  }],
  "duration_sec": 1200.5,
  "total_frames": 36015,
  "processing_time_ms": 5230.1
}
```

## Thresholds

| Parameter | Default | Description |
|-----------|---------|-------------|
| `FACE_MATCH_THRESHOLD` | 0.35 | Cosine similarity for same-person match |
| `FACE_CLUSTER_THRESHOLD` | 0.50 | Cosine similarity for clustering merge |
| `FACE_MIN_CONFIDENCE` | 0.60 | Minimum RetinaFace detection score |

**Tuning tips**:
- Lower match threshold (0.25-0.30) = more matches, more false positives
- Higher match threshold (0.40-0.50) = fewer matches, more false negatives
- Cluster threshold controls how tightly faces are grouped
- Start with defaults, adjust based on your video quality

## Troubleshooting

**"Model not loaded" on healthcheck**:
- First startup downloads the ArcFace model (~166MB) — takes 30-60s
- Check disk space: `docker exec face-service df -h /app/models`
- Check logs: `docker logs face-service | grep -i "model\|error\|download"`

**High memory usage**:
- Reduce `KEYFRAME_MAX_PER_VIDEO` in `.env`
- Reduce `BATCH_SIZE` in `faceRecognitionService.ts`
- See `PERFORMANCE_TUNING.md` for detailed guidance

**Slow detection**:
- Reduce `FACE_DETECTION_SIZE` to 480
- Reduce `KEYFRAME_INTERVAL_SEC` to 10
- Check CPU usage: `docker stats face-service`

**No faces detected**:
- Check image quality — ArcFace needs minimum 64x64 face region
- Lower `FACE_MIN_CONFIDENCE` to 0.50
- Ensure faces are front-facing (profile views have lower accuracy)
