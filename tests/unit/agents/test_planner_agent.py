from __future__ import annotations

from typing import TYPE_CHECKING

from src.agents.models import PlannerOutput
from src.agents.planner import PlannerAgent
from src.llm.base import BaseLLM, Message

if TYPE_CHECKING:
    from pydantic import BaseModel

    from src.graph.state import ResearchState


class FakeLLM(BaseLLM):
    async def complete(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
    ) -> str | BaseModel:
        return PlannerOutput(subtasks=["a", "b", "c"], reasoning="ok")


async def test_planner_agent_returns_subtasks() -> None:
    agent = PlannerAgent(FakeLLM())
    state: ResearchState = {
        "task_id": "t1",
        "query": "query",
        "requested_sources": [],
        "max_papers": 5,
        "max_search_iterations": 2,
        "subtasks": [],
        "papers": [],
        "findings": [],
        "report": None,
        "search_iteration": 0,
        "status": "running",
        "stage": "planning",
        "error": None,
    }
    result = await agent.run(state)
    assert result["subtasks"] == ["a", "b", "c"]
