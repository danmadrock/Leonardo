from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class ReportRecord(Base):
    __tablename__ = "reports"
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), primary_key=True)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    structured_report_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )