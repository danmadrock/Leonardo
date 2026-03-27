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
        search  = arxiv.Search(query=query, max_results=max_results, sort_by=arxiv.SortCriterion.Relevance)
        results = list(self._client.results(search))
        return [self._map(r) for r in results]

    def _map(self, r: arxiv.Result) -> Paper:
        arxiv_id = r.entry_id.split("/abs/")[-1]
        return Paper(
            title = r.title,
            abstract = r.summary,
            authors = [str(a) for a in r.authors],
            year = r.published.year if r.published else None,
            arxiv_id = arxiv_id,
            doi = r.doi,
            url = r.entry_id,
            pdf_url = str(r.pdf_url) if r.pdf_url else None,
            venue = str(r.journal_ref) if r.journal_ref else None,
            keywords = [str(c) for c in r.categories],
            source = self.name,
        )