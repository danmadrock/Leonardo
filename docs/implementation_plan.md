# Implementation Plan — Converge Code to v1 Contract

> Purpose: lock implementation sequence to the API contract in `docs/api.md` and stop docs/code drift.

---

## 1) Definition of Done (DoD)

The v1 contract is done when all are true:

1. FastAPI exposes only v1 research endpoints from `docs/api.md`.
2. Pydantic schemas exactly match request/response contracts and enums.
3. Task lifecycle in DB + worker transitions matches status/stage rules.
4. LangGraph `ResearchState` shape matches this plan.
5. Report persistence and retrieval match canonical `Report` schema.
6. Contract tests fail on any schema drift.

---

## 2) Canonical state shape (single source of truth)

`src/graph/state.py` must define and export this typed state:

```python
class ResearchState(TypedDict):
    # Identity
    task_id: str
    query: str

    # Request config
    requested_sources: list[str]
    max_papers: int
    max_search_iterations: int

    # Pipeline outputs
    subtasks: list[str]
    papers: list[PaperRef]
    findings: list[Finding]
    report: Report | None

    # Runtime progress / control
    status: TaskStatus
    stage: PipelineStage
    search_iteration: int

    # Failure channel
    error: ErrorPayload | None
```

Field ownership by node:

- Planner writes: `subtasks`, `stage=planner`.
- Search writes: `papers`, `search_iteration`, `stage=search`.
- Analysis writes: `findings`, `stage=analysis`.
- Report writes: `report`, `stage=report` then `stage=completed`, `status=completed`.
- Global failure handler writes: `status=failed`, `stage=failed`, `error`.

---

## 3) Task lifecycle contract

## 3.1 Allowed transitions

```text
pending/queued
  -> running/planner
  -> running/search
  -> running/analysis
  -> running/report
  -> completed/completed

(any running stage)
  -> failed/failed

pending/queued
  -> failed/failed    # e.g., broker/worker startup failure
```

Invalid transitions must raise internal error and be logged.

## 3.2 Persistence requirements

`tasks` table minimum fields:

- `id` (uuid string)
- `query` (text)
- `status` (`pending|running|completed|failed`)
- `stage` (`queued|planner|search|analysis|report|completed|failed`)
- `error_code` (nullable string)
- `error_message` (nullable text)
- `created_at` (timestamp)
- `updated_at` (timestamp)

`reports` table minimum fields:

- `task_id` (fk, pk)
- `markdown` (text)
- `report_json` (jsonb; canonical report object)
- `created_at` (timestamp)

---

## 4) API implementation plan

## 4.1 Schemas first

Create dedicated research schemas:

- `src/api/schemas/research.py`
  - `ResearchCreateRequest`
  - `ResearchCreateResponse`
  - `ResearchStatusResponse`
  - `ResearchReportResponse`
  - `ErrorResponse`
  - `TaskStatus`, `PipelineStage`

Rules:

- No endpoint-local ad-hoc dict responses.
- All responses serialized through schema classes.

## 4.2 Router and versioning

Create `src/api/routers/research.py` with:

- `POST /api/v1/research`
- `GET /api/v1/research/{task_id}/status`
- `GET /api/v1/research/{task_id}/report`

Keep current paper CRUD out of v1 contract surface unless explicitly documented separately.

## 4.3 Service layer

Add service functions (or module) to centralize contract logic:

- `create_task(...)`
- `enqueue_task(...)`
- `get_status(...)`
- `get_report(...)`

Router must not directly encode lifecycle rules.

---

## 5) Worker and graph execution plan

1. Worker loads task, builds initial `ResearchState` from DB row + request options.
2. Worker sets `status=running`, `stage=planner` before graph execution.
3. Each node returns partial updates only.
4. After each node, persist status/stage/progress snapshot for polling endpoint.
5. On successful completion:
   - persist canonical report JSON + markdown,
   - set `status=completed`, `stage=completed`.
6. On exception:
   - map to `ErrorPayload` with code/message/retryable,
   - set `status=failed`, `stage=failed`.

---

## 6) Drift prevention gates (required)

## 6.1 Contract tests

Add tests that assert exact response shapes and enums:

- `tests/e2e/test_research_api_contract.py`
  - create returns `202` and required fields
  - status response includes stage/progress/error
  - report JSON schema matches canonical report
  - markdown representation available
  - non-ready report returns `425`

## 6.2 Schema snapshot

Generate OpenAPI snapshot and diff in CI:

- produce `openapi.json`
- compare with committed snapshot
- fail on breaking changes unless consciously updated

## 6.3 Type-level guardrails

- `ResearchState` and API schemas imported from one module each (no duplicate enum definitions).
- mypy/pyright checks enabled for schema modules.

---

## 7) Execution order (milestones)

### Milestone A — Contract foundation

- Fill `docs/api.md` and this plan (done in this change).
- Add schema classes + enums.
- Add research router skeleton with TODO service calls.

### Milestone B — Persistence/lifecycle alignment

- Expand task/report models and migration for stage + error fields + report_json.
- Implement lifecycle transition helpers.

### Milestone C — Pipeline wiring

- Implement `ResearchState` and graph builder/nodes.
- Connect Celery task execution to lifecycle transitions.

### Milestone D — Contract verification

- Add e2e contract tests.
- Add OpenAPI snapshot gating in CI.

---

## 8) Explicit out-of-contract behavior

The following are implementation details and may change without API version bump:

- Exact prompts and agent internals.
- Search dedupe algorithm specifics.
- Source provider retry strategy.
- Internal DB indexing and query plans.