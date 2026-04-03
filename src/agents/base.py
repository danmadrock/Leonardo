from __future__ import annotations

from abc import ABC, abstractmethod

from src.graph.state import ResearchState
from src.llm.base import BaseLLM


class BaseAgent(ABC):
    """Base interface for all research pipeline agents."""
    def __init__(self, llm: BaseLLM) -> None:
        self.llm = llm

    @abstractmethod
    async def run(self, state: ResearchState) -> dict:
        """Return a partial state update for the orchestrator merge step."""
        ...