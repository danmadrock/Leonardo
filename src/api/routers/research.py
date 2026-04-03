from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from src.api.dependencies import get_db
from src.api.schemas.research import (
    PipelineStage,
    ProgressSnapshot,
    ResearchCreateRequest,
    ResearchCreateResponse,
    ResearchReportResponse,
    ResearchStatusResponse,
    ResearchTaskResponse,
    TaskStatus,
)
from src.api.schemas.tasks import ResearchTaskCreate
from src.core.config import settings
from src.crud.reports import get_report
from src.crud.tasks import create_task, get_task, get_task_by_idempotency_key
from src.tasks.celery_app import celery_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/research", tags=["research"])


def _stage_for_api(status_value: str, stage_value: str) -> PipelineStage:
    if status_value == "pending":
        return PipelineStage.queued
    if status_value == "failed":
        return PipelineStage.failed
    if status_value == "completed":
        return PipelineStage.completed

    mapping = {
        "planning": PipelineStage.planner,
        "search": PipelineStage.search,
        "analysis": PipelineStage.analysis,
        "report": PipelineStage.report,
    }
    return mapping.get(stage_value, PipelineStage.queued)


def _request_fingerprint(payload: ResearchCreateRequest) -> str:
    canonical = f"{
        payload.query.strip()}|{
            payload.max_papers
            }|{
                ','.join(sorted(payload.sources or []))
                }"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@router.post(
    "", response_model=ResearchCreateResponse, status_code=status.HTTP_202_ACCEPTED
)
async def create_research_task(
    payload: ResearchCreateRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ResearchCreateResponse:
    if payload.sources is not None:
        if len(payload.sources) != len(set(payload.sources)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Duplicate sources are not allowed",
            )
        unknown = sorted(set(payload.sources) - set(settings.ENABLED_SOURCES))
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown sources: {unknown}",
            )

    fingerprint = _request_fingerprint(payload)
    if idempotency_key:
        existing = await get_task_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key reuse with different request payload",
                )
            task = existing
        else:
            task = await create_task(
                db,
                ResearchTaskCreate(
                    query=payload.query,
                    selected_sources=payload.sources or [],
                    max_papers=payload.max_papers,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                ),
            )
            celery_app.send_task("research.execute", args=[task.id])
    else:
        task = await create_task(
            db,
            ResearchTaskCreate(
                query=payload.query,
                selected_sources=payload.sources or [],
                max_papers=payload.max_papers,
                request_fingerprint=fingerprint,
            ),
        )
        celery_app.send_task("research.execute", args=[task.id])

    base = str(request.base_url).rstrip("/")
    return ResearchCreateResponse(
        task_id=task.id,
        status=TaskStatus(task.status.value),
        stage=_stage_for_api(task.status.value, task.stage.value),
        status_url=f"{base}/api/v1/research/{task.id}/status",
        report_url=f"{base}/api/v1/research/{task.id}/report",
        created_at=task.created_at,
    )


@router.get("/{task_id}", response_model=ResearchTaskResponse)
async def get_research_task(
    task_id: str, db: AsyncSession = Depends(get_db)
) -> ResearchTaskResponse:  # noqa: B008
    task = await get_task(db, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    return ResearchTaskResponse(
        task_id=task.id,
        status=TaskStatus(task.status.value),
        stage=_stage_for_api(task.status.value, task.stage.value),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("/{task_id}/status", response_model=ResearchStatusResponse)
async def get_research_status(
    task_id: str, db: AsyncSession = Depends(get_db)
) -> ResearchStatusResponse:  # noqa: B008
    task = await get_task(db, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    return ResearchStatusResponse(
        task_id=task.id,
        status=TaskStatus(task.status.value),
        stage=_stage_for_api(task.status.value, task.stage.value),
        progress=ProgressSnapshot(
            search_iteration=task.iterations_used,
            max_search_iterations=task.max_iterations,
            subtasks_total=task.progress_subtasks_total,
            subtasks_completed=task.progress_subtasks_completed,
            papers_found=task.progress_papers_collected,
            findings_extracted=task.progress_findings_generated,
        ),
        error=task.error,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("/{task_id}/report", response_model=None)
async def get_research_report(
    task_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ResearchReportResponse | Response:  # noqa: B008
    task = await get_task(db, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    if task.status.value == "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=task.error or "Task failed"
        )
    if task.status.value != "completed":
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY, detail="Report is not ready"
        )

    report = await get_report(db, task_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    accepts_markdown = "text/markdown" in request.headers.get("accept", "")
    if accepts_markdown:
        return Response(
            content=report.markdown, media_type="text/markdown; charset=utf-8"
        )

    return ResearchReportResponse(
        task_id=task.id,
        query=task.query,
        report=report.structured_report_json,
        generated_at=report.updated_at,
    )
