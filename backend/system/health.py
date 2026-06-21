"""System health checks."""

from fastapi import APIRouter
from backend.config import settings

router = APIRouter()


@router.get("/")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "server": "odysseus",
        "host": settings.HOST,
        "port": settings.PORT,
    }
