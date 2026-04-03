from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.config import settings

if TYPE_CHECKING:
    from src.graph.state import ResearchState

MIN_FINDINGS_THRESHOLD = 3


def route_after_analysis(state: ResearchState) -> str:
    """Iterative deepening: loop back to search if coverage is still thin."""
    search_iteration = state.get("search_iteration", 0)
    max_iterations = state.get("max_search_iterations", settings.MAX_SEARCH_ITERATIONS)
    findings = state.get("findings", [])
    papers = state.get("papers", [])

    if search_iteration >= max_iterations:
        return "report"
    if not papers:
        return "search"
    if len(findings) < MIN_FINDINGS_THRESHOLD:
        return "search"
    return "report"


__all__ = ["route_after_analysis"]
