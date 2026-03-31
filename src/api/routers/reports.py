from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.api.schemas import ReportRecordCreate, ReportRecordRead, ReportRecordUpdate
from src.crud.reports import get_report, list_reports, update_report, upsert_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.put("", response_model=ReportRecordRead, status_code=status.HTTP_201_CREATED)
async def upsert_report_endpoint(
    payload: ReportRecordCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ReportRecordRead:
    report = await upsert_report(db, payload)
    return ReportRecordRead.model_validate(report)


@router.get("", response_model=list[ReportRecordRead])
async def list_reports_endpoint(
    limit: int = Query(default=20, ge=1, le=100),  # noqa: B008
    offset: int = Query(default=0, ge=0),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[ReportRecordRead]:
    reports = await list_reports(db, limit=limit, offset=offset)
    return [ReportRecordRead.model_validate(report) for report in reports]


@router.get("/{task_id}", response_model=ReportRecordRead)
async def get_report_endpoint(
    task_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ReportRecordRead:
    report = await get_report(db, task_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return ReportRecordRead.model_validate(report)


@router.patch("/{task_id}", response_model=ReportRecordRead)
async def update_report_endpoint(
    task_id: str,
    payload: ReportRecordUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ReportRecordRead:
    report = await get_report(db, task_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    updated = await update_report(db, report, payload)
    return ReportRecordRead.model_validate(updated)
