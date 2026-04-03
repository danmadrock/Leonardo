from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.graph.edges import route_after_analysis
from src.graph.nodes import analysis_node, planner_node, report_node, search_node
from src.graph.state import ResearchState


def build_graph():
    """Compile the research workflow graph."""
    builder = StateGraph(ResearchState)

    builder.add_node("planner", planner_node)
    builder.add_node("search", search_node)
    builder.add_node("analysis", analysis_node)
    builder.add_node("report", report_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "search")
    builder.add_edge("search", "analysis")
    builder.add_conditional_edges(
        "analysis",
        route_after_analysis,
        {
            "search": "search",
            "report": "report",
        },
    )
    builder.add_edge("report", END)

    return builder.compile()


__all__ = ["build_graph"]