"""Face recognition — performers, clusters, scanning.
Uses the face_recognition bridge to interact with the VR video database
and the Node.js face-recognition service.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from backend.database import get_session, get_vr_session, Performer, FaceCluster, FaceClusterVideo
from backend.video.face_recognition import (
    get_performers as bridge_get_performers,
    get_performer as bridge_get_performer,
    get_clusters as bridge_get_clusters,
    get_unnamed_clusters as bridge_get_unnamed,
    get_stats as bridge_get_stats,
    get_daemon_status,
    scan_video as bridge_scan_video,
    batch_scan as bridge_batch_scan,
    name_cluster as bridge_name_cluster,
    merge_clusters as bridge_merge_clusters,
    unname_cluster as bridge_unname_cluster,
    delete_cluster as bridge_delete_cluster,
    delete_performer as bridge_delete_performer,
)

router = APIRouter()
log = logging.getLogger("faces")


# ── Health & Status ─────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """Check face recognition service health."""
    return await get_daemon_status()


@router.get("/status")
async def status():
    """Full daemon status."""
    return await get_daemon_status()


# ── Performers & Clusters ───────────────────────────────────────────────

@router.get("/")
async def list_performers_and_clusters(
    include_unnamed: bool = Query(True, description="Include unnamed clusters"),
):
    """List all performers and face clusters."""
    performers = await bridge_get_performers()
    clusters = await bridge_get_clusters(include_unnamed=include_unnamed)
    stats = await bridge_get_stats()

    named = []
    unnamed = []
    for c in clusters:
        if c.get("performer_id"):
            named.append(c)
        else:
            unnamed.append(c)

    return {
        "named": performers,
        "unnamed": unnamed,
        "stats": stats,
    }


@router.get("/performers")
async def list_performers():
    """List all named performers."""
    performers = await bridge_get_performers()
    # Enrich with cluster counts
    clusters = await bridge_get_clusters(include_unnamed=False)
    performer_cluster_map = {}
    for c in clusters:
        pid = c.get("performer_id")
        if pid:
            performer_cluster_map[pid] = performer_cluster_map.get(pid, 0) + 1

    return {
        "performers": [
            {
                "id": p["id"],
                "name": p["name"],
                "video_count": p.get("video_count", 0),
                "cluster_count": performer_cluster_map.get(p["id"], 0),
                "thumbnail": p.get("thumbnail_url", ""),
                "created_at": p.get("created_at"),
                "updated_at": p.get("updated_at"),
            }
            for p in performers
        ],
        "stats": await bridge_get_stats(),
    }


@router.get("/performers/{performer_id}")
async def get_performer_detail(performer_id: str):
    """Get performer details with their clusters and videos."""
    performer = await bridge_get_performer(performer_id)
    if not performer:
        raise HTTPException(404, "Performer not found")
    return performer


@router.get("/clusters")
async def list_clusters(
    unnamed_only: bool = Query(False, description="Only unnamed clusters"),
):
    """List face clusters."""
    if unnamed_only:
        clusters = await bridge_get_unnamed()
    else:
        clusters = await bridge_get_clusters(include_unnamed=True)
    return {"clusters": clusters, "stats": await bridge_get_stats()}


@router.get("/stats")
async def get_face_stats():
    """Get face recognition statistics."""
    return await bridge_get_stats()


# ── Scanning ────────────────────────────────────────────────────────────

@router.post("/scan")
async def trigger_scan(video_id: Optional[str] = None):
    """
    Trigger face scan on a single video (if video_id provided)
    or batch scan unscanned videos.
    """
    if video_id:
        result = await bridge_scan_video(video_id)
    else:
        result = await bridge_batch_scan()
    return result


@router.post("/scan/{video_id}")
async def scan_single_video(video_id: str):
    """Scan a single video by ID."""
    result = await bridge_scan_video(video_id)
    return result


@router.post("/batch-scan")
async def batch_scan_videos(
    video_ids: Optional[list[str]] = None,
    limit: int = Query(500, ge=1, le=5000),
):
    """Batch scan unscanned videos or specific video IDs."""
    result = await bridge_batch_scan(video_ids=video_ids, limit=limit)
    return result


# ── Naming & Merging ────────────────────────────────────────────────────

@router.post("/name-cluster")
async def name_face_cluster(
    cluster_id: str,
    performer_name: str,
):
    """Name a face cluster, creating or merging into a performer."""
    if not cluster_id or not performer_name:
        raise HTTPException(400, "cluster_id and performer_name are required")

    result = await bridge_name_cluster(cluster_id, performer_name)
    if result.get("status") == "error":
        raise HTTPException(500, result.get("error", "Unknown error"))
    return result


@router.post("/merge")
async def merge_face_clusters(
    cluster_ids: list[str],
    performer_name: str,
):
    """Merge multiple face clusters into a single performer."""
    if not cluster_ids or len(cluster_ids) < 2:
        raise HTTPException(400, "At least 2 cluster_ids are required")
    if not performer_name:
        raise HTTPException(400, "performer_name is required")

    result = await bridge_merge_clusters(cluster_ids, performer_name)
    if result.get("status") == "error":
        raise HTTPException(500, result.get("error", "Unknown error"))
    return result


@router.post("/unname-cluster")
async def unname_face_cluster(cluster_id: str):
    """Remove performer name from a cluster."""
    if not cluster_id:
        raise HTTPException(400, "cluster_id is required")

    result = await bridge_unname_cluster(cluster_id)
    if result.get("status") == "error":
        raise HTTPException(500, result.get("error", "Unknown error"))
    return result


# ── Deletion ────────────────────────────────────────────────────────────

@router.delete("/cluster/{cluster_id}")
async def delete_face_cluster(cluster_id: str):
    """Delete a face cluster."""
    # Check if cluster exists
    clusters = await bridge_get_clusters(include_unnamed=True)
    found = any(c["id"] == cluster_id for c in clusters)
    if not found:
        raise HTTPException(404, "Cluster not found")

    result = await bridge_delete_cluster(cluster_id)
    if result.get("status") == "error":
        raise HTTPException(500, result.get("error", "Unknown error"))
    return result


@router.delete("/performers/{performer_id}")
async def delete_performer_endpoint(performer_id: str):
    """Delete a performer."""
    performer = await bridge_get_performer(performer_id)
    if not performer:
        raise HTTPException(404, "Performer not found")

    result = await bridge_delete_performer(performer_id)
    if result.get("status") == "error":
        raise HTTPException(500, result.get("error", "Unknown error"))
    return result
