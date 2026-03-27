# Adding a New Data Source

> This guide walks you through implementing a new scientific data source plugin for Leonardo Research.  
> By the end you will have a fully integrated source that the search agent can query alongside arXiv and Semantic Scholar.

---

## Table of Contents

1. [How Sources Work](#1-how-sources-work)
2. [The DataSource Interface](#2-the-datasource-interface)
3. [The Paper Model](#3-the-paper-model)
4. [Step-by-Step Implementation](#4-step-by-step-implementation)
5. [Registering Your Source](#5-registering-your-source)
6. [Configuration and Feature Flags](#6-configuration-and-feature-flags)
7. [Testing Your Source](#7-testing-your-source)
8. [Error Handling Patterns](#8-error-handling-patterns)
9. [Rate Limiting and Pagination](#9-rate-limiting-and-pagination)
10. [Authentication Patterns](#10-authentication-patterns)
11. [Real-World Example: PubMed](#11-real-world-example-pubmed)
12. [Real-World Example: Crossref](#12-real-world-example-crossref)
13. [Advanced: Metadata Enrichment](#13-advanced-metadata-enrichment)
14. [Source Quality Checklist](#14-source-quality-checklist)

---

## 1. How Sources Work

The search agent does not know about individual sources. It queries the **source registry** — a dict of `{name: DataSource}` instances — and calls `.search()` on each source listed in `settings.ENABLED_SOURCES`.

```
Search agent
  │
  ├── for source_name in settings.ENABLED_SOURCES:
  │       source = registry[source_name]
  │       papers = await source.search(query, max_results)
  │
  ├── deduplicate by (doi, arxiv_id, title_hash)
  ├── filter near-duplicates via ChromaDB
  └── → state.papers
```

Your source only needs to implement one method: `async def search(query, max_results) -> list[Paper]`.  
Everything else — deduplication, caching, embedding, relevance scoring — is handled by the search agent.

---

## 2. The DataSource Interface

**File:** `src/sources/base.py`

```python
from abc import ABC, abstractmethod
from typing import ClassVar
from src.sources.models import Paper


class DataSource(ABC):
    """
    Abstract base class for all scientific data sources.

    Implementations must:
    - Set a unique `name` class variable (used as the registry key)
    - Implement `search()` as an async method
    - Return a list of `Paper` objects (partial fields are allowed)
    - Never raise exceptions to the caller — catch and log internally,
      return an empty list on total failure
    """

    name: ClassVar[str]

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[Paper]:
        """
        Search for papers matching `query`.

        Args:
            query:       Natural language or boolean search string.
            max_results: Maximum number of Paper objects to return.
                         Implementations should respect this limit.

        Returns:
            List of Paper objects. May be empty. Must not be None.
        """
        ...
```

That is the entire contract. One class variable, one method.

---

## 3. The Paper Model

**File:** `src/sources/models.py`

Every source returns `Paper` objects. Familiarise yourself with all fields before mapping your API response:

```python
from pydantic import BaseModel, HttpUrl


class PaperRef(BaseModel):
    """Lightweight reference used for citations inside Finding objects."""
    title:    str
    url:      str
    doi:      str | None = None
    arxiv_id: str | None = None


class Paper(BaseModel):
    # ── Required ──────────────────────────────────────────────────────
    title:   str            # Full title of the paper
    url:     str            # Canonical URL to the paper's landing page
    source:  str            # Your source's `name` value

    # ── Strongly recommended ──────────────────────────────────────────
    abstract:  str  = ""    # Full abstract text; used for embedding + analysis
    authors:   list[str] = []
    year:      int  | None = None

    # ── Deduplication keys (provide at least one) ─────────────────────
    doi:       str  | None = None   # e.g. "10.1038/nature12373"
    arxiv_id:  str  | None = None   # e.g. "2305.12345"

    # ── Optional enrichment ───────────────────────────────────────────
    pdf_url:          str  | None = None
    citation_count:   int  | None = None
    venue:            str  | None = None   # journal or conference name
    keywords:         list[str]   = []
    metadata:         dict        = {}     # source-specific extras
```

**Deduplication note:** The search agent deduplicates across sources using DOI and arXiv ID. If your source returns papers that might also appear in arXiv or Semantic Scholar, **always populate `doi` and/or `arxiv_id`** when the information is available. Leaving them `None` means duplicates from other sources will not be detected.

**Abstract is critical.** The analysis agent uses the abstract to generate `Finding` objects. A `Paper` with an empty abstract will produce a low-quality finding. If your API does not return abstracts, fetch them from a secondary endpoint, or skip the paper.

---

## 4. Step-by-Step Implementation

### Step 1 — Create the source file

Create `src/sources/{your_source_name}.py`. Use snake_case for the filename; it becomes the source's identity throughout the system.

```
src/sources/
├── base.py
├── models.py
├── arxiv.py
├── semantic_scholar.py
├── registry.py
└── pubmed.py          ← your new file
```

### Step 2 — Implement the class

Minimal skeleton:

```python
# src/sources/pubmed.py

import logging
from typing import ClassVar

import httpx

from src.sources.base import DataSource
from src.sources.models import Paper
from src.core.config import settings

logger = logging.getLogger(__name__)


class PubMedSource(DataSource):
    name: ClassVar[str] = "pubmed"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
            timeout=15.0,
        )

    async def search(self, query: str, max_results: int = 10) -> list[Paper]:
        try:
            ids    = await self._fetch_ids(query, max_results)
            papers = await self._fetch_details(ids)
            return papers
        except Exception:
            logger.exception("PubMed search failed", extra={"query": query})
            return []

    async def _fetch_ids(self, query: str, max_results: int) -> list[str]:
        response = await self._client.get(
            "esearch.fcgi",
            params={
                "db":      "pubmed",
                "term":    query,
                "retmax":  max_results,
                "retmode": "json",
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["esearchresult"]["idlist"]

    async def _fetch_details(self, ids: list[str]) -> list[Paper]:
        if not ids:
            return []

        response = await self._client.get(
            "esummary.fcgi",
            params={
                "db":      "pubmed",
                "id":      ",".join(ids),
                "retmode": "json",
            },
        )
        response.raise_for_status()
        data    = response.json()
        results = data.get("result", {})

        papers = []
        for uid in results.get("uids", []):
            record = results[uid]
            papers.append(self._to_paper(record))

        return papers

    def _to_paper(self, record: dict) -> Paper:
        doi = next(
            (
                aid["value"]
                for aid in record.get("articleids", [])
                if aid["idtype"] == "doi"
            ),
            None,
        )

        return Paper(
            title          = record.get("title", ""),
            abstract       = "",              # esummary does not include abstracts;
                                              # see Section 13 for enrichment
            authors        = [
                a["name"] for a in record.get("authors", [])
            ],
            year           = int(record["pubdate"][:4])
                             if record.get("pubdate") else None,
            doi            = doi,
            url            = f"https://pubmed.ncbi.nlm.nih.gov/{record['uid']}/",
            pdf_url        = None,
            venue          = record.get("source"),
            source         = self.name,
        )
```

### Step 3 — Register and test

See [Section 5](#5-registering-your-source) and [Section 7](#7-testing-your-source).

---

## 5. Registering Your Source

**File:** `src/sources/registry.py`

```python
from src.sources.arxiv            import ArXivSource
from src.sources.semantic_scholar import SemanticScholarSource
from src.sources.pubmed           import PubMedSource          # ← import

REGISTRY: dict[str, DataSource] = {
    "arxiv":            ArXivSource(),
    "semantic_scholar": SemanticScholarSource(),
    "pubmed":           PubMedSource(),                        # ← register
}


def get_source(name: str) -> DataSource:
    if name not in REGISTRY:
        raise ValueError(f"Unknown source: {name!r}. Available: {list(REGISTRY)}")
    return REGISTRY[name]
```

That is the entire registration step. No other file needs to change.

To enable your source for all requests, add it to `.env`:

```env
ENABLED_SOURCES=arxiv,semantic_scholar,pubmed
```

To enable it only for specific requests, pass it in the API call:

```json
{
  "query": "CRISPR gene editing review",
  "sources": ["pubmed"]
}
```

---

## 6. Configuration and Feature Flags

If your source requires an API key or custom configuration, add typed fields to `src/core/config.py`:

```python
# src/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... existing fields ...

    # PubMed (optional API key for higher rate limits)
    PUBMED_API_KEY:      str | None = None
    PUBMED_MAX_RESULTS:  int        = 20
    PUBMED_TIMEOUT_SECS: float      = 15.0
```

Then read from settings in your source:

```python
class PubMedSource(DataSource):
    def __init__(self) -> None:
        params = {}
        if settings.PUBMED_API_KEY:
            params["api_key"] = settings.PUBMED_API_KEY

        self._default_params = params
        self._client = httpx.AsyncClient(
            base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
            timeout=settings.PUBMED_TIMEOUT_SECS,
        )
```

Add the new env var to `.env.example` with a comment:

```env
# PubMed API key (optional — increases rate limit from 3 to 10 req/s)
# PUBMED_API_KEY=
```

---

## 7. Testing Your Source

Create `tests/unit/sources/test_{your_source}.py`. Every source should have these three test categories:

### 7.1 Happy path

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.sources.pubmed import PubMedSource


@pytest.fixture
def source() -> PubMedSource:
    return PubMedSource()


@pytest.mark.asyncio
async def test_search_returns_papers(source: PubMedSource) -> None:
    mock_ids_response = {
        "esearchresult": {"idlist": ["38000001", "38000002"]}
    }
    mock_details_response = {
        "result": {
            "uids": ["38000001"],
            "38000001": {
                "uid":     "38000001",
                "title":   "CRISPR-Cas9 gene editing advances",
                "authors": [{"name": "Smith J"}, {"name": "Jones A"}],
                "pubdate": "2024",
                "source":  "Nature",
                "articleids": [{"idtype": "doi", "value": "10.1038/s41586-024-00001-1"}],
            },
        }
    }

    with patch.object(source._client, "get", side_effect=[
        AsyncMock(json=lambda: mock_ids_response, raise_for_status=lambda: None),
        AsyncMock(json=lambda: mock_details_response, raise_for_status=lambda: None),
    ]):
        papers = await source.search("CRISPR gene editing", max_results=5)

    assert len(papers) == 1
    assert papers[0].title == "CRISPR-Cas9 gene editing advances"
    assert papers[0].doi   == "10.1038/s41586-024-00001-1"
    assert papers[0].source == "pubmed"
    assert papers[0].year  == 2024
```

### 7.2 Empty results

```python
@pytest.mark.asyncio
async def test_search_returns_empty_on_no_results(source: PubMedSource) -> None:
    mock_response = {"esearchresult": {"idlist": []}}

    with patch.object(source._client, "get", return_value=AsyncMock(
        json=lambda: mock_response, raise_for_status=lambda: None
    )):
        papers = await source.search("xyzzy nonexistent topic 99999")

    assert papers == []
```

### 7.3 Failure resilience

```python
@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(source: PubMedSource) -> None:
    """Source must never propagate exceptions to the search agent."""
    with patch.object(source._client, "get", side_effect=httpx.ConnectError("timeout")):
        papers = await source.search("any query")

    assert papers == []   # swallowed, not raised
```

### 7.4 Integration test (optional, requires network)

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_pubmed_search() -> None:
    source  = PubMedSource()
    papers  = await source.search("transformer attention mechanism", max_results=3)

    assert len(papers) > 0
    assert all(p.title    for p in papers)
    assert all(p.url      for p in papers)
    assert all(p.source == "pubmed" for p in papers)
```

Run integration tests with:

```bash
pytest tests/ -m integration
```

They are excluded from the default `make test` run to avoid CI dependency on external APIs.

---

## 8. Error Handling Patterns

The search agent tolerates source failures gracefully — if one source fails, the pipeline continues with results from the others. This means your source must **never raise an exception to the caller**. Catch everything, log it, return `[]`.

**Pattern A — top-level catch (recommended for simple sources):**

```python
async def search(self, query: str, max_results: int = 10) -> list[Paper]:
    try:
        return await self._do_search(query, max_results)
    except Exception:
        logger.exception(
            "Source search failed",
            extra={"source": self.name, "query": query},
        )
        return []
```

**Pattern B — granular catch (recommended when partial results are useful):**

```python
async def search(self, query: str, max_results: int = 10) -> list[Paper]:
    ids = await self._fetch_ids(query, max_results)   # raises → []
    if not ids:
        return []

    papers = []
    for id_batch in chunks(ids, size=20):
        try:
            papers.extend(await self._fetch_details(id_batch))
        except Exception:
            logger.warning(
                "Batch fetch failed; continuing with partial results",
                extra={"source": self.name, "batch": id_batch},
            )
    return papers
```

Use pattern B when the source has a two-phase search (ID lookup → detail fetch) and partial results are better than no results.

---

## 9. Rate Limiting and Pagination

**Rate limiting:**

Many scientific APIs have strict rate limits. Use `asyncio.Semaphore` to cap concurrent requests:

```python
class PubMedSource(DataSource):
    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(3)   # max 3 concurrent requests
        self._client    = httpx.AsyncClient(...)

    async def _get(self, endpoint: str, params: dict) -> dict:
        async with self._semaphore:
            response = await self._client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
```

For sources with per-second rate limits (e.g., PubMed without API key = 3 req/s), use a token bucket or `asyncio.sleep` between requests.

**Pagination:**

If the source supports pagination and you want more results than a single page allows:

```python
async def _fetch_all_ids(
    self,
    query: str,
    max_results: int,
) -> list[str]:
    all_ids   = []
    page_size = min(max_results, 200)   # API maximum per request
    retstart  = 0

    while len(all_ids) < max_results:
        batch = await self._fetch_id_page(query, page_size, retstart)
        if not batch:
            break
        all_ids.extend(batch)
        retstart += page_size

    return all_ids[:max_results]
```

---

## 10. Authentication Patterns

**API key in query params:**

```python
self._default_params = {"api_key": settings.PUBMED_API_KEY}

async def _get(self, endpoint: str, params: dict) -> dict:
    response = await self._client.get(
        endpoint,
        params={**self._default_params, **params},
    )
    ...
```

**API key in headers:**

```python
self._client = httpx.AsyncClient(
    base_url="...",
    headers={"x-api-key": settings.MY_SOURCE_API_KEY},
)
```

**OAuth2 / token refresh:**

Sources requiring OAuth2 are significantly more complex. The pattern is:

```python
class OAuth2Source(DataSource):
    def __init__(self) -> None:
        self._token:    str | None = None
        self._token_expires_at: float = 0.0

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        # fetch a new token, store it, update expiry
        ...
        return self._token

    async def search(self, query: str, max_results: int = 10) -> list[Paper]:
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        ...
```

---

## 11. Real-World Example: PubMed

The complete, production-ready PubMed source with abstract fetching, retry logic, and rate limiting:

```python
# src/sources/pubmed.py

import asyncio
import logging
import time
from typing import ClassVar

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config   import settings
from src.sources.base  import DataSource
from src.sources.models import Paper

logger = logging.getLogger(__name__)

_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


class PubMedSource(DataSource):
    name: ClassVar[str] = "pubmed"

    def __init__(self) -> None:
        self._sem    = asyncio.Semaphore(3)
        self._client = httpx.AsyncClient(base_url=_BASE, timeout=15.0)
        self._params = (
            {"api_key": settings.PUBMED_API_KEY}
            if settings.PUBMED_API_KEY
            else {}
        )

    # ── Public interface ───────────────────────────────────────────────

    async def search(self, query: str, max_results: int = 10) -> list[Paper]:
        try:
            ids     = await self._search_ids(query, max_results)
            papers  = await self._fetch_summaries(ids)
            papers  = await self._enrich_abstracts(papers, ids)
            return papers
        except Exception:
            logger.exception("PubMed search error", extra={"query": query})
            return []

    # ── Private helpers ────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def _search_ids(self, query: str, max_results: int) -> list[str]:
        async with self._sem:
            r = await self._client.get(
                "esearch.fcgi",
                params={**self._params, "db": "pubmed", "term": query,
                        "retmax": max_results, "retmode": "json"},
            )
            r.raise_for_status()
            return r.json()["esearchresult"]["idlist"]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def _fetch_summaries(self, ids: list[str]) -> list[Paper]:
        if not ids:
            return []
        async with self._sem:
            r = await self._client.get(
                "esummary.fcgi",
                params={**self._params, "db": "pubmed",
                        "id": ",".join(ids), "retmode": "json"},
            )
            r.raise_for_status()
            result = r.json().get("result", {})
            return [
                self._map_summary(result[uid])
                for uid in result.get("uids", [])
                if uid in result
            ]

    async def _enrich_abstracts(
        self, papers: list[Paper], ids: list[str]
    ) -> list[Paper]:
        """Fetch full abstracts via efetch — esummary does not include them."""
        if not ids:
            return papers

        async with self._sem:
            r = await self._client.get(
                "efetch.fcgi",
                params={**self._params, "db": "pubmed",
                        "id": ",".join(ids), "rettype": "abstract",
                        "retmode": "text"},
            )
            # efetch returns plain text blocks separated by blank lines.
            # Simple heuristic: assign the n-th block to the n-th paper.
            blocks = [b.strip() for b in r.text.split("\n\n") if b.strip()]
            for paper, block in zip(papers, blocks):
                paper.abstract = block
        return papers

    def _map_summary(self, record: dict) -> Paper:
        doi = next(
            (a["value"] for a in record.get("articleids", [])
             if a["idtype"] == "doi"),
            None,
        )
        return Paper(
            title          = record.get("title", ""),
            abstract       = "",
            authors        = [a["name"] for a in record.get("authors", [])],
            year           = int(record["pubdate"][:4]) if record.get("pubdate") else None,
            doi            = doi,
            url            = f"https://pubmed.ncbi.nlm.nih.gov/{record['uid']}/",
            venue          = record.get("source"),
            citation_count = record.get("pmcrefcount"),
            source         = self.name,
            metadata       = {"pmid": record["uid"]},
        )
```

---

## 12. Real-World Example: Crossref

Crossref is a DOI registration agency that provides metadata for millions of published papers. This example shows a source that does not require authentication and maps a deeply nested API response:

```python
# src/sources/crossref.py

import logging
from typing import ClassVar

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.sources.base   import DataSource
from src.sources.models import Paper

logger = logging.getLogger(__name__)


class CrossrefSource(DataSource):
    name: ClassVar[str] = "crossref"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.crossref.org/",
            headers={"User-Agent": "LeonardoResearch/1.0 (mailto:your@email.com)"},
            timeout=15.0,
        )

    async def search(self, query: str, max_results: int = 10) -> list[Paper]:
        try:
            return await self._search(query, max_results)
        except Exception:
            logger.exception("Crossref search error", extra={"query": query})
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def _search(self, query: str, max_results: int) -> list[Paper]:
        r = await self._client.get(
            "works",
            params={"query": query, "rows": max_results,
                    "select": "DOI,title,author,published,abstract,container-title,is-referenced-by-count"},
        )
        r.raise_for_status()
        items = r.json().get("message", {}).get("items", [])
        return [self._map(item) for item in items if item.get("title")]

    def _map(self, item: dict) -> Paper:
        authors = [
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in item.get("author", [])
        ]
        date_parts = item.get("published", {}).get("date-parts", [[]])
        year = date_parts[0][0] if date_parts and date_parts[0] else None
        doi  = item.get("DOI")

        return Paper(
            title          = item["title"][0] if item.get("title") else "",
            abstract       = item.get("abstract", ""),
            authors        = authors,
            year           = year,
            doi            = doi,
            url            = f"https://doi.org/{doi}" if doi else "",
            venue          = (item.get("container-title") or [""])[0],
            citation_count = item.get("is-referenced-by-count"),
            source         = self.name,
        )
```

---

## 13. Advanced: Metadata Enrichment

Some sources (like PubMed via `esummary`) do not return abstracts in the search response. You have two options:

**Option A — second fetch in `search()`**  
Fetch abstracts for all results before returning. Adds latency but keeps the `Paper` objects complete. Recommended for sources where abstracts are critical.

**Option B — lazy enrichment hook**  
Implement an optional `enrich(paper: Paper) -> Paper` method on your source. The search agent can call this lazily for papers that the analysis agent actually selects. This avoids fetching abstracts for papers that are deduplicated away.

```python
class DataSource(ABC):
    ...

    async def enrich(self, paper: Paper) -> Paper:
        """
        Optional. Fetch additional metadata for a single paper.
        Default implementation returns the paper unchanged.
        Override to add abstracts, full text, citation graphs, etc.
        """
        return paper
```

The search agent checks `hasattr(source, 'enrich')` and calls it on the top-N papers by relevance score after the initial search phase.

---

## 14. Source Quality Checklist

Before opening a pull request for a new source, verify every item:

**Implementation**

- [ ] Class is in `src/sources/{name}.py`; filename matches `name` class variable
- [ ] `name` is a unique, lowercase, snake_case string
- [ ] `search()` is `async` and returns `list[Paper]`
- [ ] `search()` never raises an exception (top-level try/except returns `[]`)
- [ ] `Paper.source` is set to `self.name` on every object
- [ ] `Paper.doi` is populated when the API provides it
- [ ] `Paper.abstract` is populated (not empty string) for at least 80% of results
- [ ] HTTP client has an explicit timeout
- [ ] Concurrent requests are bounded by a `Semaphore`
- [ ] Retry logic is implemented (at least 3 attempts with backoff)

**Configuration**

- [ ] Any required API keys are read from `settings`, not hardcoded
- [ ] New settings fields have sensible defaults
- [ ] `.env.example` is updated with the new env var(s) and a comment
- [ ] Source is added to `REGISTRY` in `src/sources/registry.py`

**Tests**

- [ ] Happy path test (mocked HTTP, verifies `Paper` field mapping)
- [ ] Empty result test (API returns 0 results → `[]`)
- [ ] Failure resilience test (HTTP error → `[]`, not exception)
- [ ] Optional: integration test marked `@pytest.mark.integration`
- [ ] All tests pass: `make test`

**Documentation**

- [ ] Docstring on the class explains: what the source indexes, rate limits, and any API key requirements
- [ ] Any non-obvious field mapping is commented inline
- [ ] PR description links to the API documentation

---

## Getting Help

If you are unsure about any part of this process, look at the existing source implementations as reference:

- `src/sources/arxiv.py` — simple two-step source (search then fetch), no auth
- `src/sources/semantic_scholar.py` — enriched metadata, optional API key, citation weighting

Both are well-commented and cover the most common patterns you will encounter.
