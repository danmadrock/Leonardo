from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReportRecordCreate(BaseModel):
    task_id: str
    markdown: str = Field(min_length=1)
    structured_report_json: dict[str, Any] = Field(default_factory=dict)


class ReportRecordUpdate(BaseModel):
    markdown: str | None = None
    structured_report_json: dict[str, Any] | None = None


class ReportRecordRead(BaseModel):
    task_id: str
    markdown: str
    structured_report_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
