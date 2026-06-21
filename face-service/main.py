# face-service/main.py
"""
ArcFace Face Recognition Microservice
─────────────────────────────────────
Standalone FastAPI service for performer face detection, recognition,
clustering, and auto-categorization for the VR Video Library.

Model stack:
  - Detection: RetinaFace (via InsightFace)
  - Recognition: ArcFace w600k_r50.onnx (ResNet-50, 512-dim)
  - Fallback: Ollama vision model for ambiguous cases

All models load once at startup and stay in memory. Designed for 16GB RAM hosts
with a 5GB container memory cap.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import cv2
import ffmpeg
import numpy as np
import structlog
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from PIL import Image

# ── Load env ──────────────────────────────────────────────────────────────
load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
FACE_MODEL_NAME = os.getenv("FACE_MODEL_NAME", "buffalo_l")
FACE_MODEL_DIR = os.getenv("FACE_MODEL_DIR", "/app/models")
FACE_DETECTION_SIZE = int(os.getenv("FACE_DETECTION_SIZE", "640"))
FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.35"))
FACE_CLUSTER_THRESHOLD = float(os.getenv("FACE_CLUSTER_THRESHOLD", "0.50"))
FACE_MIN_CONFIDENCE = float(os.getenv("FACE_MIN_CONFIDENCE", "0.60"))
KEYFRAME_INTERVAL_SEC = int(os.getenv("KEYFRAME_INTERVAL_SEC", "5"))
KEYFRAME_MAX_PER_VIDEO = int(os.getenv("KEYFRAME_MAX_PER_VIDEO", "20"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:latest")

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=LOG_LEVEL,
)
logger = structlog.get_logger("face-service")

# ── Global model refs (loaded once at startup) ────────────────────────────
_face_analyzer: Optional[object] = None  # InsightFace FaceAnalysis
_arcface_model: Optional[object] = None  # Direct ArcFace ONNX if needed
_model_loaded: bool = False


# ── Pydantic models ───────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: str
    uptime_sec: float


class FaceDetection(BaseModel):
    bbox: list[float]  # [x1, y1, x2, y2]
    confidence: float
    landmarks: list[list[float]]  # 5-point landmarks
    descriptor: list[float]  # 512-dim ArcFace embedding


class DetectionResponse(BaseModel):
    faces: list[FaceDetection]
    image_width: int
    image_height: int
    processing_time_ms: float


class MatchRequest(BaseModel):
    descriptor: list[float]  # 512-dim query embedding
    gallery: list[list[float]]  # Nx512 gallery embeddings
    threshold: float = FACE_MATCH_THRESHOLD


class MatchResult(BaseModel):
    index: int
    similarity: float


class MatchResponse(BaseModel):
    matches: list[MatchResult]
    query_time_ms: float


class ClusterRequest(BaseModel):
    descriptors: list[list[float]]  # Nx512
    threshold: float = FACE_CLUSTER_THRESHOLD


class ClusterAssignment(BaseModel):
    cluster_id: int
    representative_idx: int
    member_indices: list[int]
    avg_similarity: float


class ClusterResponse(BaseModel):
    clusters: list[ClusterAssignment]
    num_input: int
    num_clusters: int
    processing_time_ms: float


class KeyframeRequest(BaseModel):
    video_path: str
    interval_sec: int = KEYFRAME_INTERVAL_SEC
    max_frames: int = KEYFRAME_MAX_PER_VIDEO


class KeyframeInfo(BaseModel):
    timestamp_sec: float
    frame_number: int
    width: int
    height: int
    temp_path: str


class KeyframeResponse(BaseModel):
    keyframes: list[KeyframeInfo]
    duration_sec: float
    total_frames: int
    processing_time_ms: float


class OllamaFallbackRequest(BaseModel):
    image_base64: str
    prompt: str = "Describe the person in this image: gender, approximate age, distinctive features. Return JSON."


# ── Model loading ────────────────────────────────────────────────────────
def load_models():
    """Load ArcFace + RetinaFace models once at startup. ~1.5GB RAM."""
    global _face_analyzer, _arcface_model, _model_loaded

    logger.info("loading_models", model=FACE_MODEL_NAME, model_dir=FACE_MODEL_DIR)

    try:
        import insightface
        from insightface.app import FaceAnalysis

        # RetinaFace detection + ArcFace recognition in one analyzer
        _face_analyzer = FaceAnalysis(
            name=FACE_MODEL_NAME,
            root=FACE_MODEL_DIR,
            providers=["CPUExecutionProvider"],  # CPU-only for 16GB constraint
        )
        _face_analyzer.prepare(
            ctx_id=0,
            det_size=(FACE_DETECTION_SIZE, FACE_DETECTION_SIZE),
        )

        _model_loaded = True
        logger.info("models_loaded", model=FACE_MODEL_NAME)

    except ImportError:
        logger.warning("insightface_not_installed",
                       msg="Install insightface>=0.7.3 for production use. "
                           "Service will run in degraded mode (no face detection).")
        _model_loaded = False

    except Exception as exc:
        logger.error("model_load_error", error=str(exc))
        _model_loaded = False


# ── App lifecycle ────────────────────────────────────────────────────────
_startup_time = time.monotonic()


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_models()
    yield
    logger.info("shutting_down")


app = FastAPI(
    title="VR Face Recognition Service",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Helpers ───────────────────────────────────────────────────────────────
def _bytes_to_cv2(data: bytes) -> np.ndarray:
    """Decode image bytes to OpenCV BGR numpy array."""
    buf = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image")
    return img


def _pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
    """Convert PIL Image to OpenCV BGR."""
    rgb = np.array(pil_img.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _cv2_to_pil(cv2_img: np.ndarray) -> Image.Image:
    """Convert OpenCV BGR to PIL RGB."""
    rgb = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def _l2_normalize(v: np.ndarray) -> np.ndarray:
    """L2-normalize a vector (or row-wise for 2D)."""
    if v.ndim == 1:
        norm = np.linalg.norm(v)
        return v / norm if norm > 1e-10 else v
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-10)
    return v / norms


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two L2-normalized vectors."""
    return float(np.dot(a, b))


# ── Healthcheck ───────────────────────────────────────────────────────────
@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy" if _model_loaded else "degraded",
        model_loaded=_model_loaded,
        model_name=FACE_MODEL_NAME,
        uptime_sec=round(time.monotonic() - _startup_time, 1),
    )


# ── Phase 1: Enhanced keyframe extraction ────────────────────────────────
@app.post("/api/keyframes/extract", response_model=KeyframeResponse)
async def extract_keyframes(
    video_path: str = Form(...),
    interval_sec: int = Form(KEYFRAME_INTERVAL_SEC),
    max_frames: int = Form(KEYFRAME_MAX_PER_VIDEO),
):
    """
    Extract keyframes from a video file using ffmpeg.
    Returns paths to temporary frame images + metadata.
    Used by the Phase 1 enhanced face-api.js pipeline.
    """
    t0 = time.monotonic()

    if not Path(video_path).exists():
        raise HTTPException(404, f"Video not found: {video_path}")

    try:
        # Probe video duration and frame count
        probe = ffmpeg.probe(video_path)
        video_stream = next(
            s for s in probe["streams"] if s["codec_type"] == "video"
        )
        duration = float(video_stream.get("duration", probe["format"].get("duration", 0)))
        total_frames = int(video_stream.get("nb_frames", 0))
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
    except Exception as exc:
        raise HTTPException(400, f"Could not probe video: {exc}")

    # Calculate timestamps
    num_frames = min(max_frames, int(duration / interval_sec)) if interval_sec > 0 else 0
    timestamps = [i * interval_sec for i in range(num_frames)]

    keyframes = []
    tmp_dir = Path(tempfile.mkdtemp(prefix="vrframes_"))

    for i, ts in enumerate(timestamps):
        out_path = str(tmp_dir / f"frame_{i:04d}.jpg")
        try:
            (
                ffmpeg
                .input(video_path, ss=ts)
                .output(out_path, vframes=1, qscale=2)
                .overwrite_output()
                .run(quiet=True)
            )
            keyframes.append(KeyframeInfo(
                timestamp_sec=ts,
                frame_number=int(ts * 30),  # approximate
                width=width,
                height=height,
                temp_path=out_path,
            ))
        except ffmpeg.Error as exc:
            logger.warning("keyframe_extract_error", ts=ts, error=str(exc))

    elapsed = (time.monotonic() - t0) * 1000
    return KeyframeResponse(
        keyframes=keyframes,
        duration_sec=duration,
        total_frames=total_frames,
        processing_time_ms=round(elapsed, 1),
    )


# ── Phase 2: Face detection ──────────────────────────────────────────────
@app.post("/api/faces/detect", response_model=DetectionResponse)
async def detect_faces(
    file: UploadFile = File(...),
    max_faces: int = Query(10, ge=1, le=50),
    det_size: int = Query(FACE_DETECTION_SIZE, ge=160, le=1024),
):
    """
    Detect faces in an image and return bounding boxes + ArcFace descriptors.
    Primary endpoint for both Phase 1 (enhanced face-api.js) and Phase 2 (full ArcFace).
    """
    t0 = time.monotonic()

    if not _model_loaded:
        raise HTTPException(503, "Face model not loaded. Check /api/health.")

    # Read + validate image
    try:
        contents = await file.read()
        img = _bytes_to_cv2(contents)
    except Exception as exc:
        raise HTTPException(400, f"Invalid image: {exc}")

    h, w = img.shape[:2]

    try:
        # InsightFace detection + embedding in one pass
        faces = _face_analyzer.get(img, max_num=max_faces)
    except Exception as exc:
        logger.error("detection_error", error=str(exc))
        raise HTTPException(500, f"Detection failed: {exc}")

    results = []
    for face in faces:
        # Skip low-confidence detections
        if face.det_score < FACE_MIN_CONFIDENCE:
            continue

        # bbox: [x1, y1, x2, y2]
        bbox = face.bbox.tolist() if hasattr(face.bbox, "tolist") else list(face.bbox)
        # 5-point landmarks
        kps = face.kps.tolist() if hasattr(face.kps, "tolist") else list(face.kps)
        # 512-dim embedding (already L2-normalized by InsightFace)
        embedding = face.embedding.tolist() if hasattr(face.embedding, "tolist") else list(face.embedding)

        # Validate embedding dimension
        if len(embedding) != 512:
            logger.warning("unexpected_embedding_dim", dim=len(embedding))
            continue

        results.append(FaceDetection(
            bbox=[round(v, 1) for v in bbox],
            confidence=round(float(face.det_score), 4),
            landmarks=[[round(p[0], 1), round(p[1], 1)] for p in kps],
            descriptor=[round(v, 6) for v in embedding],
        ))

    elapsed = (time.monotonic() - t0) * 1000
    logger.info("faces_detected", count=len(results), image_size=f"{w}x{h}", ms=round(elapsed, 1))

    return DetectionResponse(
        faces=results,
        image_width=w,
        image_height=h,
        processing_time_ms=round(elapsed, 1),
    )


# ── Face matching ────────────────────────────────────────────────────────
@app.post("/api/faces/match", response_model=MatchResponse)
async def match_faces(request: MatchRequest):
    """
    Match a query descriptor against a gallery of known descriptors.
    Returns sorted matches above threshold.
    Cosine similarity (vectors are pre-normalized).
    """
    t0 = time.monotonic()

    query = np.array(request.descriptor, dtype=np.float32)
    gallery = np.array(request.gallery, dtype=np.float32)

    if query.shape != (512,):
        raise HTTPException(400, f"Query must be 512-dim, got {query.shape}")
    if gallery.ndim != 2 or gallery.shape[1] != 512:
        raise HTTPException(400, f"gallery must be Nx512, got {gallery.shape}")

    # L2-normalize (defensive — should already be normalized)
    query = _l2_normalize(query)
    gallery = _l2_normalize(gallery)

    # Batch cosine similarity: gallery @ query
    similarities = gallery @ query  # (N,)

    matches = []
    for idx in np.argsort(-similarities):  # descending
        sim = float(similarities[idx])
        if sim < request.threshold:
            break
        matches.append(MatchResult(
            index=int(idx),
            similarity=round(sim, 4),
        ))

    elapsed = (time.monotonic() - t0) * 1000
    return MatchResponse(
        matches=matches[:20],  # cap at top 20
        query_time_ms=round(elapsed, 1),
    )


# ── Agglomerative clustering ────────────────────────────────────────────
@app.post("/api/faces/cluster", response_model=ClusterResponse)
async def cluster_faces(request: ClusterRequest):
    """
    Agglomerative clustering of face descriptors.
    Each cluster is represented by its centroid (avg of member descriptors).
    Threshold controls merge distance (cosine similarity >= threshold).
    """
    t0 = time.monotonic()

    descriptors = np.array(request.descriptors, dtype=np.float32)
    if descriptors.ndim != 2 or descriptors.shape[1] != 512:
        raise HTTPException(400, f"Expected Nx512, got {descriptors.shape}")

    n = len(descriptors)
    if n == 0:
        return ClusterResponse(clusters=[], num_input=0, num_clusters=0, processing_time_ms=0)

    descriptors = _l2_normalize(descriptors)

    # Greedy agglomerative clustering (efficient for <10k faces)
    # Each face starts as its own cluster, merge if max similarity >= threshold
    assignments = list(range(n))  # cluster representative index for each face
    visited = [False] * n

    # Precompute pairwise similarities (NxN, symmetric)
    # For large N, do this in chunks; for <5k faces, full matrix is fine
    max_chunk = 5000
    if n <= max_chunk:
        sim_matrix = descriptors @ descriptors.T  # (N, N)
    else:
        sim_matrix = None  # compute on-the-fly

    clusters: dict[int, list[int]] = {i: [i] for i in range(n)}

    for i in range(n):
        if visited[i]:
            continue
        for j in range(i + 1, n):
            if visited[j]:
                continue
            if sim_matrix is not None:
                sim = float(sim_matrix[i, j])
            else:
                sim = _cosine_similarity(descriptors[i], descriptors[j])
            if sim >= request.threshold:
                # Merge j into i's cluster
                clusters[i].extend(clusters[j])
                del clusters[j]
                visited[j] = True
        visited[i] = True

    # Build response
    result = []
    for cluster_id, (rep_idx, members) in enumerate(clusters.items()):
        if not members:
            continue
        member_vecs = descriptors[members]
        centroid = _l2_normalize(member_vecs.mean(axis=0).reshape(1, -1))[0]
        # Avg similarity to centroid
        avg_sim = float(np.mean(member_vecs @ centroid))
        result.append(ClusterAssignment(
            cluster_id=cluster_id,
            representative_idx=rep_idx,
            member_indices=members,
            avg_similarity=round(avg_sim, 4),
        ))

    elapsed = (time.monotonic() - t0) * 1000
    logger.info("faces_clustered", input=n, clusters=len(result), ms=round(elapsed, 1))

    return ClusterResponse(
        clusters=result,
        num_input=n,
        num_clusters=len(result),
        processing_time_ms=round(elapsed, 1),
    )


# ── Ollama vision fallback ──────────────────────────────────────────────
@app.post("/api/faces/describe")
async def describe_face_ollama(request: OllamaFallbackRequest):
    """
    Fallback: use Ollama vision model to describe unknown faces.
    Used for ambiguous detections where ArcFace confidence is low.
    Requires Ollama running with a vision model (e.g., llava).
    """
    import httpx

    if not OLLAMA_BASE_URL:
        raise HTTPException(501, "OLLAMA_BASE_URL not configured")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_VISION_MODEL,
                    "prompt": request.prompt,
                    "images": [request.image_base64],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return {"description": data.get("response", ""), "model": OLLAMA_VISION_MODEL}
    except httpx.ConnectError:
        raise HTTPException(502, "Cannot connect to Ollama")
    except httpx.TimeoutException:
        raise HTTPException(504, "Ollama request timed out")
    except Exception as exc:
        logger.error("ollama_fallback_error", error=str(exc))
        raise HTTPException(500, f"Ollama fallback failed: {exc}")


# ── Batch processing ────────────────────────────────────────────────────
@app.post("/api/faces/batch_detect")
async def batch_detect(
    files: list[UploadFile] = File(...),
    max_faces: int = Query(10, ge=1, le=50),
):
    """
    Detect faces in multiple images. Returns results keyed by filename.
    Used for batch keyframe processing.
    """
    if not _model_loaded:
        raise HTTPException(503, "Model not loaded")

    results = {}
    for file in files:
        try:
            contents = await file.read()
            img = _bytes_to_cv2(contents)
            h, w = img.shape[:2]
            faces = _face_analyzer.get(img, max_num=max_faces)

            file_faces = []
            for face in faces:
                if face.det_score < FACE_MIN_CONFIDENCE:
                    continue
                file_faces.append({
                    "bbox": face.bbox.tolist() if hasattr(face.bbox, "tolist") else list(face.bbox),
                    "confidence": round(float(face.det_score), 4),
                    "descriptor": face.embedding.tolist()[:5] + ["..."] if hasattr(face.embedding, "tolist") else [],
                })
            results[file.filename] = {"faces": file_faces, "size": f"{w}x{h}"}
        except Exception as exc:
            results[file.filename] = {"error": str(exc)}

    return {"results": results, "total_files": len(files)}


# ── Error handlers ───────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def generic_error_handler(request, exc):
    logger.error("unhandled_error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )
