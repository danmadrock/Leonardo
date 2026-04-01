# Architecture — Leonardo Research

> **Audience:** contributors, technical reviewers, and engineers onboarding to the codebase.  
> This document explains *why* the system is designed the way it is, not just *what* it does.

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [System Overview](#2-system-overview)
3. [Component Deep Dive](#3-component-deep-dive)
   - 3.1 [REST API Layer](#31-rest-api-layer)
   - 3.2 [LangGraph Orchestrator](#32-langgraph-orchestrator)
   - 3.3 [Agent Layer](#33-agent-layer)
   - 3.4 [Data Source Layer](#34-data-source-layer)
   - 3.5 [LLM Abstraction Layer](#35-llm-abstraction-layer)
   - 3.6 [Async Worker Layer](#36-async-worker-layer)
   - 3.7 [Persistence Layer](#37-persistence-layer)
4. [Data Flow](#4-data-flow)
5. [State Machine Design](#5-state-machine-design)
6. [Concurrency Model](#6-concurrency-model)
7. [Failure Modes and Resilience](#7-failure-modes-and-resilience)
8. [Observability](#8-observability)
9. [Security Considerations](#9-security-considerations)
10. [Performance Characteristics](#10-performance-characteristics)
11. [Extension Points](#11-extension-points)
12. [Decision Log](#12-decision-log)

---

## 1. Design Philosophy

Leonardo Research is built around four principles that informed every architectural decision:

**Single responsibility at every layer.** The HTTP layer validates and enqueues. Workers execute pipelines. Agents transform state. Sources retrieve data. No component crosses its boundary. This makes each unit independently testable and replaceable.

**Explicit state over implicit side effects.** All pipeline state flows through a single typed `ResearchState` object passed between LangGraph nodes. There are no shared mutable globals, no thread-local state, no implicit context threading. At any point during execution you can inspect the full state and understand exactly where the pipeline is.

**Extensibility as a first-class concern.** New data sources, new LLM providers, and new agent types can each be added without modifying existing code — only by adding new files and registering them. The system follows the Open/Closed Principle by design.

**Async by default.** Every I/O-bound operation — LLM calls, HTTP requests to arXiv, database reads — is `async`. The system is written for `asyncio` from the ground up, not retrofitted. Synchronous code exists only where a dependency forces it (e.g., some SQLAlchemy operations), and those are isolated.

---

## 2. System Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                         CLIENT                                     │
└──────────────────────────────┬─────────────────────────────────────┘
                               │  HTTP
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                    FASTAPI  APPLICATION                            │
│                                                                    │
│   POST /research    GET /research/{id}    GET /research/{id}/report│
│                                                                    │
│   ┌────────────────────────────────────────────────────────────┐   │
│   │  Request validation (Pydantic)  →  Celery task enqueue     │   │
│   └────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬─────────────────────────────────────┘
                               │  Redis (Celery broker)
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                     CELERY  WORKER(S)                              │
│                                                                    │
│   ┌────────────────────────────────────────────────────────────┐   │
│   │               LANGGRAPH  ORCHESTRATOR                      │   │
│   │                                                            │   │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │   │
│   │  │ Planner  │→ │  Search  │→ │ Analysis │→ │  Report  │    │   │
│   │  │  agent   │  │  agent   │  │  agent   │  │  agent   │    │   │
│   │  └──────────┘  └─────┬────┘  └──────────┘  └──────────┘    │   │
│   │                      │ conditional loop                    │   │
│   │                      └──────────────────────────────────┐  │   │
│   │                                                         │  │   │
│   │              ResearchState  (TypedDict)                 │  │   │
│   └────────────────────────────────────────────────────────────┘   │
│                                                                    │
│   ┌─────────────────────┐    ┌─────────────────────────────────┐   │
│   │   SOURCE REGISTRY   │    │       LLM  ABSTRACTION          │   │
│   │  arXiv              │    │  LiteLLM → OpenAI / Anthropic   │   │
│   │  Semantic Scholar   │    │         / Ollama / vLLM         │   │
│   │  [ pluggable ]      │    └─────────────────────────────────┘   │
│   └─────────────────────┘                                          │
└──────┬──────────────────────────────────────────┬──────────────────┘
       │                                          │
       ▼                                          ▼
┌─────────────┐   ┌─────────────┐   ┌────────────────────────────┐
│ PostgreSQL  │   │    Redis    │   │         ChromaDB           │
│             │   │             │   │                            │
│ Tasks       │   │ Task queue  │   │  Paper embeddings          │
│ Reports     │   │ LG checkpts │   │  Deduplication index       │
│ Papers      │   │ Result cache│   │                            │
└─────────────┘   └─────────────┘   └────────────────────────────┘
```

---

## 3. Component Deep Dive

### 3.1 REST API Layer

**Location:** `src/api/`

The API is intentionally thin. Its only jobs are:

1. Validate incoming requests via Pydantic schemas
2. Persist an initial `Task` record to PostgreSQL with `status=pending`
3. Enqueue a Celery task with the task UUID
4. Return `202 Accepted` with the task ID and a polling URL

The API never imports from `src/agents/` or `src/graph/`. It knows nothing about the pipeline internals. This decoupling means the entire pipeline can be refactored without touching a single API file.

**Router structure:**

```
src/api/routers/
├── research.py    POST /research, GET /research/{id}, GET /research/{id}/report
└── health.py      GET /health, GET /readiness
```

**Dependency injection** (`src/api/dependencies.py`) provides:

- `get_db()` — async SQLAlchemy session
- `get_celery()` — Celery application instance
- `get_settings()` — typed config singleton

All three are injected via FastAPI's `Depends()`. No global state is accessed directly inside route handlers.

**SSE streaming** (`GET /research/{id}/status`) uses `StreamingResponse` with an async generator that polls Redis for state updates every 500ms and yields JSON-encoded progress events. This avoids long-polling overhead without requiring WebSocket infrastructure.

---

### 3.2 LangGraph Orchestrator

**Location:** `src/graph/`

LangGraph is the backbone of the pipeline. It provides:

- **Typed state** — the graph operates on a `ResearchState` TypedDict; nodes receive the full state and return a partial dict of keys to update
- **Conditional edges** — routing logic is a plain Python function, not configuration
- **Checkpointing** — the `AsyncRedisSaver` checkpointer writes state after every node completes; if a worker crashes, the task resumes from the last successful node on restart
- **Streaming** — `graph.astream()` yields state deltas after each node, which are forwarded to the Redis SSE channel

**Graph compilation** (`src/graph/builder.py`):

```python
def build_graph() -> CompiledGraph:
    builder = StateGraph(ResearchState)

    builder.add_node("planner",  planner_node)
    builder.add_node("search",   search_node)
    builder.add_node("analysis", analysis_node)
    builder.add_node("report",   report_node)

    builder.set_entry_point("planner")
    builder.add_edge("planner", "search")
    builder.add_conditional_edges(
        "search",
        should_continue_searching,      # routing function in edges.py
        {"search": "search", "analysis": "analysis"},
    )
    builder.add_edge("analysis", "report")
    builder.add_edge("report",   END)

    checkpointer = AsyncRedisSaver.from_conn_string(settings.REDIS_URL)
    return builder.compile(checkpointer=checkpointer)
```

The compiled graph is a module-level singleton, initialised once at worker startup.

**State schema** (`src/graph/state.py`):

```python
class ResearchState(TypedDict):
    task_id:          str
    query:            str
    subtasks:         list[str]
    papers:           list[Paper]
    findings:         list[Finding]
    report:           Report | None
    search_iteration: int                  # guards the loop
    status:           TaskStatus
    error:            str | None
```

Every field has a clear owner: `planner` writes `subtasks`; `search` appends to `papers`; `analysis` writes `findings`; `report` writes `report`. No node touches another node's output fields.

---

### 3.3 Agent Layer

**Location:** `src/agents/`

All agents inherit from `BaseAgent`:

```python
class BaseAgent(ABC):
    def __init__(self, llm: BaseLLM) -> None:
        self.llm = llm

    @abstractmethod
    async def run(self, state: ResearchState) -> dict:
        """Return partial state update."""
        ...
```

Agents are pure async functions wrapped in a class for dependency injection (the LLM instance). The LangGraph node wrappers in `src/graph/nodes.py` call `agent.run(state)` and return the result — the graph infrastructure handles merging the partial update into the full state.

**Planner agent** (`src/agents/planner.py`)

Receives `state["query"]`. Uses a structured output prompt to ask the LLM to decompose the query into 3–5 independent search subtasks, each targeting a different angle of the topic. Returns `{"subtasks": [...]}`.

The prompt includes a few-shot example of good decomposition vs. poor decomposition. This dramatically improves consistency across different LLM providers.

**Search agent** (`src/agents/search.py`)

Receives `state["subtasks"]`. Calls all registered sources concurrently via `asyncio.gather`. Deduplicates results by a compound key of `(doi or arxiv_id, title_hash)`. Checks ChromaDB for semantic near-duplicates (cosine similarity > 0.92) before adding a paper to state — this prevents the analysis agent from re-processing papers that cover identical ground under different titles.

Returns `{"papers": [...], "search_iteration": state["search_iteration"] + 1}`.

**Analysis agent** (`src/agents/analysis.py`)

Receives `state["papers"]`. For each paper, sends the abstract + metadata to the LLM and extracts a structured `Finding`:

```python
class Finding(BaseModel):
    claim:        str           # the core contribution
    methodology:  str           # how they did it
    limitations:  str           # what they acknowledge as gaps
    relevance:    float         # 0.0–1.0, model-scored
    source_paper: PaperRef      # DOI / arXiv ID / URL
```

Papers with `relevance < 0.3` are excluded from the findings list. This threshold is configurable via `MIN_FINDING_RELEVANCE` in settings.

To avoid rate limits and context window overflow, papers are analysed in batches of `ANALYSIS_BATCH_SIZE` (default: 5) with `asyncio.gather`.

**Report agent** (`src/agents/report.py`)

Receives `state["findings"]`. Produces a structured Markdown report with a fixed schema. The fixed schema is intentional — it makes the output predictable for downstream consumers and UI rendering.

Report schema:

```
# Research Report: {query}

## Executive Summary
## Key Findings
  ### Finding 1 [source citation]
  ...
## Methodology Overview
## Research Gaps
## Sources
```

---

### 3.4 Data Source Layer

**Location:** `src/sources/`

The source layer is designed as a plugin system. The contract is a single abstract method:

```python
class DataSource(ABC):
    name: ClassVar[str]

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[Paper]:
        ...
```

The `Paper` model is defined in `src/sources/base.py` and is the canonical data structure for all paper metadata:

```python
class Paper(BaseModel):
    title:       str
    abstract:    str
    authors:     list[str]
    year:        int | None
    doi:         str | None
    arxiv_id:    str | None
    url:         str
    source:      str            # name of the DataSource that returned this
    pdf_url:     str | None
```

The **source registry** (`src/sources/registry.py`) is a dict of `{name: DataSource instance}`. The search agent queries `settings.ENABLED_SOURCES` (a list of names from config) and looks each up in the registry. Sources not in `ENABLED_SOURCES` are never instantiated.

**arXiv source** (`src/sources/arxiv.py`) uses the `arxiv` Python client library with exponential backoff retry logic. It maps the arXiv `Result` object to `Paper`.

**Semantic Scholar source** (`src/sources/semantic_scholar.py`) calls the Semantic Scholar Graph API. It enriches results with citation count and influential citation count, which are stored in `Paper.metadata` and used by the analysis agent to weight relevance scoring.

See [`adding_sources.md`](adding_sources.md) for the full guide to implementing a new source.

---

### 3.5 LLM Abstraction Layer

**Location:** `src/llm/`

All LLM calls go through a `BaseLLM` interface wrapping LiteLLM:

```python
class BaseLLM(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
    ) -> str | BaseModel:
        ...
```

When `response_model` is provided, the implementation uses LiteLLM's `instructor` integration to return a validated Pydantic object instead of raw text. This is how agents receive structured output from the LLM without parsing it themselves.

The concrete implementation (`src/llm/openai.py`) handles:
- Retry with exponential backoff on rate-limit errors (429)
- Token counting and context window management
- Streaming (used for report generation to feed SSE output)

Switching providers is a config change:

```env
LLM_MODEL=gpt-4o                           # OpenAI
LLM_MODEL=claude-3-5-sonnet-20241022       # Anthropic
LLM_MODEL=ollama/mistral                   # Local Ollama
LLM_MODEL=openai/custom                    # Any OpenAI-compatible endpoint
OPENAI_BASE_URL=http://your-vllm:8000/v1
```

---

### 3.6 Async Worker Layer

**Location:** `src/tasks/`

Celery workers decouple pipeline execution from the HTTP request lifecycle. The worker receives a task UUID, loads the `Task` record from PostgreSQL, runs the LangGraph pipeline, and writes the completed `Report` back to the database.

```python
@celery_app.task(bind=True, max_retries=3)
def run_research_pipeline(self, task_id: str) -> None:
    asyncio.run(_run_async(task_id))

async def _run_async(task_id: str) -> None:
    graph  = get_compiled_graph()
    state  = ResearchState(task_id=task_id, query=..., ...)
    config = {"configurable": {"thread_id": task_id}}

    async for event in graph.astream(state, config=config):
        await _publish_progress(task_id, event)   # Redis pub/sub → SSE

    await _persist_report(task_id, state)
```

Worker configuration (`docker/docker-compose.yml`):

```yaml
worker:
  command: celery -A src.tasks.celery_app worker --concurrency=4 --loglevel=info
  deploy:
    replicas: 2
```

Scale horizontally: `docker compose up --scale worker=N`. Each worker is stateless; the LangGraph checkpointer in Redis ensures that if a worker is terminated mid-pipeline, the next available worker resumes from the last checkpoint.

---

### 3.7 Persistence Layer

**Three stores, three purposes:**

**PostgreSQL** (via SQLAlchemy 2.x async + Alembic) is the source of truth for:
- `tasks` — task metadata, status, timestamps
- `reports` — final report content and structured findings
- `papers` — deduplicated paper records (FK from reports)

It is the only store that a human operator would query directly (e.g., "how many tasks completed this week").

**Redis** serves two roles:
1. **Celery broker** — task queue and result backend
2. **LangGraph checkpointer** — graph state snapshots keyed by `thread_id` (task UUID). TTL is set to 7 days; after that, incomplete tasks are marked `failed` by a cron job.

Redis is treated as a cache and queue — it is not a source of truth. The system can survive a full Redis flush by re-running failed tasks.

**ChromaDB** stores vector embeddings of paper abstracts. Used by the search agent for semantic deduplication. Also enables future features such as "find papers similar to this finding" or semantic search across the full paper corpus. ChromaDB persists to a mounted volume in Docker.

---

## 4. Data Flow

A complete request lifecycle from HTTP to stored report:

```
1.  POST /api/v1/research
      │
      ├── Pydantic validates request body
      ├── INSERT INTO tasks (id, query, status='pending')
      ├── celery.delay('run_research_pipeline', task_id)
      └── return 202 { task_id, status_url }

2.  Celery worker picks up task from Redis queue
      │
      └── asyncio.run(_run_async(task_id))

3.  LangGraph: planner node
      │  input:  state.query
      │  LLM call → structured JSON → list[str]
      └── state.subtasks = ["angle 1", "angle 2", "angle 3"]

4.  LangGraph: search node
      │  input:  state.subtasks
      │  asyncio.gather(arxiv.search(s) for s in subtasks)
      │  asyncio.gather(semantic_scholar.search(s) for s in subtasks)
      │  deduplicate by DOI / arXiv ID
      │  filter near-duplicates via ChromaDB cosine similarity
      │  embed new papers → ChromaDB
      └── state.papers = [Paper, ...]

5.  Conditional edge: should_continue_searching?
      │  if len(state.papers) < MIN_PAPERS and iteration < MAX_ITERATIONS:
      │      → loop back to search node with refined query
      └── else: → analysis node

6.  LangGraph: analysis node
      │  input:  state.papers
      │  for batch in chunks(state.papers, ANALYSIS_BATCH_SIZE):
      │      asyncio.gather(analyse(paper) for paper in batch)
      └── state.findings = [Finding, ...]

7.  LangGraph: report node
      │  input:  state.findings
      │  LLM streaming call → Markdown
      │  findings → inline citations
      └── state.report = Report(markdown=..., sources=[...])

8.  Worker post-processing
      ├── INSERT INTO reports (task_id, content, sources)
      ├── UPDATE tasks SET status='done', completed_at=NOW()
      └── publish 'done' event to Redis pub/sub channel

9.  SSE stream delivers final status to any listening clients
```

---

## 5. State Machine Design

The LangGraph graph is a directed graph with one conditional edge. The full state transition diagram:

```
         ┌─────────┐
         │  START  │
         └────┬────┘
              │
              ▼
         ┌─────────┐
         │ planner │   writes: subtasks
         └────┬────┘
              │
              ▼
┌─────────────────────────┐
│         search          │   writes: papers, search_iteration
└────────────┬────────────┘
             │
    ┌────────┴────────┐
    │                 │
    │  should_continue_searching(state):
    │  • len(papers) < MIN_PAPERS
    │  • AND iteration < MAX_ITERATIONS
    │                 │
  True (loop)      False (continue)
    │                 │
    └────────┐        │
             │        ▼
             │   ┌──────────┐
             │   │ analysis │   writes: findings
             │   └────┬─────┘
             │        │
             │        ▼
             │   ┌──────────┐
             │   │  report  │   writes: report
             │   └────┬─────┘
             │        │
             └───     ▼
                   ┌─────┐
                   │ END │
                   └─────┘
```

The conditional routing function is a pure function with no side effects:

```python
def should_continue_searching(state: ResearchState) -> str:
    insufficient = len(state["papers"]) < settings.MIN_PAPERS_THRESHOLD
    can_iterate  = state["search_iteration"] < settings.MAX_SEARCH_ITERATIONS

    if insufficient and can_iterate:
        return "search"
    return "analysis"
```

---

## 6. Concurrency Model

The system has three concurrency domains, each with different semantics:

**Within a single pipeline (asyncio):**  
All I/O within a worker runs on a single asyncio event loop. Source searches are parallelised with `asyncio.gather`. Analysis batches are parallelised with `asyncio.gather`. This provides concurrency without the overhead of threads and avoids GIL contention.

**Across pipelines (Celery workers):**  
Each running pipeline is an independent Celery task executing in its own process. Multiple pipelines run in true parallel. The number of concurrent pipelines is `workers × concurrency_per_worker`. Default: `2 workers × 4 concurrency = 8 pipelines`.

**Database access:**  
SQLAlchemy 2.x async engine with a connection pool (`pool_size=10`, `max_overflow=20`). All database operations use `async with session:` context managers; sessions are never shared between tasks.

**Redis access:**  
The `AsyncRedisSaver` for LangGraph checkpointing and the Celery broker both use connection pooling via `aioredis`. The two connection pools are separate to avoid head-of-line blocking between checkpoint writes and task queue operations.

---

## 7. Failure Modes and Resilience

| Failure | Detection | Recovery |
|---|---|---|
| LLM rate limit (429) | `litellm.RateLimitError` | Exponential backoff, up to 3 retries |
| LLM API timeout | `asyncio.TimeoutError` after 30s | Retry with backoff |
| arXiv / Semantic Scholar down | HTTP error or timeout | Source skipped; pipeline continues with available results |
| Worker crash mid-pipeline | Redis checkpoint exists | Next worker resumes from last node |
| Redis down | Celery cannot enqueue | API returns 503; no tasks accepted |
| PostgreSQL down | SQLAlchemy connection error | API returns 503; task not created |
| Celery task exceeds time limit | `SoftTimeLimitExceeded` | Task marked `failed`; error message stored |

**Dead letter handling:** Tasks that exceed `MAX_RETRIES` are moved to a `failed_tasks` Celery queue. A separate cron job (`scripts/retry_failed.py`) can requeue them after manual review.

**Partial results:** If the pipeline fails during the `report` node, the collected `findings` are still persisted to the database. The client receives a `partial` status and can access whatever was extracted.

---

## 8. Observability

**Structured logging** (`src/core/logging.py`):  
All log statements use `structlog` with JSON output in production. Every log line carries `task_id`, `agent`, `stage`, and `duration_ms` fields. This makes it trivial to filter all log lines for a specific pipeline execution in any log aggregation tool.

**Health endpoints:**

```
GET /health     — always 200; confirms the process is alive
GET /readiness  — 200 only if DB and Redis are reachable
```

The readiness endpoint is used by Docker Compose `healthcheck` and Kubernetes liveness/readiness probes.

**Celery monitoring:**  
The Celery configuration includes `task_send_sent_event=True` and `worker_send_task_events=True`. This enables real-time monitoring via Flower (`make flower`) or any Celery-compatible APM (Datadog, New Relic).

**LangGraph traces:**  
When `LANGCHAIN_TRACING_V2=true` is set in `.env`, all graph executions are traced to LangSmith. This provides a visual execution trace of every node, including inputs, outputs, and LLM call details — invaluable for debugging agent behaviour.

---

## 9. Security Considerations

**API keys are never logged.** The `settings` object masks sensitive fields (`openai_api_key`, `database_url`) in its `__repr__`. Structlog's processor chain includes a `mask_secrets` processor that redacts any log value containing `key`, `secret`, or `password`.

**Input sanitisation.** Research queries are treated as untrusted user input. They are never interpolated directly into LLM system prompts — they are passed as `user` role messages. SQL queries use parameterised statements exclusively via SQLAlchemy's ORM.

**Source URL validation.** Before fetching any URL returned by a data source, the URL is validated against an allowlist of known scientific domains (`arxiv.org`, `api.semanticscholar.org`, etc.). This prevents server-side request forgery (SSRF) via a malicious source plugin.

**Docker security.** Containers run as non-root users (`USER 1001`). The API container has no write access to the host filesystem. Environment variables are the only secrets injection mechanism; `.env` files are excluded from images via `.dockerignore`.

---

## 10. Performance Characteristics

Approximate latency and throughput figures on a 4-core machine with GPT-4o:

| Metric | Value |
|---|---|
| API response (enqueue) | < 100ms |
| Planner node | 2–4s (one LLM call) |
| Search node (2 sources, 3 subtasks) | 3–8s (parallel HTTP) |
| Analysis node (15 papers, batch=5) | 15–35s (3 parallel LLM calls) |
| Report node | 10–20s (one streaming LLM call) |
| **End-to-end pipeline** | **~45–90 seconds** |
| Throughput (8 concurrent workers) | ~5–7 completed reports/minute |

The dominant cost is LLM tokens. Switching to `gpt-4o-mini` or a local model reduces pipeline time to under 30 seconds at significantly lower cost, with some quality trade-off in analysis depth.

**ChromaDB deduplication** saves meaningful LLM tokens on repeated or overlapping queries. A corpus of 1,000 embedded papers reduces redundant analysis calls by roughly 15–25% on average.

---

## 11. Extension Points

The system has four explicit extension points, each with a defined interface:

| Extension point | Location | Interface |
|---|---|---|
| New data source | `src/sources/` | `DataSource` ABC |
| New LLM provider | `src/llm/` | `BaseLLM` ABC |
| New agent | `src/agents/` | `BaseAgent` ABC |
| New graph topology | `src/graph/builder.py` | LangGraph `StateGraph` |

Adding a new agent to the graph requires: implementing `BaseAgent`, adding a node to `builder.py`, and defining any new state keys it reads/writes in `state.py`. The rest of the system is unaffected.

See [`adding_sources.md`](adding_sources.md) for a complete walkthrough of the most common extension: adding a new data source.

---

## 12. Decision Log

This section records the key architectural decisions and the reasoning that led to them. Future contributors should read this before proposing large changes.

---

**ADR-001: LangGraph over a custom pipeline runner**

*Decision:* Use LangGraph as the orchestration layer.  
*Alternatives considered:* Custom `asyncio` pipeline, Prefect, Airflow.  
*Reasoning:* LangGraph provides typed state, conditional edges, and Redis-backed checkpointing with ~50 lines of graph definition code. A custom pipeline would require reimplementing checkpointing, error recovery, and state propagation. Prefect and Airflow are designed for data pipelines, not LLM agent graphs; they lack first-class support for LLM streaming and conditional branching on agent output.

---

**ADR-002: Celery over FastAPI BackgroundTasks**

*Decision:* Run pipelines in Celery workers, not in FastAPI background tasks.  
*Alternatives considered:* `BackgroundTasks`, `asyncio.create_task`.  
*Reasoning:* A pipeline can take 60–90 seconds. FastAPI background tasks are tied to the lifetime of the HTTP worker process — a Kubernetes pod restart or rolling deploy would silently kill in-flight pipelines. Celery tasks are durable (stored in Redis), retryable, and observable. The operational cost of running Redis (already required for LangGraph checkpointing) is zero.

---

**ADR-003: LiteLLM over direct OpenAI SDK**

*Decision:* Route all LLM calls through LiteLLM.  
*Alternatives considered:* OpenAI SDK directly, LangChain's LLM wrappers.  
*Reasoning:* LiteLLM provides a single consistent interface for 100+ providers. The marginal overhead is negligible. Using the OpenAI SDK directly would couple every agent to a single provider; switching to a local model for cost reduction would require touching every agent. LangChain's wrappers are heavier and carry implicit state.

---

**ADR-004: ChromaDB over pgvector**

*Decision:* Use ChromaDB for vector embeddings, not pgvector.  
*Alternatives considered:* pgvector (PostgreSQL extension), Pinecone, Qdrant.  
*Reasoning:* ChromaDB runs as a local container with zero configuration, matching the project's goal of a fully self-contained `docker compose up` deployment. pgvector requires a PostgreSQL extension and schema changes that complicate Alembic migrations. Pinecone and Qdrant are managed services that introduce an external dependency. ChromaDB can be swapped for any of these in `src/sources/` without touching agent code.

---

**ADR-005: Fixed report schema**

*Decision:* The report agent produces a fixed Markdown schema (summary → findings → methodology → gaps → sources).  
*Alternatives considered:* Let the LLM determine the structure; configurable templates.  
*Reasoning:* A fixed schema makes the output predictable for downstream consumers (a future UI, an export tool, a user's scripts). It also makes the analysis agent's job clearer — it extracts structured `Finding` objects that map directly to sections. Configurable templates add complexity without clear benefit at this stage; if needed, this is a non-breaking addition.
