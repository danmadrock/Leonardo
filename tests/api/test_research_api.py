from datetime import datetime

from src.api.schemas import ReportRecordCreate, ResearchTaskCreate, ResearchTaskUpdate
from src.crud.reports import upsert_report
from src.crud.tasks import create_task, update_task
from src.models.task import TaskStage, TaskStatus


def test_submit_research_task(client):
    response = client.post(
        "/api/v1/research",
        json={"query": "What are advances in protein diffusion models?"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["stage"] == "queued"


async def test_status_and_report_endpoints(client, db_session_factory):
    async with db_session_factory() as db:
        task = await create_task(
            db,
            ResearchTaskCreate(
                query="What are advances in protein diffusion models?",
                selected_sources=[],
            ),
        )
        await update_task(
            db,
            task,
            ResearchTaskUpdate(
                status=TaskStatus.completed,
                stage=TaskStage.done,
                completed_at=datetime.utcnow(),
            ),
        )
        await upsert_report(
            db,
            ReportRecordCreate(
                task_id=task.id,
                markdown="# done",
                structured_report_json={
                    "executive_summary": "ok",
                    "raw_markdown": "# done",
                },
            ),
        )

    status_resp = client.get(f"/api/v1/research/{task.id}/status")
    assert status_resp.status_code == 200

    report_resp = client.get(f"/api/v1/research/{task.id}/report")
    assert report_resp.status_code == 200
    assert report_resp.json()["task_id"] == task.id
