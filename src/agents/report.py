from __future__ import annotations

from src.agents.base import BaseAgent
from src.agents.models import Finding, Report, ReportBody
from src.graph.state import ResearchState
from src.llm.base import Message
from src.sources.models import PaperRef


class ReportAgent(BaseAgent):
    async def run(self, state: ResearchState) -> dict:
        findings: list[Finding] = state["findings"]
        sources = self._dedupe_sources([finding.source_paper for finding in findings])

        messages: list[Message] = [
            {
                "role": "system",
                "content": (
                    "You are Leonardo's report writer. "
                    "Produce concise scientific synthesis from findings."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Query: {state['query']}\\n"
                    f"Findings count: {len(findings)}\\n"
                    "Write executive summary, methodology overview, and research gaps."
                ),
            },
        ]
        report_body = await self.llm.complete(messages, response_model=ReportBody)
        assert isinstance(report_body, ReportBody)
        markdown = self._render_markdown(
            query=state["query"],
            executive_summary=report_body.executive_summary,
            findings=findings,
            methodology_overview=report_body.methodology_overview,
            identified_gaps=report_body.identified_gaps,
            sources=sources,
        )
        report = Report(
            executive_summary=report_body.executive_summary,
            key_findings=findings,
            methodology_overview=report_body.methodology_overview,
            identified_gaps=report_body.identified_gaps,
            sources=sources,
            raw_markdown=markdown,
        )
        return {"report": report}

    @staticmethod
    def _dedupe_sources(sources: list[PaperRef]) -> list[PaperRef]:
        seen: set[tuple[str, str | None, str | None]] = set()
        unique: list[PaperRef] = []
        for source in sources:
            key = (source.title.strip().lower(), source.doi, source.arxiv_id)
            if key in seen:
                continue
            seen.add(key)
            unique.append(source)
        return unique

    @staticmethod
    def _citation(source: PaperRef) -> str:
        if source.doi:
            return f"doi:{source.doi}"
        if source.arxiv_id:
            return f"arXiv:{source.arxiv_id}"
        return source.url

    def _render_markdown(self, *, query: str, executive_summary: str, findings: list[Finding], methodology_overview: str, identified_gaps: list[str], sources: list[PaperRef]) -> str:
        lines = [
            f"# Research Report: {query}",
            "",
            "## Executive Summary",
            executive_summary,
            "",
            "## Key Findings",
        ]

        for idx, finding in enumerate(findings, start=1):
            cite = self._citation(finding.source_paper)
            lines.extend(
                [
                    f"### Finding {idx} [{cite}]",
                    f"- Claim: {finding.claim}",
                    f"- Methodology: {finding.methodology}",
                    f"- Limitations: {finding.limitations}",
                    f"- Relevance: {finding.relevance:.2f}",
                    "",
                ]
            )

        lines.extend(["## Methodology Overview", methodology_overview, "", "## Research Gaps"])
        if identified_gaps:
            lines.extend([f"- {gap}" for gap in identified_gaps])
        else:
            lines.append("- No explicit gaps identified.")

        lines.extend(["", "## Sources"])
        for source in sources:
            lines.append(f"- {source.title} — {self._citation(source)}")

        return "\n".join(lines)