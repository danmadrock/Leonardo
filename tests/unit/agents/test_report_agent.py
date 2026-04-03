from __future__ import annotations

from typing import TYPE_CHECKING

from src.agents.models import Finding, ReportBody
from src.agents.report import ReportAgent
from src.llm.base import BaseLLM, Message
from src.sources.models import PaperRef

if TYPE_CHECKING:
    from pydantic import BaseModel

    from src.graph.state import ResearchState


class FakeLLM(BaseLLM):
    async def complete(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
    ) -> str | BaseModel:
        return ReportBody(
            executive_summary="sum",
            methodology_overview="meth",
            identified_gaps=["gap"],
        )


async def test_report_agent_generates_markdown() -> None:
    agent = ReportAgent(FakeLLM())
    finding = Finding(
        claim="c",
        methodology="m",
        limitations="l",
        relevance=0.8,
        source_paper=PaperRef(title="p", url="https://x", arxiv_id="1234"),
    )
    state: ResearchState = {
        "task_id": "t1",
        "query": "q",
        "requested_sources": [],
        "max_papers": 5,
        "max_search_iterations": 2,
        "subtasks": [],
        "papers": [],
        "findings": [finding],
        "report": None,
        "search_iteration": 0,
        "status": "running",
        "stage": "report",
        "error": None,
    }
    result = await agent.run(state)
    assert "# Research Report: q" in result["report"].raw_markdown
