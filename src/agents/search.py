from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from pydantic import HttpUrl, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import BaseAgent
from src.api.schemas import PaperCreate
from src.core.config import settings
from src.crud.papers import create_paper_if_missing
from src.graph.state import ResearchState
from src.sources.models import Paper
from src.sources.registry import get_source

_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


def _paper_key(paper: Paper) -> tuple[str, str, str]:
    doi = (paper.doi or "").strip().lower()
    arxiv_id = (paper.arxiv_id or "").strip().lower()
    title = paper.title.strip().lower()
    return doi, arxiv_id, title


def _coerce_url(raw_url: str) -> HttpUrl | None:
    try:
        return _HTTP_URL_ADAPTER.validate_python(raw_url)
    except ValidationError:
        return None


class SearchAgent(BaseAgent):
    def __init__(self, llm, db_session_factory: Callable[[], AsyncSession] | None = None) -> None:
        super().__init__(llm)
        self.db_session_factory = db_session_factory

    async def run(self, state: ResearchState) -> dict:
        enabled_sources = state.get("requested_sources") or settings.ENABLED_SOURCES
        per_subtask_limit = min(
            state.get("max_papers", settings.MAX_PAPERS_PER_SUBTASK),
            settings.MAX_PAPERS_PER_SUBTASK,
        )
        jobs: list[Awaitable[list[Paper]]] = []
        for subtask in state["subtasks"]:
            for source_name in enabled_sources:
                source = get_source(source_name)
                jobs.append(source.search(subtask, max_results=per_subtask_limit))
        batches = await asyncio.gather(*jobs, return_exceptions=True)
        seen: set[tuple[str, str, str]] = set()
        deduped: list[Paper] = []
        for batch in batches:
            if isinstance(batch, BaseException):
                continue
            for paper in batch:
                key = _paper_key(paper)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(paper)
        if self.db_session_factory is not None:
            await self._persist_papers(deduped)
        return {
            "papers": deduped,
            "search_iteration": state["search_iteration"] + 1,
        }

    async def _persist_papers(self, papers: list[Paper]) -> None:
        assert self.db_session_factory is not None
        async with self.db_session_factory() as db:
            for paper in papers:
                parsed_url = _coerce_url(paper.url)
                if parsed_url is None:
                    continue
                payload = PaperCreate(
                    title=paper.title,
                    abstract=paper.abstract,
                    url=parsed_url,
                    source=paper.source,
                    authors=paper.authors,
                    year=paper.year,
                    doi=paper.doi,
                    arxiv_id=paper.arxiv_id,
                    citation_count=paper.citation_count,
                    venue=paper.venue,
                    metadata=paper.metadata,
                )
                await create_paper_if_missing(db, payload)