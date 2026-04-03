import pytest

from src.sources.arxiv import ArXivSource
from src.sources.semantic_scholar import SemanticScholarSource


@pytest.mark.integration
@pytest.mark.asyncio
async def test_arxiv_source_live() -> None:
    source = ArXivSource()
    papers = await source.search("graph neural networks", max_results=2)

    assert papers
    for paper in papers:
        assert paper.title
        assert paper.url
        assert paper.source == "arxiv"
        assert paper.abstract


@pytest.mark.integration
@pytest.mark.asyncio
async def test_semantic_scholar_source_live() -> None:
    source = SemanticScholarSource()
    papers = await source.search("graph neural networks", max_results=2)

    assert papers
    for paper in papers:
        assert paper.title
        assert paper.url
        assert paper.source == "semantic_scholar"
        assert paper.abstract
