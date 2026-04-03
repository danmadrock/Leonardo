from __future__ import annotations

from src.agents.base import BaseAgent
from src.agents.models import PlannerOutput
from src.graph.state import ResearchState
from src.llm.base import Message

_PLANNER_SYSTEM_PROMPT = (
    "You are Leonardo's planning agent. "
    "Decompose a scientific research question into independent search subtasks. "
    "Return exactly 3 to 5 concise subtasks with no overlap. "
    "Subtasks must be search-ready and include core keywords."
)


class PlannerAgent(BaseAgent):
    async def run(self, state: ResearchState) -> dict:
        query = state["query"].strip()
        messages: list[Message] = [
            {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Create subtasks for this query.\\n"
                    "Rules:\\n"
                    "1) Output 3-5 subtasks only.\\n"
                    "2) Each subtask must target a different angle.\\n"
                    "3) Keep each subtask under 120 characters.\\n"
                    f"Query: {query}"
                ),
            },
        ]

        output = await self.llm.complete(messages, response_model=PlannerOutput)
        assert isinstance(output, PlannerOutput)

        subtasks = [task.strip() for task in output.subtasks if task.strip()]
        return {"subtasks": subtasks}
