from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol

from .parallel import gather_bounded


@dataclass
class SubagentResult:
    ok: bool
    name: str
    output: Any
    meta: Dict[str, Any]


class Subagent(Protocol):
    name: str
    async def run(self, ctx, *, input: Any, meta: Dict[str, Any]) -> SubagentResult: ...


class SubagentRegistry:
    def __init__(self):
        self._agents: Dict[str, Subagent] = {}

    def register(self, agent: Subagent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> Subagent:
        if name not in self._agents:
            raise KeyError(f"Unknown subagent: {name}")
        return self._agents[name]

    def list(self) -> List[str]:
        return sorted(self._agents.keys())


class SubagentOrchestrator:
    def __init__(self, registry: SubagentRegistry):
        self.registry = registry

    async def run_many(
        self,
        ctx,
        calls: List[tuple[str, Any, Dict[str, Any]]],
        *,
        max_concurrency: int = 4,
    ) -> List[SubagentResult]:
        coros: List[Awaitable[SubagentResult]] = []
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

    async def run(self, ctx, *, input: Any, meta: Dict[str, Any]) -> SubagentResult:
        query = str(input).strip()
        root = Path(meta.get("root", "."))
        pattern = meta.get("regex", False)

        hits: List[dict] = []
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


class PlannerSubagent:
    """
    Cheap planner: turns a user goal into a task list.
    Deterministic starter; later you can swap with an LLM planner.
    """
    name = "planner"

    async def run(self, ctx, *, input: Any, meta: Dict[str, Any]) -> SubagentResult:
        goal = str(input).strip()
        tasks = []

        # quick heuristic plan
        tasks.append({"kind": "analyze", "title": "Clarify goal", "input": goal})
        tasks.append({"kind": "search", "title": "Search repo for relevant modules", "input": goal})
        tasks.append({"kind": "design", "title": "Propose approach + file changes", "input": goal})
        tasks.append({"kind": "implement", "title": "Create patch", "input": goal})
        tasks.append({"kind": "gates", "title": "Run gates/tests", "input": {"pytest": []}})

        return SubagentResult(ok=True, name=self.name, output=tasks, meta={"goal": goal, "count": len(tasks)})
