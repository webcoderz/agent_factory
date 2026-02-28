from __future__ import annotations

import asyncio
import builtins
import re
from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .parallel import gather_bounded


@dataclass
class SubagentResult:
    ok: bool
    name: str
    output: Any
    meta: dict[str, Any]


class Subagent(Protocol):
    name: str

    async def run(self, ctx, *, input: Any, meta: dict[str, Any]) -> SubagentResult: ...


class SubagentRegistry:
    def __init__(self):
        self._agents: dict[str, Subagent] = {}

    def register(self, agent: Subagent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> Subagent:
        if name not in self._agents:
            raise KeyError(f"Unknown subagent: {name}")
        return self._agents[name]

    def list(self) -> builtins.list[str]:
        return sorted(self._agents.keys())


class SubagentOrchestrator:
    def __init__(self, registry: SubagentRegistry):
        self.registry = registry

    async def run_many(
        self,
        ctx,
        calls: list[tuple[str, Any, dict[str, Any]]],
        *,
        max_concurrency: int = 4,
    ) -> list[SubagentResult]:
        coros: list[Awaitable[SubagentResult]] = []
        for name, inp, meta in calls:
            agent = self.registry.get(name)
            coros.append(agent.run(ctx, input=inp, meta=meta))
        return await gather_bounded(coros, max_concurrency=max_concurrency)


# ----------------------------
# Built-in starter subagents
# ----------------------------


class RepoGrepSubagent:
    """
    Deterministic: searches repo for keywords/regex. Cheap. Great parallel companion.
    """

    name = "repo_grep"

    async def run(self, ctx, *, input: Any, meta: dict[str, Any]) -> SubagentResult:
        query = str(input).strip()
        root = Path(meta.get("root", "."))
        pattern = meta.get("regex", False)

        hits: list[dict] = []
        rx = re.compile(query) if pattern else None

        # small async yield to keep loop responsive
        await asyncio.sleep(0)

        for path in root.rglob("*.py"):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            if rx:
                if rx.search(text):
                    hits.append({"file": str(path)})
            else:
                if query in text:
                    hits.append({"file": str(path)})

            if len(hits) >= int(meta.get("limit", 25)):
                break

        return SubagentResult(ok=True, name=self.name, output=hits, meta={"query": query, "count": len(hits)})


def _default_plan(goal: str) -> list[dict[str, Any]]:
    """Fallback when no model or LLM plan fails: fixed sequence."""
    return [
        {"kind": "analyze", "title": "Clarify goal", "input": goal},
        {"kind": "search", "title": "Search repo for relevant modules", "input": goal},
        {"kind": "design", "title": "Propose approach + file changes", "input": goal},
        {"kind": "implement", "title": "Create patch", "input": goal},
        {"kind": "gates", "title": "Run gates/tests", "input": {"pytest": []}},
    ]


class PlannerSubagent:
    """
    Dynamic planner: when ctx.model is set, uses LLM with structured output to
    choose task sequence (e.g. skip analyze for small edits, add multiple searches).
    Falls back to a fixed plan when no model or validation fails.
    """

    name = "planner"

    async def run(self, ctx, *, input: Any, meta: dict[str, Any]) -> SubagentResult:
        goal = str(input).strip()
        if not goal:
            return SubagentResult(ok=True, name=self.name, output=[], meta={"goal": goal, "count": 0})

        if getattr(ctx, "model", None) is not None:
            try:
                from pydantic_ai import Agent

                from .plan_models import PlanOutput, plan_output_to_tasks

                prompt = f"""Given this development goal, output a minimal ordered plan of tasks.

GOAL: {goal}

Available task kinds (use only these):
- analyze: clarify the goal into a short spec (use when the goal is vague or large).
- search: find relevant code; input = search query (can be more specific than the goal).
- design: propose approach and which files to change (use when multiple files or non-obvious approach).
- implement: create the code patch (always include if the goal involves code changes).
- gates: run compile/import checks and optional tests (include at the end when code was changed).

Rules:
- Prefer fewer tasks when the goal is small (e.g. "fix typo in README" → search + implement + gates).
- For large or vague goals start with analyze, then search, then design, then implement, then gates.
- You may use multiple search tasks with different queries if needed.
- Every plan that changes code should end with implement and then gates.
- Return JSON only: {{"tasks": [{{"kind": "...", "title": "...", "input": "..."}}, ...]}}."""

                async with ctx.model_limiter:
                    agent = Agent(model=ctx.model, output_type=PlanOutput)
                    result = await agent.run(prompt)
                plan: PlanOutput = result.output
                tasks = plan_output_to_tasks(plan)
                if not tasks:
                    tasks = _default_plan(goal)
                return SubagentResult(
                    ok=True,
                    name=self.name,
                    output=tasks,
                    meta={"goal": goal, "count": len(tasks), "dynamic": True},
                )
            except Exception:
                tasks = _default_plan(goal)
                return SubagentResult(
                    ok=True,
                    name=self.name,
                    output=tasks,
                    meta={"goal": goal, "count": len(tasks), "dynamic": False, "fallback": True},
                )

        tasks = _default_plan(goal)
        return SubagentResult(ok=True, name=self.name, output=tasks, meta={"goal": goal, "count": len(tasks)})
