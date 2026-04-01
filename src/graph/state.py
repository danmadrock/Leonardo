from __future__ import annotations
from typing import Literal, TypedDict
from src.agents.models import Finding, Report
from src.sources.models import Paper

ResearchStatus = Literal["pending", "running", "completed", "failed"]
TaskStage = Literal["planning", "search", "analysis", "report", "done", "error"]


class ResearchState(TypedDict):
    """Canonical state carried through the LangGraph pipeline."""
    task_id: str
    query: str
    subtasks: list[str]
    papers: list[Paper]
    findings: list[Finding]
    report: Report | None
    search_iteration: int
    status: ResearchStatus
    error: str | None