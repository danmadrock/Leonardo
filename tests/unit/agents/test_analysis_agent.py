from __future__ import annotations

from typing import TYPE_CHECKING

from src.agents.analysis import AnalysisAgent
from src.agents.models import Finding
from src.llm.base import BaseLLM, Message
from src.sources.models import Paper, PaperRef

if TYPE_CHECKING:
    from pydantic import BaseModel

    from src.graph.state import ResearchState


class FakeLLM(BaseLLM):
    async def complete(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
    ) -> str | BaseModel:
        return Finding(
            claim="c",
            methodology="m",
            limitations="l",
            relevance=0.9,
            source_paper=PaperRef(title="t", url="https://x"),
        )


async def test_analysis_agent_filters_and_returns_findings() -> None:
    agent = AnalysisAgent(FakeLLM())
    state: ResearchState = {
        "task_id": "t1",
        "query": "q",
        "requested_sources": [],
        "max_papers": 5,
        "max_search_iterations": 2,
        "subtasks": [],
        "papers": [Paper(title="t", url="https://x", source="s")],
        "findings": [],
        "report": None,
        "search_iteration": 0,
        "status": "running",
        "stage": "analysis",
        "error": None,
    }
    result = await agent.run(state)
    assert len(result["findings"]) == 1
