from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.models.task import TaskStage, TaskStatus

if TYPE_CHECKING:
    from datetime import datetime


class ResearchTaskCreate(BaseModel):
    query: str = Field(min_length=1)
    status: TaskStatus = TaskStatus.pending
    stage: TaskStage = TaskStage.planning
    selected_sources: list[str] = Field(default_factory=list)
    idempotency_key: str | None = None
    request_fingerprint: str | None = None
    max_papers: int = Field(default=50, ge=1)
    max_iterations: int = Field(default=3, ge=1)


class ResearchTaskUpdate(BaseModel):
    status: TaskStatus | None = None
    stage: TaskStage | None = None
    error: str | None = None
    selected_sources: list[str] | None = None
    idempotency_key: str | None = None
    request_fingerprint: str | None = None
    max_papers: int | None = Field(default=None, ge=1)
    max_iterations: int | None = Field(default=None, ge=1)
    iterations_used: int | None = Field(default=None, ge=0)
    progress_subtasks_total: int | None = Field(default=None, ge=0)
    progress_subtasks_completed: int | None = Field(default=None, ge=0)
    progress_papers_collected: int | None = Field(default=None, ge=0)
    progress_findings_generated: int | None = Field(default=None, ge=0)
    graph_state_snapshot_ref: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ResearchTaskRead(BaseModel):
    id: str
    query: str
    status: TaskStatus
    stage: TaskStage
    error: str | None
    selected_sources: list[str]
    idempotency_key: str | None
    request_fingerprint: str | None
    max_papers: int
    max_iterations: int
    iterations_used: int
    progress_subtasks_total: int
    progress_subtasks_completed: int
    progress_papers_collected: int
    progress_findings_generated: int
    graph_state_snapshot_ref: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime

    model_config = {"from_attributes": True}
