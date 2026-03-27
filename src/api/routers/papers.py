from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.api.schemas import PaperCreate, PaperRead, PaperUpdate
from src.crud.papers import create_paper, delete_paper, get_paper, list_papers, update_paper

router = APIRouter(prefix="/papers", tags=["papers"])


def _to_read_model(paper: object) -> PaperRead:
    data = PaperRead.model_validate(paper)
    data.metadata = paper.metadata_json  # type: ignore[attr-defined]
    return data


@router.post("", response_model=PaperRead, status_code=status.HTTP_201_CREATED)
async def create_paper_endpoint(
    payload: PaperCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaperRead:
    paper = await create_paper(db, payload)
    return _to_read_model(paper)


@router.get("", response_model=list[PaperRead])
async def list_papers_endpoint(
    limit: int = Query(default=20, ge=1, le=100),  # noqa: B008
    offset: int = Query(default=0, ge=0),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[PaperRead]:
    papers = await list_papers(db, limit=limit, offset=offset)
    return [_to_read_model(paper) for paper in papers]


@router.get("/{paper_id}", response_model=PaperRead)
async def get_paper_endpoint(
    paper_id: int,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaperRead:
    paper = await get_paper(db, paper_id)
    if paper is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")
    return _to_read_model(paper)


@router.patch("/{paper_id}", response_model=PaperRead)
async def update_paper_endpoint(
    paper_id: int,
    payload: PaperUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaperRead:
    paper = await get_paper(db, paper_id)
    if paper is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")

    updated = await update_paper(db, paper, payload)
    return _to_read_model(updated)


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_paper_endpoint(
    paper_id: int,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> None:
    paper = await get_paper(db, paper_id)
    if paper is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")
    await delete_paper(db, paper)
