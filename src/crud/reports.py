from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import ReportRecordCreate, ReportRecordUpdate
from src.models.report import ReportRecord


async def upsert_report(db: AsyncSession, payload: ReportRecordCreate) -> ReportRecord:
    report = await db.get(ReportRecord, payload.task_id)
    if report is None:
        report = ReportRecord(**payload.model_dump())
        db.add(report)
    else:
        report.markdown = payload.markdown
        report.structured_report_json = payload.structured_report_json

    await db.commit()
    await db.refresh(report)
    return report


async def get_report(db: AsyncSession, task_id: str) -> ReportRecord | None:
    return await db.get(ReportRecord, task_id)


async def list_reports(
    db: AsyncSession, limit: int = 20, offset: int = 0
) -> list[ReportRecord]:
    result = await db.execute(
        select(ReportRecord)
        .order_by(ReportRecord.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def update_report(
    db: AsyncSession,
    report: ReportRecord,
    payload: ReportRecordUpdate,
) -> ReportRecord:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(report, key, value)

    await db.commit()
    await db.refresh(report)
    return report


async def delete_report(db: AsyncSession, report: ReportRecord) -> None:
    await db.delete(report)
    await db.commit()
