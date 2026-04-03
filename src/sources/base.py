from abc import ABC, abstractmethod
from typing import ClassVar
from src.sources.models import Paper


class DataSource(ABC):
    name: ClassVar[str]

    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> list[Paper]: ...

    async def enrich(self, paper: Paper) -> Paper:
        """Optional: fetch additional metadata. Override to implement."""
        return paper
