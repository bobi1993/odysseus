# Performance Tuning Guide — Face Recognition on 16GB RAM
# ═══════════════════════════════════════════════════════════

## Memory Budget (16GB total)

| Component          | Typical Peak | Notes                              |
|--------------------|-------------|-------------------------------------|
| Odysseus (FastAPI) | 1.5-2.5 GB  | Core app + embeddings + RAG         |
| Ollama (LLM)       | 3-6 GB      | Model-dependent; unload when idle   |
| Face Service       | 1.5-3 GB    | ArcFace model + batch buffers       |
| ChromaDB           | 0.5-1 GB    | Vector store                        |
| SearXNG            | 0.3-0.5 GB  | Search engine                       |
| OS + overhead      | 1-2 GB      | macOS system processes              |
| **Headroom**       | **1-3 GB**  | For spikes, browser, etc.           |

## Face Service Tuning

### Model Selection (RAM impact)
- **w600k_r50** (default): ~166MB on disk, ~1.2GB RAM at runtime
  - Best accuracy/speed tradeoff for 16GB
- **w600k_mbf**: ~80MB on disk, ~0.8GB RAM
  - Lighter alternative; slight accuracy drop
- Avoid w120k_huge variants — they need 3-4GB alone

### ONNX Runtime Settings
```python
# In main.py, when creating the FaceAnalysis session:
import onnxruntime as ort

sess_options = ort.SessionOptions()
sess_options.intra_op_num_threads = 2      # Limit CPU threads
sess_options.inter_op_num_threads = 2
sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
sess_options.enable_mem_pattern = False     # Reduce memory for sequential inference
sess_options.enable_cpu_mem_arena = False   # Pre-allocate, no arena growth

# Use these in FaceAnalysis providers:
providers = [
    ("CPUExecutionProvider", {
        "arena_extend_strategy": "kSameAsRequested",  # Don't over-allocate
    })
]
```

### Batch Processing Tuning
- `BATCH_SIZE = 5` (in faceRecognitionService.ts): Good default
  - Increase to 10 if RAM allows (monitor with `ps aux | grep face`)
  - Decrease to 3 if OOM during batch scans
- `KEYFRAME_MAX_PER_VIDEO = 20`: Limits peak memory per video
  - Reduce to 10 for 4K videos (larger frames = more RAM)
- `FACE_DETECTION_SIZE = 640`: Good default
  - Reduce to 480 for faster processing (slight accuracy drop)
  - Increase to 832 for small/distant faces (more RAM + time)

### Descriptor Storage
- Each 512-dim float32 descriptor = 2048 bytes
- 100k faces = ~200MB for descriptors alone
- Store as BLOB in SQLite (not JSON) for compactness
- For >500k faces, consider a dedicated vector DB (ChromaDB)

## Docker Memory Limits

```yaml
# docker-compose.yml
face-service:
  deploy:
    resources:
      limits:
        memory: 5G      # Hard cap — OOM kill if exceeded
      reservations:
        memory: 512M    # Guaranteed minimum
```

## Ollama Model Unloading

The cron job unloads idle Ollama models every 30 min. Coordinate with face scans:
- Schedule face scans when Ollama is unloaded (less RAM pressure)
- Or use a smaller Ollama model (llava:7b instead of llava:13b)

```bash
# Check current Ollama memory usage
curl http://localhost:11434/api/ps

# Manually unload before a big scan
curl http://localhost:11434/api/generate -d '{"model":"llava","keep_alive":0}'
```

## SQLite Performance

### PRAGMA settings (already in schema)
```sql
PRAGMA journal_mode=WAL;     -- Write-Ahead Logging for concurrent reads
PRAGMA cache_size=-8000;     -- 8MB page cache (increase to -20000 for 20MB)
PRAGMA mmap_size=268435456;  -- 256MB memory-mapped I/O
PRAGMA temp_store=MEMORY;    -- Keep temp tables in RAM
```

### Index strategy
The migration creates indexes on:
- `performers(slug)` — lookup by URL slug
- `performers(name)` — search
- `face_detections(video_id)` — per-video queries
- `face_detections(performer_id)` — per-performer queries
- `performer_videos(performer_id, video_id)` — unique link

For >100k face detections, add:
```sql
CREATE INDEX IF NOT EXISTS idx_face_detections_descriptor ON face_detections(performer_id, confidence DESC);
```

## Scan Scheduling

### Recommended: Staggered scans
```bash
# In crontab or Odysseus scheduled tasks:
# Scan 10 videos at a time, every hour
0 * * * * /app/scripts/scan_batch.sh --limit 10

# Full re-cluster weekly
0 3 * * 0 /app/scripts/recluster.sh
```

### Scan batch size
- Small library (<500 videos): Scan all at once
- Medium (500-2000): Batches of 50
- Large (2000+): Batches of 20, spread across hours

## Monitoring

### Check face service memory
```bash
docker stats face-service --no-stream
```

### Check model load time
```bash
curl -s http://localhost:8050/api/health | jq '.uptime_sec'
# First request after startup: model loads (~15-30s for w600k_r50)
```

### Log analysis
```bash
# Watch for OOM kills
docker logs face-service 2>&1 | grep -i "memory\|oom\|killed"

# Check scan performance
docker logs face-service 2>&1 | grep "faces_detected\|faces_clustered"
```

## Error Recovery

### If face service OOMs:
1. Reduce `KEYFRAME_MAX_PER_VIDEO` to 10
2. Reduce `BATCH_SIZE` to 3
3. Reduce `FACE_DETECTION_SIZE` to 480
4. Add swap space (last resort, slow)

### If scans are too slow:
1. Reduce `KEYFRAME_INTERVAL_SEC` to 10 (fewer frames)
2. Reduce `KEYFRAME_MAX_PER_VIDEO` to 10
3. Use `FACE_DETECTION_SIZE=480`
4. Skip videos < 30 seconds

### If accuracy is low:
1. Increase `FACE_DETECTION_SIZE` to 832
2. Lower `FACE_MIN_CONFIDENCE` to 0.50
3. Lower `FACE_MATCH_THRESHOLD` to 0.30
4. Increase `KEYFRAME_MAX_PER_VIDEO` to 30
