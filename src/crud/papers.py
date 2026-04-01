from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import PaperCreate, PaperUpdate
from src.models.paper import PaperRecord


async def create_paper(db: AsyncSession, payload: PaperCreate) -> PaperRecord:
    paper = PaperRecord(
        title=payload.title,
        abstract=payload.abstract,
        url=str(payload.url),
        source=payload.source,
        authors=payload.authors,
        year=payload.year,
        doi=payload.doi,
        arxiv_id=payload.arxiv_id,
        citation_count=payload.citation_count,
        venue=payload.venue,
        metadata_json=payload.metadata,
    )
    db.add(paper)
    await db.commit()
    await db.refresh(paper)
    return paper


async def get_paper_by_identity(db: AsyncSession, *, doi: str | None, arxiv_id: str | None, title: str) -> PaperRecord | None:
    clauses = [func.lower(PaperRecord.title) == title.strip().lower()]
    if doi:
        clauses.append(func.lower(PaperRecord.doi) == doi.strip().lower())
    if arxiv_id:
        clauses.append(func.lower(PaperRecord.arxiv_id) == arxiv_id.strip().lower())

    result = await db.execute(select(PaperRecord).where(or_(*clauses)).limit(1))
    return result.scalar_one_or_none()


async def create_paper_if_missing(db: AsyncSession, payload: PaperCreate) -> PaperRecord:
    existing = await get_paper_by_identity(
        db,
        doi=payload.doi,
        arxiv_id=payload.arxiv_id,
        title=payload.title,
    )
    if existing is not None:
        return existing
    return await create_paper(db, payload)


async def list_papers(db: AsyncSession, limit: int = 20, offset: int = 0) -> list[PaperRecord]:
    result = await db.execute(
        select(PaperRecord).limit(limit).offset(offset).order_by(PaperRecord.id.desc())
    )
    return list(result.scalars().all())


async def get_paper(db: AsyncSession, paper_id: int) -> PaperRecord | None:
    return await db.get(PaperRecord, paper_id)


async def update_paper(db: AsyncSession, paper: PaperRecord, payload: PaperUpdate) -> PaperRecord:
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "metadata":
            paper.metadata_json = value
            continue
        if key == "url" and value is not None:
            setattr(paper, key, str(value))
            continue
        setattr(paper, key, value)

    await db.commit()
    await db.refresh(paper)
    return paper


async def delete_paper(db: AsyncSession, paper: PaperRecord) -> None:
    await db.delete(paper)
    await db.commit()
