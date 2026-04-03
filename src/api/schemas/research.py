from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from datetime import datetime


class PipelineStage(StrEnum):
    queued = "queued"
    planner = "planner"
    search = "search"
    analysis = "analysis"
    report = "report"
    completed = "completed"
    failed = "failed"


class TaskStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ResearchCreateRequest(BaseModel):
    query: str = Field(min_length=10, max_length=2000)
    max_papers: int = Field(default=20, ge=1, le=100)
    sources: list[str] | None = None


class ResearchCreateResponse(BaseModel):
    task_id: str
    status: TaskStatus
    stage: PipelineStage
    status_url: str
    report_url: str
    created_at: datetime


class ResearchTaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    stage: PipelineStage
    created_at: datetime
    updated_at: datetime


class ProgressSnapshot(BaseModel):
    search_iteration: int
    max_search_iterations: int
    subtasks_total: int
    subtasks_completed: int
    papers_found: int
    findings_extracted: int


class ResearchStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    stage: PipelineStage
    progress: ProgressSnapshot
    error: str | None
    created_at: datetime
    updated_at: datetime


class ResearchReportResponse(BaseModel):
    task_id: str
    query: str
    report: dict
    generated_at: datetime
