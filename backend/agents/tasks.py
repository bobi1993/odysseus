"""Task queue — create, dispatch, execute, track."""

import json
import logging
import time
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from backend.database import get_session, Task

router = APIRouter()
log = logging.getLogger("tasks")


class CreateTaskRequest(BaseModel):
    title: str
    body: str = ""
    assignee: str = "default"
    priority: str = "normal"
    parents: list[str] = []


@router.get("/")
async def list_tasks(
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """List all tasks, optionally filtered by status."""
    query = select(Task).order_by(Task.created_at.desc())
    if status:
        query = query.where(Task.status == status)
    result = await session.execute(query)
    tasks = result.scalars().all()
    return {
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "body": t.body,
                "assignee": t.assignee,
                "priority": t.priority,
                "status": t.status,
                "result": t.result,
                "dispatch_method": t.dispatch_method,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ]
    }


@router.post("/")
async def create_task(
    req: CreateTaskRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new task."""
    task = Task(
        id=f"t_{int(time.time() * 1000)}",
        title=req.title,
        body=req.body,
        assignee=req.assignee,
        priority=req.priority,
        status="ready",
        parents=req.parents,
    )
    session.add(task)
    await session.commit()
    return {"id": task.id, "title": task.title, "status": task.status}


@router.post("/{task_id}/dispatch")
async def dispatch_task(
    task_id: str,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Dispatch a task for execution."""
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status not in ("ready", "failed"):
        raise HTTPException(400, f"Task is {task.status}")

    task.status = "running"
    task.dispatch_method = "queued"
    await session.commit()

    background.add_task(_execute_task, task_id)

    return {"id": task_id, "status": "running"}


async def _execute_task(task_id: str):
    """Background task execution."""
    from backend.database import async_session
    async with async_session() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return

        try:
            # Execute via AI Gateway
            import httpx
            from backend.config import settings

            full_task = f"{task.title}\n{task.body}" if task.body else task.title

            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(
                    f"{settings.AI_GATEWAY_URL}/api/execute",
                    json={"task": full_task, "model": settings.DEFAULT_MODEL},
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    task.status = "done"
                    task.result = data.get("output", "")[:2000]
                    task.dispatch_method = "ai-gateway"
                else:
                    task.status = "failed"
                    task.result = f"HTTP {resp.status_code}: {resp.text[:500]}"
                    task.dispatch_method = "ai-gateway"
        except Exception as e:
            task.status = "failed"
            task.result = str(e)[:500]
            task.dispatch_method = "error"

        task.completed_at = datetime.utcnow()
        await session.commit()
        log.info(f"Task {task_id}: {task.status}")


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: str,
    result: str = "",
    session: AsyncSession = Depends(get_session),
):
    """Mark a task as completed."""
    r = await session.execute(select(Task).where(Task.id == task_id))
    task = r.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    task.status = "done"
    task.result = result
    task.completed_at = datetime.utcnow()
    await session.commit()
    return {"id": task_id, "status": "done"}
