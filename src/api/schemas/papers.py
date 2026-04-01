from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class PaperCreate(BaseModel):
    title: str = Field(min_length=1, max_length=1000)
    abstract: str = ""
    url: HttpUrl
    source: str = Field(min_length=1, max_length=64)
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    citation_count: int | None = None
    venue: str | None = None
    metadata: dict = Field(default_factory=dict)


class PaperUpdate(BaseModel):
    title: str | None = None
    abstract: str | None = None
    url: HttpUrl | None = None
    authors: list[str] | None = None
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    citation_count: int | None = None
    venue: str | None = None
    metadata: dict | None = None


class PaperRead(BaseModel):
    id: int
    title: str
    abstract: str
    url: str
    source: str
    authors: list[str]
    year: int | None
    doi: str | None
    arxiv_id: str | None
    citation_count: int | None
    venue: str | None
    metadata: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
