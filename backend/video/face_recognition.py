"""
Face Recognition Bridge — Python → Node.js face-recognition service.

Wraps the existing Node.js face-recognition service at:
  /Users/johndoe/Desktop/vr video/backend/services/face-recognition.js

Uses subprocess to call the Node.js service for face detection/scanning.
Provides Python async functions that the FastAPI routes can call.
"""

import asyncio
import json
import logging
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Optional

from backend.config import settings

log = logging.getLogger("face_bridge")

VR_BACKEND_DIR = Path(settings.VR_BACKEND_DIR)
FACE_SERVICE_SCRIPT = VR_BACKEND_DIR / "services" / "face-recognition.js"

# Pre-escape the DB path for use in JS string literals
_DB_PATH_ESCAPED = settings.VR_DATABASE_PATH.replace("'", "\\'")


def _check_node_available() -> bool:
    """Check if Node.js is installed and available."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _check_service_files() -> bool:
    """Check that the face-recognition service files exist."""
    if not FACE_SERVICE_SCRIPT.exists():
        log.error("Face recognition service not found: %s", FACE_SERVICE_SCRIPT)
        return False
    return True


async def _run_node_script(script_code: str, timeout: int = 30) -> dict:
    """Run a Node.js script snippet in the VR backend directory and return parsed JSON."""
    if not _check_node_available():
        raise RuntimeError("Node.js is not available on this system")

    if not _check_service_files():
        raise RuntimeError("Face recognition service files not found")

    cmd = ["node", "--input-type=module", "-e", script_code]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(VR_BACKEND_DIR),
            env={**os.environ, "NODE_PATH": str(VR_BACKEND_DIR / "node_modules")},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            log.error("Node.js script error: %s", err_msg)
            raise RuntimeError(f"Face recognition error: {err_msg[:500]}")

        output = stdout.decode("utf-8", errors="replace").strip()
        if not output:
            return {}

        # Find the last line that looks like JSON
        for line in reversed(output.split("\n")):
            line = line.strip()
            if line.startswith("{") or line.startswith("["):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue

        # Fallback: try to parse entire output
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            log.warning("Could not parse Node.js output as JSON: %s", output[:200])
            return {"raw_output": output}

    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError(f"Face recognition timed out after {timeout}s")


def _sync_db_query(query: str, params: tuple = ()) -> list:
    """Synchronous DB query helper."""
    db_path = settings.VR_DATABASE_PATH
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _sync_db_execute(query: str, params: tuple = ()) -> dict:
    """Synchronous DB execute helper."""
    db_path = settings.VR_DATABASE_PATH
    if not Path(db_path).exists():
        return {"status": "error", "error": "Database not found"}
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(query, params)
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()


# ── Public API ──────────────────────────────────────────────────────────


async def get_daemon_status() -> dict:
    """Check the status of the face recognition service."""
    node_ok = _check_node_available()
    files_ok = _check_service_files()

    status = {
        "node_available": node_ok,
        "service_files_found": files_ok,
        "ready": node_ok and files_ok,
        "models_dir": settings.VR_FACE_MODEL_DIR,
        "models_found": False,
        "vr_backend_dir": str(VR_BACKEND_DIR),
    }

    model_dir = Path(settings.VR_FACE_MODEL_DIR)
    if model_dir.exists():
        required = [
            "ssd_mobilenetv1_model-weights_manifest.json",
            "face_landmark_68_model-weights_manifest.json",
            "face_recognition_model-weights_manifest.json",
        ]
        status["models_found"] = all((model_dir / f).exists() for f in required)
        status["ready"] = status["ready"] and status["models_found"]

    return status


async def get_performers() -> list:
    """Get all named performers from the VR database."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _sync_db_query,
        "SELECT id, name, video_count, cluster_count, thumbnail_url, created_at, updated_at "
        "FROM performers ORDER BY name",
    )


async def get_performer(performer_id: str) -> Optional[dict]:
    """Get a single performer with their clusters and videos."""
    loop = asyncio.get_event_loop()

    def _read():
        db_path = settings.VR_DATABASE_PATH
        if not Path(db_path).exists():
            return None
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT * FROM performers WHERE id = ?", (performer_id,)).fetchone()
            if not row:
                return None

            performer = dict(row)

            # Clusters v2
            clusters_v2 = conn.execute(
                "SELECT id, performer_id, face_count, video_count, avg_quality, created_at, updated_at "
                "FROM face_clusters_v2 WHERE performer_id = ?",
                (performer_id,),
            ).fetchall()
            performer["clusters_v2"] = [dict(c) for c in clusters_v2]

            # Clusters v1
            clusters_v1 = conn.execute(
                "SELECT id, performer_id, face_count, created_at, updated_at "
                "FROM face_clusters WHERE performer_id = ?",
                (performer_id,),
            ).fetchall()
            performer["clusters_v1"] = [dict(c) for c in clusters_v1]

            # Videos via performer_videos
            pv_rows = conn.execute(
                "SELECT pv.video_id, pv.confidence, v.title, v.thumbnail_url, v.source_type "
                "FROM performer_videos pv "
                "LEFT JOIN videos v ON v.id = pv.video_id "
                "WHERE pv.performer_id = ? "
                "ORDER BY pv.confidence DESC",
                (performer_id,),
            ).fetchall()
            performer["videos"] = [dict(r) for r in pv_rows]

            return performer
        finally:
            conn.close()

    return await loop.run_in_executor(None, _read)


async def get_clusters(include_unnamed: bool = True) -> list:
    """Get all face clusters (optionally only unnamed ones)."""
    loop = asyncio.get_event_loop()

    def _read():
        db_path = settings.VR_DATABASE_PATH
        if not Path(db_path).exists():
            return []
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            clusters = {}

            v1_rows = conn.execute(
                "SELECT id, performer_id, face_count, created_at, updated_at FROM face_clusters"
            ).fetchall()
            for r in v1_rows:
                d = dict(r)
                clusters[d["id"]] = {
                    "id": d["id"],
                    "performer_id": d.get("performer_id"),
                    "face_count": d.get("face_count", 0),
                    "video_count": 0,
                    "avg_quality": 0,
                    "created_at": d.get("created_at"),
                    "updated_at": d.get("updated_at"),
                }

            v2_rows = conn.execute(
                "SELECT id, performer_id, face_count, video_count, avg_quality, created_at, updated_at "
                "FROM face_clusters_v2"
            ).fetchall()
            for r in v2_rows:
                d = dict(r)
                clusters[d["id"]] = {
                    "id": d["id"],
                    "performer_id": d.get("performer_id"),
                    "face_count": d.get("face_count", 0),
                    "video_count": d.get("video_count", 0),
                    "avg_quality": d.get("avg_quality", 0),
                    "created_at": d.get("created_at"),
                    "updated_at": d.get("updated_at"),
                }

            result = list(clusters.values())
            if not include_unnamed:
                result = [c for c in result if c.get("performer_id")]

            result.sort(key=lambda c: (0 if c.get("performer_id") else 1, -c.get("face_count", 0)))
            return result
        finally:
            conn.close()

    return await loop.run_in_executor(None, _read)


async def get_unnamed_clusters() -> list:
    """Get all unnamed face clusters."""
    clusters = await get_clusters(include_unnamed=True)
    return [c for c in clusters if not c.get("performer_id")]


async def scan_video(video_id: str, video_info: Optional[dict] = None) -> dict:
    """
    Trigger a face scan on a single video.
    Calls the Node.js face-recognition service via subprocess.
    """
    status = await get_daemon_status()
    if not status["ready"]:
        return {
            "status": "error",
            "error": "Face recognition service not ready",
            "details": status,
        }

    video_json = json.dumps(video_id)
    script = (
        "import { scanVideoWithKeyframes } from './services/face-recognition.js';\n"
        "import { openDb } from './lib/db.js';\n"
        "import { setDb } from './services/face-recognition.js';\n"
        f"const db = openDb('{_DB_PATH_ESCAPED}');\n"
        "setDb(db);\n"
        f"const videoId = {video_json};\n"
        "const video = db.prepare('SELECT id, title, source_type as source, thumbnail_url FROM videos WHERE id = ?').get(videoId);\n"
        "if (!video) {\n"
        "  console.log(JSON.stringify({ status: 'error', error: 'Video not found' }));\n"
        "  process.exit(0);\n"
        "}\n"
        "try {\n"
        "  const result = await scanVideoWithKeyframes(videoId, video);\n"
        "  console.log(JSON.stringify({ status: 'ok', result }));\n"
        "} catch (err) {\n"
        "  console.log(JSON.stringify({ status: 'error', error: err.message }));\n"
        "}\n"
    )

    try:
        result = await _run_node_script(script, timeout=120)
        return result
    except RuntimeError as e:
        return {"status": "error", "error": str(e)}


async def batch_scan(video_ids: Optional[list] = None, limit: int = 500) -> dict:
    """
    Batch scan videos for face recognition.
    If video_ids is None, scans all unscanned videos up to the limit.
    """
    status = await get_daemon_status()
    if not status["ready"]:
        return {
            "status": "error",
            "error": "Face recognition service not ready",
            "details": status,
        }

    if video_ids:
        placeholder = ",".join(f"'{vid}'" for vid in video_ids)
        where_clause = f"WHERE v.id IN ({placeholder})"
    else:
        where_clause = ""

    limit_val = limit

    script = (
        "import { batchScanAdvanced } from './services/face-recognition.js';\n"
        "import { openDb } from './lib/db.js';\n"
        "import { setDb } from './services/face-recognition.js';\n"
        f"const db = openDb('{_DB_PATH_ESCAPED}');\n"
        "setDb(db);\n"
        f"const videos = db.prepare(`\n"
        f"  SELECT v.id, v.title, v.source_type as source, v.thumbnail_url\n"
        f"  FROM videos v\n"
        f"  LEFT JOIN face_cluster_videos fcv ON fcv.video_id = v.id\n"
        f"  {where_clause}\n"
        f"  GROUP BY v.id\n"
        f"  HAVING COUNT(fcv.id) = 0\n"
        f"  LIMIT ?\n"
        f"`).all({limit_val});\n"
        "console.log(JSON.stringify({ status: 'ok', videos_found: videos.length }));\n"
        "if (videos.length > 0) {\n"
        "  try {\n"
        "    const result = await batchScanAdvanced(videos.map(v => v.id), { extractKeyframes: true, hierarchical: true });\n"
        "    console.log(JSON.stringify({ status: 'ok', result }));\n"
        "  } catch (err) {\n"
        "    console.log(JSON.stringify({ status: 'error', error: err.message }));\n"
        "  }\n"
        "}\n"
    )

    try:
        result = await _run_node_script(script, timeout=600)
        return result
    except RuntimeError as e:
        return {"status": "error", "error": str(e)}


async def name_cluster(cluster_id: str, performer_name: str) -> dict:
    """Name a face cluster, creating or merging into a performer."""
    status = await get_daemon_status()
    if not status["ready"]:
        return {
            "status": "error",
            "error": "Face recognition service not ready",
            "details": status,
        }

    cid_json = json.dumps(cluster_id)
    pname_json = json.dumps(performer_name)
    script = (
        "import { nameCluster } from './services/face-recognition.js';\n"
        "import { openDb } from './lib/db.js';\n"
        "import { setDb } from './services/face-recognition.js';\n"
        f"const db = openDb('{_DB_PATH_ESCAPED}');\n"
        "setDb(db);\n"
        f"try {{\n"
        f"  const result = nameCluster({cid_json}, {pname_json});\n"
        f"  console.log(JSON.stringify({{ status: 'ok', result }}));\n"
        f"}} catch (err) {{\n"
        f"  console.log(JSON.stringify({{ status: 'error', error: err.message }}));\n"
        f"}}\n"
    )

    try:
        result = await _run_node_script(script, timeout=30)
        return result
    except RuntimeError as e:
        return {"status": "error", "error": str(e)}


async def merge_clusters(cluster_ids: list, performer_name: str) -> dict:
    """Merge multiple face clusters into a single performer."""
    status = await get_daemon_status()
    if not status["ready"]:
        return {
            "status": "error",
            "error": "Face recognition service not ready",
            "details": status,
        }

    ids_json = json.dumps(cluster_ids)
    pname_json = json.dumps(performer_name)
    script = (
        "import { mergeMultipleClusters } from './services/face-recognition.js';\n"
        "import { openDb } from './lib/db.js';\n"
        "import { setDb } from './services/face-recognition.js';\n"
        f"const db = openDb('{_DB_PATH_ESCAPED}');\n"
        "setDb(db);\n"
        f"try {{\n"
        f"  const result = await mergeMultipleClusters({ids_json}, {pname_json}, true);\n"
        f"  console.log(JSON.stringify({{ status: 'ok', result }}));\n"
        f"}} catch (err) {{\n"
        f"  console.log(JSON.stringify({{ status: 'error', error: err.message }}));\n"
        f"}}\n"
    )

    try:
        result = await _run_node_script(script, timeout=60)
        return result
    except RuntimeError as e:
        return {"status": "error", "error": str(e)}


async def unname_cluster(cluster_id: str) -> dict:
    """Remove performer name from a cluster."""
    status = await get_daemon_status()
    if not status["ready"]:
        return {
            "status": "error",
            "error": "Face recognition service not ready",
            "details": status,
        }

    cid_json = json.dumps(cluster_id)
    script = (
        "import { unnameCluster } from './services/face-recognition.js';\n"
        "import { openDb } from './lib/db.js';\n"
        "import { setDb } from './services/face-recognition.js';\n"
        f"const db = openDb('{_DB_PATH_ESCAPED}');\n"
        "setDb(db);\n"
        f"try {{\n"
        f"  const result = unnameCluster({cid_json});\n"
        f"  console.log(JSON.stringify({{ status: 'ok', result }}));\n"
        f"}} catch (err) {{\n"
        f"  console.log(JSON.stringify({{ status: 'error', error: err.message }}));\n"
        f"}}\n"
    )

    try:
        result = await _run_node_script(script, timeout=30)
        return result
    except RuntimeError as e:
        return {"status": "error", "error": str(e)}


async def delete_cluster(cluster_id: str) -> dict:
    """Delete a face cluster."""
    loop = asyncio.get_event_loop()

    def _delete():
        db_path = settings.VR_DATABASE_PATH
        if not Path(db_path).exists():
            return {"status": "error", "error": "Database not found"}
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("DELETE FROM face_cluster_videos WHERE cluster_id = ?", (cluster_id,))
            conn.execute("DELETE FROM face_clusters WHERE id = ?", (cluster_id,))
            conn.execute("DELETE FROM face_clusters_v2 WHERE id = ?", (cluster_id,))
            conn.commit()
            return {"status": "ok", "deleted": cluster_id}
        except Exception as e:
            conn.rollback()
            return {"status": "error", "error": str(e)}
        finally:
            conn.close()

    return await loop.run_in_executor(None, _delete)


async def delete_performer(performer_id: str) -> dict:
    """Delete a performer and their associations."""
    loop = asyncio.get_event_loop()

    def _delete():
        db_path = settings.VR_DATABASE_PATH
        if not Path(db_path).exists():
            return {"status": "error", "error": "Database not found"}
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("UPDATE face_clusters SET performer_id = NULL WHERE performer_id = ?", (performer_id,))
            conn.execute("UPDATE face_clusters_v2 SET performer_id = NULL WHERE performer_id = ?", (performer_id,))
            conn.execute("DELETE FROM performer_videos WHERE performer_id = ?", (performer_id,))
            conn.execute("DELETE FROM performers WHERE id = ?", (performer_id,))
            conn.commit()
            return {"status": "ok", "deleted": performer_id}
        except Exception as e:
            conn.rollback()
            return {"status": "error", "error": str(e)}
        finally:
            conn.close()

    return await loop.run_in_executor(None, _delete)


async def get_stats() -> dict:
    """Get face recognition statistics."""
    loop = asyncio.get_event_loop()

    def _stats():
        db_path = settings.VR_DATABASE_PATH
        if not Path(db_path).exists():
            return {"error": "Database not found"}
        conn = sqlite3.connect(db_path)
        try:
            total_videos = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
            total_performers = conn.execute("SELECT COUNT(*) FROM performers").fetchone()[0]
            total_clusters_v1 = conn.execute("SELECT COUNT(*) FROM face_clusters").fetchone()[0]
            total_clusters_v2 = conn.execute("SELECT COUNT(*) FROM face_clusters_v2").fetchone()[0]
            total_cluster_videos = conn.execute("SELECT COUNT(*) FROM face_cluster_videos").fetchone()[0]
            total_performer_videos = conn.execute("SELECT COUNT(*) FROM performer_videos").fetchone()[0]
            unnamed_v1 = conn.execute("SELECT COUNT(*) FROM face_clusters WHERE performer_id IS NULL").fetchone()[0]
            unnamed_v2 = conn.execute("SELECT COUNT(*) FROM face_clusters_v2 WHERE performer_id IS NULL").fetchone()[0]

            return {
                "total_videos": total_videos,
                "total_performers": total_performers,
                "total_clusters_v1": total_clusters_v1,
                "total_clusters_v2": total_clusters_v2,
                "total_clusters": max(total_clusters_v1, total_clusters_v2),
                "unnamed_clusters": max(unnamed_v1, unnamed_v2),
                "total_cluster_videos": total_cluster_videos,
                "total_performer_videos": total_performer_videos,
            }
        finally:
            conn.close()

    return await loop.run_in_executor(None, _stats)
