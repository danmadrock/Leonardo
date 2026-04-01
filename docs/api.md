# Leonardo Research API Contract (v1)

> Status: **authoritative contract** for the first production research pipeline API.
> 
> This document defines the API the implementation must converge to, even if current code differs.

---

## 1) Scope and goals

The v1 API is asynchronous and task-oriented:

- Client submits a research query.
- Server creates a task and returns immediately (`202 Accepted`).
- Client polls status.
- Client fetches the final report once completed.

Base path: `/api/v1`

Primary resources:

- `ResearchTask`
- `ResearchReport`

---

## 2) Endpoint summary

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/research` | Create a new research task |
| `GET` | `/research/{task_id}/status` | Get task progress + lifecycle state |
| `GET` | `/research/{task_id}/report` | Get final report (JSON or Markdown) |
| `GET` | `/health` | Liveness probe |
| `GET` | `/readiness` | Readiness probe |

---

## 3) Canonical enums

### 3.1 TaskStatus

```text
pending | running | completed | failed
```

Semantics:

- `pending`: accepted, not yet started by worker.
- `running`: pipeline execution in progress.
- `completed`: report finalized and persisted.
- `failed`: terminal failure, `error` must be populated.

### 3.2 PipelineStage

```text
queued | planner | search | analysis | report | completed | failed
```

Rules:

- `queued` maps to pre-execution (`TaskStatus=pending`).
- `completed` and `failed` are terminal stage markers.
- While `TaskStatus=running`, stage must be one of `planner|search|analysis|report`.

---

## 4) Request/response contracts

## 4.1 `POST /api/v1/research`

Create a new research task.

### Request body

```json
{
  "query": "What are the most recent advances in diffusion models for protein structure prediction?",
  "max_papers": 20,
  "sources": ["arxiv", "semantic_scholar"]
}
```

Field contract:

- `query` (string, required):
  - min length: `10`
  - max length: `2000`
- `max_papers` (integer, optional):
  - default: `20`
  - min: `1`
  - max: `100`
- `sources` (array[string], optional):
  - default: all enabled sources
  - each value must be registered source name
  - duplicates rejected

### Response `202 Accepted`

```json
{
  "task_id": "3f7a2b1c-12de-4f87-88c7-1f57c43d6f02",
  "status": "pending",
  "stage": "queued",
  "status_url": "/api/v1/research/3f7a2b1c-12de-4f87-88c7-1f57c43d6f02/status",
  "report_url": "/api/v1/research/3f7a2b1c-12de-4f87-88c7-1f57c43d6f02/report",
  "created_at": "2026-03-31T00:00:00Z"
}
```

### Errors

- `400 Bad Request`: malformed JSON.
- `422 Unprocessable Entity`: validation failure.
- `503 Service Unavailable`: queue unavailable.

---

## 4.2 `GET /api/v1/research/{task_id}/status`

Get lifecycle and progress counters.

### Response `200 OK`

```json
{
  "task_id": "3f7a2b1c-12de-4f87-88c7-1f57c43d6f02",
  "status": "running",
  "stage": "analysis",
  "progress": {
    "search_iteration": 1,
    "max_search_iterations": 2,
    "subtasks_total": 4,
    "subtasks_completed": 4,
    "papers_found": 17,
    "findings_extracted": 9
  },
  "error": null,
  "created_at": "2026-03-31T00:00:00Z",
  "updated_at": "2026-03-31T00:00:10Z"
}
```

### Terminal failure example

```json
{
  "task_id": "3f7a2b1c-12de-4f87-88c7-1f57c43d6f02",
  "status": "failed",
  "stage": "failed",
  "progress": {
    "search_iteration": 1,
    "max_search_iterations": 2,
    "subtasks_total": 4,
    "subtasks_completed": 4,
    "papers_found": 5,
    "findings_extracted": 0
  },
  "error": {
    "code": "ANALYSIS_PROVIDER_ERROR",
    "message": "LLM provider timeout",
    "retryable": true
  },
  "created_at": "2026-03-31T00:00:00Z",
  "updated_at": "2026-03-31T00:00:20Z"
}
```

### Errors

- `404 Not Found`: unknown `task_id`.

---

## 4.3 `GET /api/v1/research/{task_id}/report`

Return final report.

### Behavior

- If status is `completed`: return report.
- If status is `failed`: return `409` with failure payload.
- If status is `pending|running`: return `425 Too Early`.

### Response `200 OK` (`Accept: application/json`)

```json
{
  "task_id": "3f7a2b1c-12de-4f87-88c7-1f57c43d6f02",
  "query": "What are the most recent advances in diffusion models for protein structure prediction?",
  "report": {
    "executive_summary": "...",
    "key_findings": [
      {
        "claim": "RFDiffusion achieves state-of-the-art...",
        "methodology": "Conditional denoising with structure constraints...",
        "limitations": "Evaluation concentrates on benchmark families...",
        "relevance": 0.93,
        "source_paper": {
          "title": "...",
          "url": "https://...",
          "doi": null,
          "arxiv_id": "2305.12345"
        }
      }
    ],
    "methodology_overview": "...",
    "identified_gaps": ["..."],
    "sources": [
      {
        "title": "...",
        "url": "https://...",
        "doi": null,
        "arxiv_id": "2305.12345"
      }
    ],
    "raw_markdown": "# Research Report ..."
  },
  "generated_at": "2026-03-31T00:00:30Z"
}
```

### Response `200 OK` (`Accept: text/markdown`)

Returns `raw_markdown` body with content type `text/markdown; charset=utf-8`.

### Errors

- `404 Not Found`: unknown `task_id`.
- `409 Conflict`: task failed.
- `425 Too Early`: report not ready.

---

## 5) Report schema (canonical)

```yaml
Report:
  executive_summary: string
  key_findings: Finding[]
  methodology_overview: string
  identified_gaps: string[]
  sources: PaperRef[]
  raw_markdown: string

Finding:
  claim: string
  methodology: string
  limitations: string
  relevance: float  # 0.0..1.0
  source_paper: PaperRef

PaperRef:
  title: string
  url: string
  doi: string|null
  arxiv_id: string|null
```

Invariants:

1. Every `key_findings[i].source_paper` must appear in `sources`.
2. `sources` must be de-duplicated by `(doi || arxiv_id || normalized_url)`.
3. `raw_markdown` must include inline citations mappable to `sources`.

---

## 6) Error payload contract

All non-2xx responses must use:

```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human-readable detail",
    "retryable": false
  }
}
```

Standard codes (v1):

- `TASK_NOT_FOUND`
- `INVALID_SOURCE`
- `REPORT_NOT_READY`
- `TASK_FAILED`
- `QUEUE_UNAVAILABLE`
- `INTERNAL_ERROR`

---

## 7) Idempotency and compatibility

- `POST /research` is non-idempotent by default.
- Optional future header: `Idempotency-Key`.
- Backward compatibility rule for v1: additive fields only; no renames/removals.

---

## 8) Non-goals (v1)

- No task cancellation endpoint.
- No SSE/WebSocket streaming contract.
- No pagination for report internals.
- No authentication/authorization contract in this doc.
