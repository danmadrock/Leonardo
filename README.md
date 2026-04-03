<div align="center">

<br/>

```
██╗     ███████╗ ██████╗ ███╗   ██╗ █████╗ ██████╗ ██████╗  ██████╗
██║     ██╔════╝██╔═══██╗████╗  ██║██╔══██╗██╔══██╗██╔══██╗██╔═══██╗
██║     █████╗  ██║   ██║██╔██╗ ██║███████║██████╔╝██║  ██║██║   ██║
██║     ██╔══╝  ██║   ██║██║╚██╗██║██╔══██║██╔══██╗██║  ██║██║   ██║
███████╗███████╗╚██████╔╝██║ ╚████║██║  ██║██║  ██║██████╔╝╚██████╔╝
╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝
                    R E S E A R C H
```

**Autonomous multi-agent system for scientific literature research**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.1+-1C3A5F?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-orange?style=flat-square)](https://docs.astral.sh/ruff/)

</div>

---

## Overview

**Leonardo Research** is a production-grade autonomous AI research agent that accepts a scientific question and returns a fully structured, source-attributed research report — without human intervention at any stage of the pipeline.

The system decomposes complex research queries into subtasks, searches multiple scientific databases in parallel, extracts and synthesises key findings via LLM, and assembles a final Markdown report with inline citations. The entire pipeline is orchestrated as a **stateful LangGraph graph**, exposed through a **FastAPI REST API**, and deployed as a multi-container **Docker** application with asynchronous Celery workers.

```
User query  ──▶  Planner  ──▶  Search  ──▶  Analysis  ──▶  Report
                   │              │             │            │
              subtask list    raw papers    findings +    structured
                                            citations      Markdown
```

---

## Key Features

- **Multi-agent pipeline** — four specialised agents (Planner, Search, Analysis, Report) each with a single responsibility, coordinated by a LangGraph state machine
- **Pluggable data sources** — abstract `DataSource` interface; ships with arXiv and Semantic Scholar; add new sources in one file
- **Provider-agnostic LLM** — LiteLLM abstraction supports OpenAI, Anthropic, Ollama, vLLM, and any OpenAI-compatible endpoint via a single config switch
- **Async-first architecture** — FastAPI + Celery + Redis; the HTTP layer never blocks on pipeline execution
- **Full source attribution** — every claim in the generated report carries a backlink to the originating paper (DOI / arXiv ID)
- **Vector deduplication** — ChromaDB embeddings prevent re-analysing semantically redundant papers across iterations
- **Iterative deepening** — conditional LangGraph edge allows the pipeline to loop Search → Analysis before generating the final report when breadth is insufficient
- **Production-ready** — structured logging, Pydantic-typed config, database migrations with Alembic, health endpoints, and horizontal worker scaling

---

## System Architecture

The following diagram shows the full component topology, from the HTTP layer down to storage:

```
┌─────────────────────────────────────────────────────────────────┐
│                      REST API  (FastAPI)                        │
│         POST /research  ·  GET /status  ·  GET /report          │
└──────────────────────────┬──────────────────────────────────────┘
                           │  enqueue
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  LangGraph Orchestrator                         │
│              State machine  ·  task routing                     │
└────┬────────────────┬──────────────────┬───────────────┬────────┘
     │                │                  │               │
     ▼                ▼                  ▼               ▼
┌─────────┐    ┌───────────┐    ┌──────────────┐  ┌───────────┐
│ Planner │    │  Search   │    │   Analysis   │  │  Report   │
│  agent  │    │  agent    │    │    agent     │  │  agent    │
│         │    │           │    │              │  │           │
│ Breaks  │    │ Queries   │    │ Extracts key │  │ Structures│
│ task to │    │ external  │    │ findings +   │  │ output +  │
│ subtasks│    │ sources   │    │ citations    │  │ citations │
└─────────┘    └─────┬─────┘    └──────────────┘  └───────────┘
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
    ┌──────────┐ ┌──────────┐ ┌──────────────┐
    │  arXiv   │ │ Semantic │ │   Custom     │
    │   API    │ │ Scholar  │ │   sources    │
    └──────────┘ └──────────┘ │ (plugin ABC) │
                              └──────────────┘

─────────────────────── persistence ─────────────────────────────

    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │  PostgreSQL  │   │    Redis     │   │   ChromaDB   │
    │              │   │              │   │              │
    │ Tasks,       │   │ Task queue,  │   │ Vector       │
    │ reports      │   │ cache        │   │ embeddings   │
    └──────────────┘   └──────────────┘   └──────────────┘

                   ┌────────────────────────┐
                   │     Celery workers     │
                   │  Async pipeline exec.  │
                   └────────────────────────┘
```

### LangGraph Pipeline State Flow

Each node receives the shared `ResearchState` and returns a partial update. The conditional edge between Search and Analysis enables iterative deepening:

```
                       START
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Planner node                                           │
│  in:  query                                             │
│  out: state.subtasks[ ]                                 │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Search node                                            │
│  in:  state.subtasks[ ]                                 │
│  out: state.papers[ ]   (deduplicated via ChromaDB)     │
└────────────────────────┬────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │  needs_more_search? │  ◀── conditional edge
              └──────────┬──────────┘
                    no   │   yes (loop back)
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Analysis node                                          │
│  in:  state.papers[ ]                                   │
│  out: state.findings[ ]  (claim · method · relevance)   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Report node                                            │
│  in:  state.findings[ ]                                 │
│  out: state.report  (structured Markdown + citations)   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
                        END
```

---

## Repository Structure

```
leonardo-research/
│
├── src/
│   ├── agents/                    # One module per agent
│   │   ├── base.py                # BaseAgent ABC — run(state) → dict
│   │   ├── planner.py
│   │   ├── search.py
│   │   ├── analysis.py
│   │   └── report.py
│   │
│   ├── graph/                     # LangGraph state machine
│   │   ├── state.py               # ResearchState TypedDict
│   │   ├── nodes.py               # Graph node wrappers
│   │   ├── edges.py               # Conditional routing functions
│   │   └── builder.py             # Compile & export graph
│   │
│   ├── sources/                   # Pluggable data source layer
│   │   ├── base.py                # DataSource ABC
│   │   ├── arxiv.py
│   │   ├── semantic_scholar.py
│   │   ├── models.py
│   │   └── registry.py            # Source loader / registry
│   │
│   ├── api/                       # FastAPI application
│   │   ├── main.py                # App factory
│   │   ├── routers/
│   │   │   ├── research.py        # /research endpoints
│   │   │   └── health.py          # /health endpoint
│   │   ├── schemas/               # Pydantic request / response models
│   │   │   ├── request.py
│   │   │   └── response.py
│   │   └── dependencies.py        # FastAPI dependency injection
│   │
│   ├── tasks/                     # Celery async workers
│   │   ├── celery_app.py
│   │   └── research_task.py
│   │
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── task.py
│   │   └── report.py
│   │   └── paper.py
│   │
│   ├── llm/                       # LLM provider abstraction (LiteLLM)
│   │   ├── base.py
│   │   ├── openai.py
│   │   └── local.py               # Ollama / vLLM
│   │
│   └── core/
│       ├── config.py              # pydantic-settings — all env vars typed
│       ├── logging.py
│       └── exceptions.py
│
├── tests/
│   ├── unit/                      # Isolated agent / source tests
│   ├── integration/               # Graph + DB integration tests
│   └── e2e/                       # Full pipeline via HTTP
│
├── docker/
│   ├── Dockerfile                 # API image (multi-stage)
│   ├── Dockerfile.worker          # Celery worker image
│   └── docker-compose.yml         # Full stack: API, worker, pg, redis, chroma
│
├── migrations/                       # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── docs/
│   ├── architecture.md
│   ├── adding_sources.md          # Guide: implement a new DataSource plugin
|   ├–– api.md
|   ├–– implementation_plan.md
|   ├–– migrations.md
│
├── .env.example
├── pyproject.toml                 # uv / poetry — pinned deps
├── Makefile                       # make dev · test · lint · docker-up
├── LICENCE
├── alembic.ini
├── .gitignore
└── README.md
```

---

## Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| API framework | FastAPI + uvicorn | Async-native, auto-generated OpenAPI docs |
| Agent orchestration | LangGraph | Stateful, resumable, conditional graphs |
| LLM routing | LiteLLM | Single interface for OpenAI, Anthropic, Ollama, vLLM |
| Async workers | Celery + Redis | Battle-tested queue; horizontal scaling via `--concurrency` |
| Relational DB | PostgreSQL + SQLAlchemy 2.x | Typed, async-ready, Alembic migrations |
| Vector store | ChromaDB | Local-first; no extra infrastructure in dev |
| Configuration | pydantic-settings | Typed env vars; no bare `os.getenv()` in codebase |
| Testing | pytest + pytest-asyncio | Full async test coverage |
| Linting / formatting | ruff + mypy | Fast, strict, CI-enforced |
| Packaging | pyproject.toml (uv) | Modern Python standards |
| Containerisation | Docker + Docker Compose | Reproducible multi-service deployment |

---

## Getting Started

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- An OpenAI API key (or a running Ollama instance for local inference)

### 1. Clone and configure

```bash
git clone https://github.com/yourname/leonardo-research.git
cd leonardo-research
cp .env.example .env
```

Edit `.env`:

```env
# LLM provider — swap to "ollama/mistral" for fully local inference
LLM_MODEL=gpt-4o

OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379/0

# Pipeline tuning
MAX_PAPERS_PER_SUBTASK=10
MAX_SEARCH_ITERATIONS=2
```

### 2. Start with Docker (recommended)

```bash
make docker-up
```

This brings up: `api` (port 8000), `worker` (Celery), `postgres`, `redis`, `chromadb`.

### 3. Local development

```bash
# Install dependencies
pip install uv && uv sync

# Run migrations
make migrate

# Start API + worker in separate terminals
make dev-api
make dev-worker
```

---

## API Reference

The API follows REST conventions and is fully documented at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.

### Submit a research task

```http
POST /api/v1/research
Content-Type: application/json

{
  "query": "What are the most recent advances in diffusion models for protein structure prediction?",
  "max_papers": 20,
  "sources": ["arxiv", "semantic_scholar"]
}
```

**Response `202 Accepted`:**

```json
{
  "task_id": "3f7a2b1c-...",
  "status": "pending",
  "status_url": "/api/v1/research/3f7a2b1c-.../status"
}
```

### Poll status

```http
GET /api/v1/research/{task_id}/status
```

```json
{
  "task_id": "3f7a2b1c-...",
  "status": "running",
  "stage": "analysis",
  "papers_found": 17,
  "findings_extracted": 9
}
```

### Retrieve completed report

```http
GET /api/v1/research/{task_id}/report
Accept: application/json       # or text/markdown
```

```json
{
  "task_id": "3f7a2b1c-...",
  "query": "What are the most recent advances in...",
  "report": {
    "executive_summary": "...",
    "key_findings": [
      {
        "claim": "RFDiffusion achieves state-of-the-art...",
        "source": { "title": "...", "arxiv_id": "2305.12345", "url": "..." }
      }
    ],
    "methodology_overview": "...",
    "identified_gaps": ["..."],
    "sources": [...]
  },
  "generated_at": "2024-11-12T14:32:00Z"
}
```

---

## Adding a New Data Source

Implement the `DataSource` abstract class and register it — that is the entire plugin interface:

```python
# src/sources/pubmed.py
from src.sources.base import DataSource, Paper

class PubMedSource(DataSource):
    name = "pubmed"

    async def search(self, query: str, max_results: int = 10) -> list[Paper]:
        # call NCBI E-utilities API
        ...
        return papers
```

```python
# src/sources/registry.py
from src.sources.pubmed import PubMedSource

SOURCES = {
    "arxiv": ArXivSource(),
    "semantic_scholar": SemanticScholarSource(),
    "pubmed": PubMedSource(),          # ← one line
}
```

Then pass `"sources": ["pubmed"]` in the API request. No other changes required.

A full walkthrough is in [`docs/adding_sources.md`](docs/adding_sources.md).

---

## Switching LLM Providers

All LLM calls are routed through LiteLLM. Change the `LLM_MODEL` environment variable — no code changes needed:

```env
# OpenAI
LLM_MODEL=gpt-4o

# Anthropic
LLM_MODEL=claude-3-5-sonnet-20241022

# Local Ollama
LLM_MODEL=ollama/mistral
OLLAMA_BASE_URL=http://localhost:11434

# Any OpenAI-compatible endpoint
LLM_MODEL=openai/custom-model
OPENAI_BASE_URL=http://your-vllm-server:8000/v1
```

---

## Makefile Commands

```bash
make dev-api        # Start FastAPI with hot-reload
make dev-worker     # Start Celery worker (concurrency=2)
make docker-up      # Full stack via Docker Compose
make docker-down    # Tear down containers
make migrate        # Run Alembic migrations
make test           # pytest — unit + integration
make test-e2e       # End-to-end pipeline test
make lint           # ruff check + mypy
make format         # ruff format
make clean          # Remove __pycache__, .pytest_cache, etc.
```

---

## Scaling

The architecture is designed to scale horizontally at the worker tier without changes to the API or database layers:

```bash
# Scale to 8 concurrent pipeline workers
docker compose up --scale worker=8
```

Each worker runs a full LangGraph pipeline independently. Redis acts as both the task queue and the LangGraph checkpoint store, ensuring that if a worker restarts mid-pipeline, the task resumes from the last completed node.

---

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

Built with precision by [Dan Medvedev](https://github.com/danmadrock)

</div>
