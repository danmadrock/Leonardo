from __future__ import annotations

from src.graph.edges import route_after_analysis
from src.graph.state import ResearchState


def test_route_loops_when_findings_too_low() -> None:
    state: ResearchState = {
        "task_id": "t1",
        "query": "q",
        "requested_sources": [],
        "max_papers": 5,
        "max_search_iterations": 3,
        "subtasks": [],
        "papers": [],
        "findings": [],
        "report": None,
        "search_iteration": 1,
        "status": "running",
        "stage": "analysis",
        "error": None,
    }
    assert route_after_analysis(state) == "search"


def test_route_finishes_when_max_iteration_hit() -> None:
    state: ResearchState = {
        "task_id": "t1",
        "query": "q",
        "requested_sources": [],
        "max_papers": 5,
        "max_search_iterations": 3,
        "subtasks": [],
        "papers": [],
        "findings": [],
        "report": None,
        "search_iteration": 3,
        "status": "running",
        "stage": "analysis",
        "error": None,
    }
    assert route_after_analysis(state) == "report"
