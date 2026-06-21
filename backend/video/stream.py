"""Video streaming — proxy video and thumbnail streams with Range support."""

import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

router = APIRouter()
log = logging.getLogger("stream")


@router.get("/{video_id}")
async def stream_video(video_id: str, request: Request):
    """Proxy video stream with Range header support."""
    import httpx

    # TODO: Look up video URL from database
    video_url = f"https://example.com/video/{video_id}"

    headers = {}
    if "range" in request.headers:
        headers["Range"] = request.headers["Range"]

    async def stream():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", video_url, headers=headers) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk

    return StreamingResponse(stream(), media_type="video/mp4")


@router.get("/thumb/{video_id}")
async def get_thumbnail(video_id: str):
    """Get video thumbnail."""
    import httpx

    # TODO: Look up thumbnail URL from database
    thumb_url = f"https://example.com/thumb/{video_id}.jpg"

    async with httpx.AsyncClient() as client:
        resp = await client.get(thumb_url)
        if resp.status_code != 200:
            raise HTTPException(404, "Thumbnail not found")

    return StreamingResponse(
        iter([resp.content]),
        media_type="image/jpeg",
    )
