from pydantic import BaseModel, Field
from src.sources.models import PaperRef


class PlannerOutput(BaseModel):
    subtasks: list[str] = Field(
        description="List of 3-5 independent search angles for the research query.",
        min_length=2,
        max_length=6,
    )
    reasoning: str = Field(description="Brief explanation of the decomposition strategy.")


class Finding(BaseModel):
    claim: str = Field(description="The core scientific claim or contribution.")
    methodology: str = Field(description="How the result was obtained.")
    limitations: str = Field(description="Acknowledged limitations or scope.")
    relevance: float = Field(ge=0.0, le=1.0, description="Relevance to the original query.")
    source_paper: PaperRef


class Report(BaseModel):
    executive_summary: str
    key_findings: list[Finding]
    methodology_overview: str
    identified_gaps: list[str]
    sources: list[PaperRef]
    raw_markdown: str