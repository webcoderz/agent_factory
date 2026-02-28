"""
Structured plan output: LLM returns a list of tasks (kind, title, input)
so planning is dynamic (e.g. skip analyze for small changes, add multiple searches).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TaskSpec(BaseModel):
    """One task in the plan. Kinds are executed by the workbench loop."""

    kind: Literal["analyze", "search", "design", "implement", "gates"] = Field(
        description="analyze=clarify goal, search=find relevant code, design=approach+file list, implement=create patch, gates=run tests"
    )
    title: str = Field(description="Short human-readable title for this step")
    input: str = Field(
        default="", description="Input for the task: usually the goal, or a specific search query for search tasks"
    )


class PlanOutput(BaseModel):
    """Dynamic plan: ordered list of tasks. Convert to queue with plan_and_queue."""

    tasks: list[TaskSpec] = Field(default_factory=list, description="Ordered list of tasks to run")


def plan_output_to_tasks(plan: PlanOutput) -> list[dict]:
    """Convert PlanOutput to the list of dicts expected by plan_and_queue (kind, title, input)."""
    out = []
    for t in plan.tasks:
        inp: str | dict = t.input
        if t.kind == "gates":
            inp = {"pytest": []}
        out.append({"kind": t.kind, "title": t.title, "input": inp})
    return out
