from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from .subagents import SubagentResult


async def plan_and_queue(ctx, user_goal: str) -> List[str]:
    """
    Uses planner subagent to generate tasks, then enqueues them.
    """
    planner = ctx.subagents.get("planner")
    res = await planner.run(ctx, input=user_goal, meta={})
    if not res.ok:
        return [f"planner failed: {res.output}"]

    tasks = res.output
    lines = []
    for t in tasks:
        ctx.task_queue.add(t["kind"], t["title"], t["input"])
        lines.append(f"queued: {t['kind']} - {t['title']}")
    return lines


async def run_next_task(ctx) -> str:
    """
    Executes a single pending task. For now, only implements:
    - search: uses repo_grep
    - analyze/design: placeholder
    - implement: placeholder (tomorrow we wire LLM patch gen + self_improve controller)
    - gates: placeholder
    """
    t = ctx.task_queue.next_pending()
    if not t:
        return "no pending tasks"

    t.status = "in_progress"

    try:
        if t.kind == "search":
            # Run repo_grep + (optional) more deterministic scanners in parallel
            calls = [
                ("repo_grep", str(t.input), {"root": ".", "limit": 25, "regex": False}),
            ]
            results: List[SubagentResult] = await ctx.orchestrator.run_many(
                ctx,
                calls,
                max_concurrency=ctx.max_parallel_subagents,
            )
            t.status = "done"
            return f"{t.id} done: search\n" + "\n".join([f"- {r.name}: {r.meta.get('count')} hits" for r in results])

        # Stubbed tasks (tomorrow: wire actual agents)
        t.status = "done"
        return f"{t.id} done: {t.kind} (stub)"

    except Exception as e:
        t.status = "failed"
        return f"{t.id} failed: {e!r}"
