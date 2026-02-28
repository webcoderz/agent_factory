from __future__ import annotations

from collections.abc import Callable

from agent_ext.research.models import ResearchPlan, ResearchTask


def default_plan(question: str) -> ResearchPlan:
    """
    Deterministic starter plan. Good enough to run without an LLM.
    You can replace with an LLM planner later.
    """
    tasks: list[ResearchTask] = [
        ResearchTask(
            id="t1_scope",
            kind="analyze",
            goal="Clarify the question, define success criteria, and list sub-questions.",
            inputs={"question": question},
            priority=5,
            tags=["plan"],
        ),
        ResearchTask(
            id="t2_collect",
            kind="search",
            goal="Collect initial evidence and citations relevant to the question.",
            query=question,
            priority=10,
            tags=["collect"],
        ),
        ResearchTask(
            id="t3_synthesize",
            kind="synthesize",
            goal="Synthesize evidence into claims with citations and produce a final answer with limitations.",
            priority=90,
            tags=["synthesize"],
            depends_on=["t1_scope", "t2_collect"],
        ),
    ]
    return ResearchPlan(
        question=question,
        tasks=tasks,
        assumptions=[],
        stop_conditions=[
            "Enough cited evidence exists for key claims",
            "No major gaps remain",
            "Budget exhausted",
        ],
    )


class ResearchPlanner:
    """
    Planner with an optional LLM-based planning seam:
    plan_fn(question) -> ResearchPlan
    """

    def __init__(self, plan_fn: Callable[[str], ResearchPlan] | None = None):
        self.plan_fn = plan_fn or default_plan

    def make_plan(self, question: str) -> ResearchPlan:
        return self.plan_fn(question)
