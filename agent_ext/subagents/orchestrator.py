from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Tuple

from .base import SubagentResult
from .registry import SubagentRegistry
from ...types import RunContext


class SubagentOrchestrator:
    def __init__(self, registry: SubagentRegistry):
        self.registry = registry

    async def run_many(
        self,
        ctx: RunContext,
        requests: List[Tuple[str, Any, Dict[str, Any]]],
        *,
        timeout_s: int = 60,
    ) -> Dict[str, SubagentResult]:
        """
        requests: [(subagent_name, input, metadata), ...]
        returns dict keyed by subagent_name (last write wins)
        """
        async def _one(name: str, inp: Any, meta: Dict[str, Any]) -> tuple[str, SubagentResult]:
            agent = self.registry.get(name)
            ctx.logger.info("subagent.start", name=name, trace_id=ctx.trace_id)
            try:
                res = await agent.run(input=inp, metadata=meta)
            except Exception as e:
                res = SubagentResult(ok=False, error=str(e), output=None)
            ctx.logger.info("subagent.end", name=name, ok=res.ok, trace_id=ctx.trace_id)
            return name, res

        tasks = [asyncio.create_task(_one(n, i, m)) for (n, i, m) in requests]
        done, pending = await asyncio.wait(tasks, timeout=timeout_s)
        for p in pending:
            p.cancel()

        out: Dict[str, SubagentResult] = {}
        for d in done:
            k, v = await d
            out[k] = v
        return out
