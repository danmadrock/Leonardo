from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class TaskStage(str, Enum):
    planning = "planning"
    search = "search"
    analysis = "analysis"
    report = "report"
    done = "done"
    error = "error"


class ResearchTask(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), default=TaskStatus.pending)
    stage: Mapped[TaskStage] = mapped_column(SQLEnum(TaskStage), default=TaskStage.planning)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    selected_sources: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    max_papers: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    max_iterations: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    iterations_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    progress_subtasks_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_subtasks_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_papers_collected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_findings_generated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    graph_state_snapshot_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )