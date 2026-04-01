from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import ResearchTaskCreate, ResearchTaskUpdate
from src.models.task import ResearchTask


async def create_task(db: AsyncSession, payload: ResearchTaskCreate) -> ResearchTask:
    task = ResearchTask(**payload.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_task(db: AsyncSession, task_id: str) -> ResearchTask | None:
    return await db.get(ResearchTask, task_id)


async def list_tasks(db: AsyncSession, limit: int = 20, offset: int = 0) -> list[ResearchTask]:
    result = await db.execute(
        select(ResearchTask).order_by(ResearchTask.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def update_task(
    db: AsyncSession,
    task: ResearchTask,
    payload: ResearchTaskUpdate,
) -> ResearchTask:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, key, value)

    await db.commit()
    await db.refresh(task)
    return task

async def delete_task(db: AsyncSession, task: ResearchTask) -> None:
    await db.delete(task)
    await db.commit()