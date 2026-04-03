from __future__ import annotations

import asyncio
import logging
from typing import Any, ClassVar
import time

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.config import settings
from src.sources.base import DataSource
from src.sources.models import Paper

logger = logging.getLogger(__name__)


class SemanticScholarSource(DataSource):
    name: ClassVar[str] = "semantic_scholar"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.semanticscholar.org/graph/v1/",
            timeout=15.0,
        )
        self._semaphore = asyncio.Semaphore(5)
        self._last_request = 0.0
        self._min_interval = 1.0
        self._rate_lock = asyncio.Lock()

    async def _rate_limit(self):
        async with self._rate_lock:
            now = time.time()
            delta = now - self._last_request
            if delta < self._min_interval:
                await asyncio.sleep(self._min_interval - delta)
            self._last_request = time.time()

    async def search(self, query: str, max_results: int = 10) -> list[Paper]:
        try:
            payload = await self._search_with_retry(
                query=query, max_results=max_results
            )
        except Exception:
            logger.exception("Semantic Scholar search failed", extra={"query": query})
            return []

        papers: list[Paper] = []
        for raw in payload.get("data", []):
            paper = self._to_paper(raw)
            if paper.abstract:
                papers.append(paper)
        return papers

    async def _search_with_retry(self, query: str, max_results: int) -> dict[str, Any]:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
            reraise=True,
        ):
            with attempt:
                return await self._fetch_search(query=query, max_results=max_results)

        return {"data": []}

    async def _fetch_search(self, query: str, max_results: int) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if settings.SEMANTIC_SCHOLAR_API_KEY:
            headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY

        async with self._semaphore:
            await self._rate_limit()
            response = await self._client.get(
                "paper/search",
                params={
                    "query": query,
                    "limit": max_results,
                    "fields": (
                        "paperId,title,abstract,authors,year,externalIds,url,citationCount,venue"
                    ),
                },
                headers=headers,
            )
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "5"))
                logger.warning(f"Rate limited. Sleeping {retry_after}s")
                await asyncio.sleep(retry_after)
                raise httpx.HTTPStatusError(
                    "429 retry", request=response.request, response=response
                )

        response.raise_for_status()
        return response.json()

    def _to_paper(self, record: dict[str, Any]) -> Paper:
        external_ids = record.get("externalIds") or {}

        return Paper(
            title=record.get("title") or "",
            abstract=record.get("abstract") or "",
            authors=[
                author.get("name", "")
                for author in record.get("authors", [])
                if author.get("name")
            ],
            year=record.get("year"),
            doi=external_ids.get("DOI"),
            arxiv_id=external_ids.get("ArXiv"),
            url=record.get("url")
            or f"https://www.semanticscholar.org/paper/{record.get('paperId', '')}",
            citation_count=record.get("citationCount"),
            venue=record.get("venue"),
            source=self.name,
            metadata={"paper_id": record.get("paperId")},
        )

    async def close(self):
        await self._client.aclose()
