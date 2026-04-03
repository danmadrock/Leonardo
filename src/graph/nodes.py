from __future__ import annotations

from collections.abc import Awaitable, Callable

from src.agents.analysis import AnalysisAgent
from src.agents.planner import PlannerAgent
from src.agents.report import ReportAgent
from src.agents.search import SearchAgent
from src.db.session import SessionLocal
from src.graph.state import ResearchState
from src.llm import get_llm

NodeFn = Callable[[ResearchState], Awaitable[dict]]

_llm = get_llm()
_planner_agent = PlannerAgent(_llm)
_search_agent = SearchAgent(_llm, db_session_factory=SessionLocal)
_analysis_agent = AnalysisAgent(_llm)
_report_agent = ReportAgent(_llm)


async def planner_node(state: ResearchState) -> dict:
    """Run the planner agent and mark state stage."""
    update = await _planner_agent.run(state)
    update["stage"] = "planning"
    return update


async def search_node(state: ResearchState) -> dict:
    """Run the search agent and mark state stage."""
    update = await _search_agent.run(state)
    update["stage"] = "search"
    return update


async def analysis_node(state: ResearchState) -> dict:
    """Run the analysis agent and mark state stage."""
    update = await _analysis_agent.run(state)
    update["stage"] = "analysis"
    return update


async def report_node(state: ResearchState) -> dict:
    """Run the report agent and mark state stage."""
    update = await _report_agent.run(state)
    update["stage"] = "report"
    return update


__all__ = [
    "NodeFn",
    "analysis_node",
    "planner_node",
    "report_node",
    "search_node",
]
