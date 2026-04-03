from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.schemas import ReportRecordCreate, ResearchTaskUpdate
from src.crud.reports import upsert_report
from src.crud.tasks import get_task, update_task
from src.core.logging import bind_task_context, clear_task_context

from src.db.session import SessionLocal
from src.graph.builder import build_graph
from src.graph.state import ResearchState
from src.models.task import TaskStage, TaskStatus
from src.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _task_meta_payload(*, stage: str, state: ResearchState | None = None, error: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"stage": stage}
    if state is not None:
        payload["progress"] = {
            "search_iteration": state["search_iteration"],
            "max_search_iterations": state["max_search_iterations"],
            "subtasks_total": len(state["subtasks"]),
            "subtasks_completed": len(state["subtasks"]),
            "papers_found": len(state["papers"]),
            "findings_extracted": len(state["findings"]),
        }
    if error:
        payload["error"] = error
    return payload


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


async def persist_progress(db: AsyncSession, state: ResearchState) -> None:
    task = await get_task(db, state["task_id"])
    if task is None:
        return

    stage_map = {
        "planning": TaskStage.planning,
        "search": TaskStage.search,
        "analysis": TaskStage.analysis,
        "report": TaskStage.report,
    }
    stage = stage_map.get(state["stage"], TaskStage.planning)

    await update_task(
        db,
        task,
        ResearchTaskUpdate(
            stage=stage,
            iterations_used=state["search_iteration"],
            progress_subtasks_total=len(state["subtasks"]),
            progress_subtasks_completed=len(state["subtasks"]),
            progress_papers_collected=len(state["papers"]),
            progress_findings_generated=len(state["findings"]),
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


async def _execute_research_task(task_id: str, task_handle: Any) -> dict[str, Any]:
    session_factory: async_sessionmaker[AsyncSession] = SessionLocal
    async with session_factory() as db:
        task = await get_task(db, task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        bind_task_context(task_id)
        logger.info("task.start")
        await mark_task_running(db, task_id)

        state: ResearchState = {
            "task_id": task.id,
            "query": task.query,
            "requested_sources": task.selected_sources,
            "max_papers": task.max_papers,
            "max_search_iterations": task.max_iterations,
            "subtasks": [],
            "papers": [],
            "findings": [],
            "report": None,
            "search_iteration": 0,
            "status": "running",
            "stage": "planning",
            "error": None,
        }

        graph = build_graph()

        try:
            async for event in graph.astream(state):
                for node_name, node_state in event.items():
                    stage_map = {
                        "planner": "planning",
                        "search": "search",
                        "analysis": "analysis",
                        "report": "report",
                    }
                    state.update(node_state)
                    state["stage"] = cast(Any, stage_map.get(node_name, state["stage"]))
                    await persist_progress(db, state)
                    logger.info("task.progress", stage=state["stage"])
                    task_handle.update_state(
                        state="PROGRESS",
                        meta=_task_meta_payload(stage=state["stage"], state=state),
                    )

            state["status"] = "completed"
            state["stage"] = "done"
            await persist_final_state(db, state)
            logger.info("task.completed")
            return {"task_id": task_id, "status": "completed"}
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            await mark_task_failed(db, task_id, error)
            logger.exception("task.failed", error=error)
            task_handle.update_state(
                state="FAILURE",
                meta=_task_meta_payload(stage="error", error=error),
            )
            raise
        finally:
            clear_task_context()


@celery_app.task(name="research.execute", bind=True)
def execute_research_task(self: Any, task_id: str) -> dict[str, Any]:
    return asyncio.run(_execute_research_task(task_id, self))