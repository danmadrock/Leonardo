from __future__ import annotations

import asyncio

from src.agents.base import BaseAgent
from src.agents.models import Finding
from src.core.config import settings
from src.graph.state import ResearchState
from src.llm.base import Message
from src.sources.models import Paper, PaperRef

_ANALYSIS_SYSTEM_PROMPT = (
    "You are Leonardo's scientific analysis agent. "
    "Extract only evidence-backed findings from papers and score relevance to the query."
)


class AnalysisAgent(BaseAgent):
    async def run(self, state: ResearchState) -> dict:
        papers = state["papers"]
        findings: list[Finding] = []
        for i in range(0, len(papers), settings.ANALYSIS_BATCH_SIZE):
            batch = papers[i : i + settings.ANALYSIS_BATCH_SIZE]
            batch_findings = await self._analyze_batch(state["query"], batch)
            for finding in batch_findings:
                if finding.relevance >= settings.MIN_FINDING_RELEVANCE:
                    findings.append(finding)
        return {"findings": findings}

    async def _analyze_batch(self, query: str, papers: list[Paper]) -> list[Finding]:
        tasks = [self._analyze_single(query, paper) for paper in papers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        findings: list[Finding] = []
        for result in results:
            if isinstance(result, BaseException) or result is None:
                continue
            findings.append(result)
        return findings

    async def _analyze_single(self, query: str, paper: Paper) -> Finding:
        messages: list[Message] = [
            {"role": "system", "content": _ANALYSIS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Original query: {query}\\n"
                    f"Paper title: {paper.title}\\n"
                    f"Paper abstract: {paper.abstract}\\n"
                    "Return one finding grounded in this paper only. "
                    "If the paper is irrelevant, set relevance below 0.3."
                ),
            },
        ]
        output = await self.llm.complete(messages, response_model=Finding)
        assert isinstance(output, Finding)
        if not output.source_paper.title:
            output.source_paper = PaperRef(
                title=paper.title,
                url=paper.url,
                doi=paper.doi,
                arxiv_id=paper.arxiv_id,
            )
        return output