"""Chat completions — streaming and non-streaming via all LLM providers."""

import json
import logging
import time
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_session, ChatSession

router = APIRouter()
log = logging.getLogger("chat")


class ChatRequest(BaseModel):
    model: str = ""
    messages: list[dict] = []
    max_tokens: int = 4096
    temperature: float = 0.7
    stream: bool = False
    session_id: str = ""


class CreateSessionRequest(BaseModel):
    title: str = "New Chat"
    model: str = ""
    provider: str = ""


def _resolve_provider(model: str):
    """Resolve provider config from model name. Returns (provider_name, base_url, api_key, model_id)."""
    if "/" in model:
        provider_name = model.split("/")[0]
        if provider_name in settings.LLM_PROVIDERS:
            cfg = settings.LLM_PROVIDERS[provider_name]
            env_key = cfg.get("env_key", "")
            api_key = getattr(settings, env_key, "") if env_key else ""
            model_id = model.split("/", 1)[1]
            return provider_name, cfg["base_url"], api_key, model_id
    # Default to Ollama first, then OpenRouter
    for fallback in ("ollama", "openrouter"):
        cfg = settings.LLM_PROVIDERS.get(fallback, {})
        env_key = cfg.get("env_key", "")
        api_key = getattr(settings, env_key, "") if env_key else ""
        return fallback, cfg.get("base_url", ""), api_key, model
    return "ollama", "http://localhost:11434/v1", "", model


def _is_retryable_error(status_code: int, error_text: str) -> bool:
    """Check if an error is retryable (auth, credit, rate limit, model/account issues)."""
    if status_code in (401, 402, 403, 429):
        return True
    if status_code == 404:
        # 404 can mean model not found OR account invalid — retry to try other providers
        error_lower = error_text.lower()
        not_found_keywords = ["not found", "not_available", "model_not_available", "unable to access"]
        return any(kw in error_lower for kw in not_found_keywords)
    error_lower = error_text.lower()
    retry_keywords = [
        "credit", "insufficient", "quota", "rate limit",
        "billing", "payment", "exceeded", "unauthorized",
        "forbidden",
    ]
    return any(kw in error_lower for kw in retry_keywords)


def _build_providers_list(primary_name: str, primary_url: str, primary_key: str, model_id: str):
    """Build ordered list of providers to try: primary first, then all others."""
    providers_to_try = []
    seen = set()

    if primary_name == "ollama" or primary_key:
        providers_to_try.append((primary_name, primary_url, primary_key, model_id))
        seen.add(primary_name)

    for name, cfg in settings.LLM_PROVIDERS.items():
        if name in seen:
            continue
        env_key = cfg.get("env_key", "")
        api_key = getattr(settings, env_key, "") if env_key else ""
        if name == "ollama" or api_key:
            providers_to_try.append((name, cfg["base_url"], api_key, model_id))
            seen.add(name)

    return providers_to_try


async def _save_to_session(db_session: AsyncSession, session_id: str,
                            request_messages: list[dict], assistant_content: str):
    """Save chat messages to a session."""
    if not session_id or not assistant_content:
        return
    try:
        sess_result = await db_session.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        sess = sess_result.scalar_one_or_none()
        if not sess:
            return

        # Get existing messages
        msgs = []
        if sess.messages:
            msgs = list(sess.messages) if isinstance(sess.messages, list) else []

        # Add any new user/request messages not already stored
        for msg in request_messages:
            is_dup = False
            for existing in msgs:
                if (existing.get("content") == msg.get("content")
                        and existing.get("role") == msg.get("role")):
                    is_dup = True
                    break
            if not is_dup:
                msgs.append(msg)

        # Add assistant response
        msgs.append({"role": "assistant", "content": assistant_content})

        sess.messages = msgs
        sess.updated_at = datetime.utcnow()
        await db_session.commit()
    except Exception as e:
        log.error(f"Failed to save to session {session_id}: {e}")


# ── Chat Sessions CRUD ──────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    db_session: AsyncSession = Depends(get_session),
):
    """List chat sessions ordered by most recent."""
    query = select(ChatSession).order_by(ChatSession.updated_at.desc()).offset(offset).limit(limit)
    result = await db_session.execute(query)
    sessions = result.scalars().all()

    output = []
    for s in sessions:
        msg_count = 0
        if s.messages and isinstance(s.messages, list):
            msg_count = len(s.messages)
        output.append({
            "id": s.id,
            "title": s.title,
            "model": s.model,
            "provider": s.provider,
            "message_count": msg_count,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        })
    return {"sessions": output, "total": len(output)}


@router.post("/sessions")
async def create_session(
    req: CreateSessionRequest,
    db_session: AsyncSession = Depends(get_session),
):
    """Create a new chat session."""
    sess = ChatSession(
        id=f"s_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}",
        title=req.title,
        model=req.model or settings.DEFAULT_MODEL,
        provider=req.provider or "ollama",
        messages=[],
    )
    db_session.add(sess)
    await db_session.commit()
    return {
        "id": sess.id,
        "title": sess.title,
        "model": sess.model,
        "provider": sess.provider,
        "created_at": sess.created_at.isoformat() if sess.created_at else None,
    }


@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: str,
    db_session: AsyncSession = Depends(get_session),
):
    """Get a chat session with its message history."""
    result = await db_session.execute(select(ChatSession).where(ChatSession.id == session_id))
    sess = result.scalar_one_or_none()
    if not sess:
        raise HTTPException(404, "Session not found")
    messages = []
    if sess.messages and isinstance(sess.messages, list):
        messages = sess.messages
    return {
        "id": sess.id,
        "title": sess.title,
        "model": sess.model,
        "provider": sess.provider,
        "messages": messages,
        "created_at": sess.created_at.isoformat() if sess.created_at else None,
        "updated_at": sess.updated_at.isoformat() if sess.updated_at else None,
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db_session: AsyncSession = Depends(get_session),
):
    """Delete a chat session."""
    result = await db_session.execute(select(ChatSession).where(ChatSession.id == session_id))
    sess = result.scalar_one_or_none()
    if not sess:
        raise HTTPException(404, "Session not found")
    await db_session.delete(sess)
    await db_session.commit()
    return {"id": session_id, "deleted": True}


@router.patch("/sessions/{session_id}")
async def rename_session(
    session_id: str,
    req: CreateSessionRequest,
    db_session: AsyncSession = Depends(get_session),
):
    """Rename a chat session."""
    result = await db_session.execute(select(ChatSession).where(ChatSession.id == session_id))
    sess = result.scalar_one_or_none()
    if not sess:
        raise HTTPException(404, "Session not found")
    sess.title = req.title
    sess.updated_at = datetime.utcnow()
    await db_session.commit()
    return {"id": session_id, "title": req.title}


# ── Chat Completions ────────────────────────────────────────────────────

@router.post("/completions")
async def chat_completions(req: ChatRequest, db_session: AsyncSession = Depends(get_session)):
    """Non-streaming chat completion with fallback providers and session persistence."""
    if not req.model:
        req.model = settings.DEFAULT_MODEL

    primary_name, primary_url, primary_key, model_id = _resolve_provider(req.model)
    providers_to_try = _build_providers_list(primary_name, primary_url, primary_key, model_id)

    if not providers_to_try:
        raise HTTPException(401, "No LLM providers configured. Set at least one API key or ensure Ollama is running.")

    import httpx

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
                "messages": req.messages,
                "max_tokens": req.max_tokens,
                "temperature": req.temperature,
            }

            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )

            if resp.status_code == 200:
                data = resp.json()
                assistant_content = data["choices"][0]["message"]["content"]

                # Save to session
                await _save_to_session(db_session, req.session_id, req.messages, assistant_content)

                return {
                    "model": req.model,
                    "provider": provider_name,
                    "output": assistant_content,
                    "usage": data.get("usage", {}),
                }

            error_text = resp.text
            if _is_retryable_error(resp.status_code, error_text):
                log.warning(f"Provider {provider_name} failed ({resp.status_code}): {error_text[:200]}. Trying next...")
                last_error = f"[{provider_name}] {resp.status_code}: {error_text}"
                continue

            # Non-retryable error
            raise HTTPException(resp.status_code, error_text)

        except HTTPException:
            raise
        except Exception as e:
            last_error = str(e)
            log.warning(f"Provider {provider_name} error: {e}. Trying next...")
            continue

    # All providers failed
    error_detail = last_error or "All providers failed"
    raise HTTPException(502, {
        "error": "All LLM providers failed",
        "detail": error_detail,
        "providers_tried": [p[0] for p in providers_to_try],
    })


@router.post("/stream")
async def chat_stream(req: ChatRequest, db_session: AsyncSession = Depends(get_session)):
    """Streaming chat completion via SSE with fallback providers."""
    if not req.model:
        req.model = settings.DEFAULT_MODEL

    primary_name, primary_url, primary_key, model_id = _resolve_provider(req.model)
    providers_to_try = _build_providers_list(primary_name, primary_url, primary_key, model_id)

    if not providers_to_try:
        raise HTTPException(401, "No LLM providers configured.")

    import httpx

    async def event_stream():
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
                    "messages": req.messages,
                    "max_tokens": req.max_tokens,
                    "temperature": req.temperature,
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
                                last_error = f"[{provider_name}] {resp.status_code}: {error_text[:200]}"
                                log.warning(f"Provider {provider_name} stream failed, trying next...")
                                continue
                            yield f"data: {json.dumps({'error': error_text})}\n\n"
                            yield "data: [DONE]\n\n"
                            return

                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    # Save to session
                                    await _save_to_session(
                                        db_session, req.session_id, req.messages, full_content
                                    )
                                    yield "data: [DONE]\n\n"
                                    return
                                try:
                                    chunk = json.loads(data)
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        full_content += content
                                        yield f"data: {json.dumps({'content': content, 'provider': provider_name})}\n\n"
                                except json.JSONDecodeError:
                                    continue
                        return  # Stream completed successfully

            except Exception as e:
                last_error = str(e)
                log.warning(f"Provider {provider_name} stream error: {e}. Trying next...")
                continue

        # All providers failed
        error_msg = last_error or "All providers failed"
        yield f"data: {json.dumps({'error': error_msg})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
