"""Parallel middleware execution — run multiple middleware concurrently.

Useful when you have several independent checks (e.g. PII detection,
profanity filter, injection guard) that can all run at the same time.

Aggregation strategies control how results are combined:
- ALL_MUST_PASS: all must succeed (any failure fails the whole check)
- FIRST_WINS: first non-exception result is used
- MERGE: combine all results (for dict-like outputs)
"""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from enum import Enum
from typing import Any

from agent_ext.run_context import RunContext

from .base import AgentMiddleware
from .context import HookType, MiddlewareContext
from .exceptions import ParallelExecutionFailed
from .strategies import AggregationStrategy


class ParallelMiddleware(AgentMiddleware):
    """Execute multiple middleware concurrently.

    Example::

        parallel = ParallelMiddleware(
            middleware=[PIIDetector(), ProfanityFilter(), InjectionGuard()],
            strategy=AggregationStrategy.ALL_MUST_PASS,
        )
        chain = MiddlewareChain([parallel, LoggingMiddleware()])
    """

    def __init__(
        self,
        middleware: Sequence[AgentMiddleware],
        strategy: AggregationStrategy = AggregationStrategy.ALL_MUST_PASS,
        *,
        name: str | None = None,
    ) -> None:
        self._middleware = list(middleware)
        self.strategy = strategy
        self._name = name or f"Parallel({len(self._middleware)})"

    @property
    def name(self) -> str:
        return self._name

    # -- generic parallel runner --------------------------------------------

    async def _run_parallel(
        self,
        hook_name: str,
        coros: list,
        passthrough: Any,
    ) -> Any:
        """Run coroutines in parallel and aggregate per strategy."""
        results = await asyncio.gather(*coros, return_exceptions=True)

        errors = [r for r in results if isinstance(r, Exception)]
        successes = [r for r in results if not isinstance(r, Exception)]

        if self.strategy == AggregationStrategy.ALL_MUST_PASS:
            if errors:
                raise ParallelExecutionFailed(errors, successes)
            return passthrough  # all passed → use original

        if self.strategy == AggregationStrategy.FIRST_WINS:
            if successes:
                return successes[0]
            if errors:
                raise ParallelExecutionFailed(errors)
            return passthrough

        if self.strategy == AggregationStrategy.MERGE:
            # For dict-like outputs, merge all successes
            if not successes:
                if errors:
                    raise ParallelExecutionFailed(errors)
                return passthrough
            merged = passthrough
            for s in successes:
                if isinstance(s, dict) and isinstance(merged, dict):
                    merged = {**merged, **s}
                else:
                    merged = s  # last wins for non-dict
            return merged

        return passthrough

    # -- hooks (parallel dispatch) ------------------------------------------

    async def before_run(self, ctx: RunContext, prompt: str | Sequence[Any]) -> str | Sequence[Any]:
        coros = [mw.before_run(ctx, prompt) for mw in self._middleware]
        return await self._run_parallel("before_run", coros, prompt)

    async def after_run(self, ctx: RunContext, prompt: str | Sequence[Any], output: Any) -> Any:
        coros = [mw.after_run(ctx, prompt, output) for mw in self._middleware]
        return await self._run_parallel("after_run", coros, output)

    async def before_model_request(self, ctx: RunContext, messages: list[Any]) -> list[Any]:
        coros = [mw.before_model_request(ctx, messages) for mw in self._middleware]
        return await self._run_parallel("before_model_request", coros, messages)

    async def before_tool_call(
        self, ctx: RunContext, tool_name: str, tool_args: dict[str, Any]
    ) -> dict[str, Any]:
        applicable = [mw for mw in self._middleware if mw._should_handle_tool(tool_name)]
        if not applicable:
            return tool_args
        coros = [mw.before_tool_call(ctx, tool_name, tool_args) for mw in applicable]
        return await self._run_parallel("before_tool_call", coros, tool_args)

    async def after_tool_call(
        self, ctx: RunContext, tool_name: str, tool_args: dict[str, Any], result: Any
    ) -> Any:
        applicable = [mw for mw in self._middleware if mw._should_handle_tool(tool_name)]
        if not applicable:
            return result
        coros = [mw.after_tool_call(ctx, tool_name, tool_args, result) for mw in applicable]
        return await self._run_parallel("after_tool_call", coros, result)

    async def on_error(self, ctx: RunContext, error: Exception) -> Exception | None:
        coros = [mw.on_error(ctx, error) for mw in self._middleware]
        results = await asyncio.gather(*coros, return_exceptions=True)
        # Return first non-None, non-exception result
        for r in results:
            if r is not None and not isinstance(r, Exception):
                return r
        return None
