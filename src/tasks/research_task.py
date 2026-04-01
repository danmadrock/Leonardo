from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import ReportRecordCreate, ResearchTaskUpdate
from src.crud.reports import upsert_report
from src.crud.tasks import get_task, update_task
from src.graph.state import ResearchState
from src.models.task import TaskStage, TaskStatus


async def mark_task_running(db: AsyncSession, task_id: str) -> None:
    task = await get_task(db, task_id)
    if task is None:
        return
    await update_task(
        db,
        task,
        ResearchTaskUpdate(
            status=TaskStatus.running,
            stage=TaskStage.planning,
            started_at=datetime.utcnow(),
            error=None,
        ),
    )


async def mark_task_failed(db: AsyncSession, task_id: str, error: str) -> None:
    task = await get_task(db, task_id)
    if task is None:
        return
    await update_task(
        db,
        task,
        ResearchTaskUpdate(
            status=TaskStatus.failed,
            stage=TaskStage.error,
            error=error,
            completed_at=datetime.utcnow(),
        ),
    )


async def persist_final_state(db: AsyncSession, state: ResearchState) -> None:
    task = await get_task(db, state["task_id"])
    if task is None:
        return
    await update_task(
        db,
        task,
        ResearchTaskUpdate(
            status=TaskStatus.completed if state["status"] == "completed" else TaskStatus.failed,
            stage=TaskStage.done if state["status"] == "completed" else TaskStage.error,
            error=state["error"],
            iterations_used=state["search_iteration"],
            progress_subtasks_total=len(state["subtasks"]),
            progress_subtasks_completed=len(state["subtasks"]),
            progress_papers_collected=len(state["papers"]),
            progress_findings_generated=len(state["findings"]),
            completed_at=datetime.utcnow(),
        ),
    )
    if state["report"] is not None:
        await upsert_report(
            db,
            ReportRecordCreate(
                task_id=state["task_id"],
                markdown=state["report"].raw_markdown,
                structured_report_json=state["report"].model_dump(),
            ),
        )