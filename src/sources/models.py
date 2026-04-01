from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PaperRef(BaseModel):
    title: str
    url: str
    doi: str | None = None
    arxiv_id: str | None = None


class Paper(BaseModel):
    title: str
    url: str
    source: str
    abstract: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    pdf_url: str | None = None
    citation_count: int | None = None
    venue: str | None = None
    keywords: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)