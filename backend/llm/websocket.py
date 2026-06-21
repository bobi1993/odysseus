"""WebSocket endpoints — real-time chat, task updates, system stats."""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger("ws")

# ── Connection Managers ─────────────────────────────────────────────────


class ConnectionManager:
    """Generic WebSocket connection manager."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        log.info(f"WS client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        log.info(f"WS client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send a message to all connected clients."""
        disconnected = []
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                disconnected.append(conn)
        for conn in disconnected:
            self.disconnect(conn)


chat_manager = ConnectionManager()
tasks_manager = ConnectionManager()
system_manager = ConnectionManager()

# ── Chat WebSocket ──────────────────────────────────────────────────────


async def ws_chat_endpoint(websocket: WebSocket):
    """WebSocket chat endpoint — streaming chat with real-time responses.

    Protocol:
    - Client sends: {"type": "chat", "model": "...", "messages": [...], "session_id": "..."}
    - Server streams: {"type": "token", "content": "...", "provider": "..."}
    - Server sends: {"type": "done"} or {"type": "error", "detail": "..."}
    """
    await chat_manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
                continue

            msg_type = data.get("type", "chat")
            if msg_type != "chat":
                await websocket.send_json({"type": "error", "detail": f"Unknown message type: {msg_type}"})
                continue

            model = data.get("model", "")
            messages = data.get("messages", [])
            session_id = data.get("session_id", "")

            if not messages:
                await websocket.send_json({"type": "error", "detail": "No messages provided"})
                continue

            # Import here to avoid circular imports
            from backend.llm.chat import _resolve_provider, _build_providers_list, _is_retryable_error, _save_to_session
            from backend.config import settings
            from backend.database import async_session

            if not model:
                model = settings.DEFAULT_MODEL

            primary_name, primary_url, primary_key, model_id = _resolve_provider(model)
            providers_to_try = _build_providers_list(primary_name, primary_url, primary_key, model_id)

            if not providers_to_try:
                await websocket.send_json({
                    "type": "error",
                    "detail": "No LLM providers configured.",
                })
                continue

            import httpx

            sent_response = False
            last_error = None

            for provider_name, base_url, api_key, mid in providers_to_try:
                try:
                    headers = {
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://odysseus.local",
                        "X-Title": "Odysseus AI Platform",
                    }
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"

                    payload = {
                        "model": mid,
                        "messages": messages,
                        "max_tokens": data.get("max_tokens", 4096),
                        "temperature": data.get("temperature", 0.7),
                        "stream": True,
                    }

                    full_content = ""
                    async with httpx.AsyncClient(timeout=120) as client:
                        async with client.stream(
                            "POST",
                            f"{base_url}/chat/completions",
                            json=payload,
                            headers=headers,
                        ) as resp:
                            if resp.status_code != 200:
                                error_body = await resp.aread()
                                error_text = error_body.decode()
                                if _is_retryable_error(resp.status_code, error_text):
                                    last_error = f"[{provider_name}] {resp.status_code}"
                                    continue
                                await websocket.send_json({
                                    "type": "error",
                                    "detail": f"[{provider_name}] {resp.status_code}: {error_text[:200]}",
                                })
                                sent_response = True
                                break

                            async for line in resp.aiter_lines():
                                if line.startswith("data: "):
                                    chunk_data = line[6:]
                                    if chunk_data == "[DONE]":
                                        # Save to session
                                        if session_id and full_content:
                                            try:
                                                async with async_session() as db_sess:
                                                    await _save_to_session(
                                                        db_sess, session_id, messages, full_content
                                                    )
                                            except Exception as e:
                                                log.error(f"WS session save error: {e}")

                                        await websocket.send_json({
                                            "type": "done",
                                            "provider": provider_name,
                                            "model": mid,
                                        })
                                        sent_response = True
                                        break
                                    try:
                                        chunk = json.loads(chunk_data)
                                        delta = chunk["choices"][0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            full_content += content
                                            await websocket.send_json({
                                                "type": "token",
                                                "content": content,
                                                "provider": provider_name,
                                            })
                                    except json.JSONDecodeError:
                                        continue
                            else:
                                # Stream ended without [DONE]
                                if full_content:
                                    await websocket.send_json({
                                        "type": "done",
                                        "provider": provider_name,
                                        "model": mid,
                                    })
                                    sent_response = True
                                break

                    if sent_response:
                        break

                except Exception as e:
                    last_error = str(e)
                    log.warning(f"WS provider {provider_name} error: {e}")
                    continue

            if not sent_response:
                error_msg = last_error or "All providers failed"
                await websocket.send_json({
                    "type": "error",
                    "detail": error_msg,
                })

    except WebSocketDisconnect:
        chat_manager.disconnect(websocket)
    except Exception as e:
        log.error(f"Chat WS error: {e}", exc_info=True)
        chat_manager.disconnect(websocket)


# ── Tasks WebSocket ─────────────────────────────────────────────────────

async def ws_tasks_endpoint(websocket: WebSocket):
    """WebSocket task status updates — broadcasts task changes in real-time.

    Protocol:
    - Client sends: {"type": "subscribe", "task_id": "..."} (optional)
    - Server broadcasts: {"type": "task_update", "task": {...}}
    - Client sends: {"type": "ping"} → Server responds: {"type": "pong"}
    """
    await tasks_manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
                continue

            msg_type = data.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "ts": time.time()})
            elif msg_type == "subscribe":
                task_id = data.get("task_id", "")
                await websocket.send_json({
                    "type": "subscribed",
                    "task_id": task_id,
                })
            elif msg_type == "list":
                # Return current task list
                try:
                    from backend.database import async_session
                    from sqlalchemy import select
                    from backend.database import Task

                    async with async_session() as session:
                        result = await session.execute(
                            select(Task).order_by(Task.created_at.desc()).limit(50)
                        )
                        tasks = result.scalars().all()
                        await websocket.send_json({
                            "type": "task_list",
                            "tasks": [
                                {
                                    "id": t.id,
                                    "title": t.title,
                                    "status": t.status,
                                    "priority": t.priority,
                                    "assignee": t.assignee,
                                    "created_at": t.created_at.isoformat() if t.created_at else None,
                                }
                                for t in tasks
                            ],
                        })
                except Exception as e:
                    await websocket.send_json({"type": "error", "detail": str(e)})
            else:
                await websocket.send_json({"type": "error", "detail": f"Unknown type: {msg_type}"})

    except WebSocketDisconnect:
        tasks_manager.disconnect(websocket)
    except Exception as e:
        log.error(f"Tasks WS error: {e}", exc_info=True)
        tasks_manager.disconnect(websocket)


# ── System Stats WebSocket ──────────────────────────────────────────────

async def ws_system_endpoint(websocket: WebSocket):
    """WebSocket system stats — periodic CPU/RAM/disk updates.

    Protocol:
    - Server broadcasts every 2s: {"type": "stats", "cpu": {...}, "memory": {...}, "disk": {...}}
    - Client sends: {"type": "ping"} → Server responds: {"type": "pong"}
    - Client sends: {"type": "get_stats"} → Server responds with immediate stats
    """
    await system_manager.connect(websocket)
    try:
        # Start background stats broadcaster
        stats_task = asyncio.create_task(_broadcast_system_stats(websocket))

        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
                continue

            msg_type = data.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "ts": time.time()})
            elif msg_type == "get_stats":
                stats = _get_system_stats()
                await websocket.send_json({"type": "stats", **stats})
            else:
                await websocket.send_json({"type": "error", "detail": f"Unknown type: {msg_type}"})

    except WebSocketDisconnect:
        system_manager.disconnect(websocket)
    except Exception as e:
        log.error(f"System WS error: {e}", exc_info=True)
        system_manager.disconnect(websocket)


def _get_system_stats() -> dict:
    """Get current system resource usage."""
    import psutil

    cpu_percent = psutil.cpu_percent(interval=0.1)
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
        "timestamp": datetime.utcnow().isoformat(),
    }


async def _broadcast_system_stats(websocket: WebSocket):
    """Broadcast system stats every 2 seconds to a specific client."""
    try:
        while True:
            await asyncio.sleep(2)
            stats = _get_system_stats()
            await websocket.send_json({"type": "stats", **stats})
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as e:
        log.debug(f"Stats broadcast ended: {e}")
