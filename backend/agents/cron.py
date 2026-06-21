"""Cron jobs — scheduled task execution."""

import logging
import time
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from backend.database import get_session, CronJob

router = APIRouter()
log = logging.getLogger("cron")


class CreateCronRequest(BaseModel):
    name: str
    agent_id: str = ""
    schedule: str = "every 1h"
    task: str = ""
    enabled: bool = True


@router.get("/")
async def list_jobs(session: AsyncSession = Depends(get_session)):
    """List all cron jobs."""
    result = await session.execute(select(CronJob).order_by(CronJob.created_at.desc()))
    jobs = result.scalars().all()
    return {
        "jobs": [
            {
                "id": j.id,
                "name": j.name,
                "agent_id": j.agent_id,
                "schedule": j.schedule,
                "task": j.task,
                "enabled": j.enabled,
                "status": j.status,
                "last_run": j.last_run.isoformat() if j.last_run else None,
                "run_count": j.run_count,
            }
            for j in jobs
        ]
    }


@router.post("/")
async def create_job(
    req: CreateCronRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new cron job."""
    job = CronJob(
        id=f"cron_{int(time.time() * 1000)}",
        name=req.name,
        agent_id=req.agent_id,
        schedule=req.schedule,
        task=req.task,
        enabled=req.enabled,
    )
    session.add(job)
    await session.commit()
    return {"id": job.id, "name": job.name}


@router.post("/{job_id}/run")
async def run_job(job_id: str, session: AsyncSession = Depends(get_session)):
    """Manually trigger a cron job."""
    result = await session.execute(select(CronJob).where(CronJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    job.status = "running"
    job.last_run = datetime.utcnow()
    await session.commit()

    # TODO: Dispatch to task queue

    job.status = "idle"
    job.run_count += 1
    await session.commit()

    return {"id": job_id, "status": "completed"}


@router.patch("/{job_id}/toggle")
async def toggle_job(job_id: str, session: AsyncSession = Depends(get_session)):
    """Enable/disable a cron job."""
    result = await session.execute(select(CronJob).where(CronJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    job.enabled = not job.enabled
    await session.commit()
    return {"id": job_id, "enabled": job.enabled}
