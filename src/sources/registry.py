from src.sources.arxiv import ArXivSource
from src.sources.base import DataSource
from src.sources.semantic_scholar import SemanticScholarSource

REGISTRY: dict[str, DataSource] = {
    "arxiv": ArXivSource(),
    "semantic_scholar": SemanticScholarSource(),
}


def get_source(name: str) -> DataSource:
    if name not in REGISTRY:
        raise ValueError(f"Unknown source: {name!r}. Available: {list(REGISTRY)}")
    return REGISTRY[name]
