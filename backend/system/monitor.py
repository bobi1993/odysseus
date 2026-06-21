"""System monitoring — CPU, RAM, disk, GPU."""

import logging
import shutil
from fastapi import APIRouter

router = APIRouter()
log = logging.getLogger("monitor")


@router.get("/resources")
async def get_resources():
    """Get system resource usage."""
    import psutil

    cpu_percent = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "cpu": {
            "percent": cpu_percent,
            "cores": psutil.cpu_count(),
        },
        "memory": {
            "total_gb": round(memory.total / (1024**3), 1),
            "used_gb": round(memory.used / (1024**3), 1),
            "percent": memory.percent,
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 1),
            "used_gb": round(disk.used / (1024**3), 1),
            "percent": disk.percent,
        },
    }


@router.get("/gpu")
async def get_gpu():
    """Get GPU info (NVIDIA only for now)."""
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            gpus = []
            for line in result.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    gpus.append({
                        "name": parts[0],
                        "memory_total_mb": int(parts[1]),
                        "memory_used_mb": int(parts[2]),
                        "utilization": int(parts[3]),
                        "temperature": int(parts[4]),
                    })
            return {"gpus": gpus, "available": True}
    except Exception:
        pass

    return {"gpus": [], "available": False}


@router.get("/ollama")
async def get_ollama_status():
    """Check Ollama local model status."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return {"status": "running", "models": models}
    except Exception:
        pass

    return {"status": "offline", "models": []}
