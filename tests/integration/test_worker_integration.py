from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.schemas import ResearchTaskCreate
from src.crud.tasks import create_task, get_task
from src.db.base import Base
from src.tasks import research_task


class FakeGraph:
    async def astream(self, state):
        yield {"planner": {"subtasks": ["s1"]}}
        yield {"search": {"papers": [], "search_iteration": 1}}
        yield {"analysis": {"findings": []}}
        yield {"report": {"report": None}}


class FakeHandle:
    def update_state(self, state, meta):
        self.state = state
        self.meta = meta


@pytest.mark.asyncio
async def test_worker_executes_with_fake_graph(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'worker.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as db:
        task = await create_task(db, ResearchTaskCreate(query="q", selected_sources=[], max_papers=3))

    monkeypatch.setattr(research_task, "SessionLocal", factory)
    monkeypatch.setattr(research_task, "build_graph", lambda: FakeGraph())

    result = await research_task._execute_research_task(task.id, FakeHandle())
    assert result["status"] == "completed"

    async with factory() as db:
        refreshed = await get_task(db, task.id)
        assert refreshed is not None
        assert refreshed.completed_at is None or refreshed.completed_at <= datetime.utcnow()

    await engine.dispose()
