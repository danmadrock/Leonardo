from __future__ import annotations

from pydantic import BaseModel

from src.agents.search import SearchAgent
from src.graph.state import ResearchState
from src.llm.base import BaseLLM, Message
from src.sources.models import Paper


class FakeLLM(BaseLLM):
    async def complete(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
    ) -> str | BaseModel:
        raise AssertionError("not used")


class FakeSource:
    async def search(self, query: str, max_results: int = 10) -> list[Paper]:
        return [Paper(title="T", url="https://a", source="arxiv", doi="1")]


async def test_search_agent_dedupes(monkeypatch) -> None:
    agent = SearchAgent(FakeLLM())

    def fake_get_source(name: str) -> FakeSource:
        return FakeSource()

    monkeypatch.setattr("src.agents.search.get_source", fake_get_source)
    state: ResearchState = {
        "task_id": "t1",
        "query": "q",
        "requested_sources": ["arxiv", "semantic_scholar"],
        "max_papers": 5,
        "max_search_iterations": 2,
        "subtasks": ["one"],
        "papers": [],
        "findings": [],
        "report": None,
        "search_iteration": 0,
        "status": "running",
        "stage": "search",
        "error": None,
    }
    result = await agent.run(state)
    assert len(result["papers"]) == 1
    assert result["search_iteration"] == 1
