import asyncio
import logging
from typing import ClassVar
import arxiv
from src.sources.base import DataSource
from src.sources.models import Paper

logger = logging.getLogger(__name__)


class ArXivSource(DataSource):
    name: ClassVar[str] = "arxiv"

    def __init__(self) -> None:
        self._client = arxiv.Client(num_retries=3, delay_seconds=2.0)

    async def search(self, query: str, max_results: int = 10) -> list[Paper]:
        try:
            return await asyncio.to_thread(self._sync_search, query, max_results)
        except Exception:
            logger.exception("arXiv search failed", extra={"query": query})
            return []

    def _sync_search(self, query: str, max_results: int) -> list[Paper]:
        search = arxiv.Search(
            query=query, max_results=max_results, sort_by=arxiv.SortCriterion.Relevance
        )
        results = list(self._client.results(search))
        return [self._map(result) for result in results]

    def _map(self, result: arxiv.Result) -> Paper:
        arxiv_id = result.entry_id.split("/abs/")[-1]
        return Paper(
            title=result.title,
            abstract=result.summary,
            authors=[str(author) for author in result.authors],
            year=result.published.year if result.published else None,
            arxiv_id=arxiv_id,
            doi=result.doi,
            url=result.entry_id,
            pdf_url=str(result.pdf_url) if result.pdf_url else None,
            venue=str(result.journal_ref) if result.journal_ref else None,
            keywords=[str(category) for category in result.categories],
            source=self.name,
        )
