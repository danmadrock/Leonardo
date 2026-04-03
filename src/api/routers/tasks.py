from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.api.schemas import ResearchTaskCreate, ResearchTaskRead, ResearchTaskUpdate
from src.crud.tasks import create_task, get_task, list_tasks, update_task

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=ResearchTaskRead, status_code=status.HTTP_201_CREATED)
async def create_task_endpoint(
    payload: ResearchTaskCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ResearchTaskRead:
    task = await create_task(db, payload)
    return ResearchTaskRead.model_validate(task)


@router.get("", response_model=list[ResearchTaskRead])
async def list_tasks_endpoint(
    limit: int = Query(default=20, ge=1, le=100),  # noqa: B008
    offset: int = Query(default=0, ge=0),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[ResearchTaskRead]:
    tasks = await list_tasks(db, limit=limit, offset=offset)
    return [ResearchTaskRead.model_validate(task) for task in tasks]


@router.get("/{task_id}", response_model=ResearchTaskRead)
async def get_task_endpoint(
    task_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ResearchTaskRead:
    task = await get_task(db, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    return ResearchTaskRead.model_validate(task)


@router.patch("/{task_id}", response_model=ResearchTaskRead)
async def update_task_endpoint(
    task_id: str,
    payload: ResearchTaskUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ResearchTaskRead:
    task = await get_task(db, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    updated = await update_task(db, task, payload)
    return ResearchTaskRead.model_validate(updated)
