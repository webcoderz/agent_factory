"""Async guardrail middleware — run guardrails concurrently with LLM calls.

When the guardrail detects a violation while the LLM is still generating,
the request is short-circuited to save time and API costs.

Timing modes:
- BLOCKING: traditional — guardrail completes before LLM starts
- CONCURRENT: guardrail and LLM run in parallel, fail-fast on violation
- ASYNC_POST: guardrail runs after LLM (monitoring only)
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from agent_ext.run_context import RunContext

from .base import AgentMiddleware
from .exceptions import GuardrailTimeout, InputBlocked
from .strategies import GuardrailTiming

logger = logging.getLogger(__name__)


class AsyncGuardrailMiddleware(AgentMiddleware):
    """Run guardrails concurrently with LLM calls for improved latency.

    Example::

        guardrail = AsyncGuardrailMiddleware(
            guardrail=PolicyViolationDetector(),
            timing=GuardrailTiming.CONCURRENT,
            cancel_on_failure=True,
        )
    """

    def __init__(
        self,
        guardrail: AgentMiddleware,
        timing: GuardrailTiming = GuardrailTiming.CONCURRENT,
        cancel_on_failure: bool = True,
        timeout: float | None = None,
        name: str | None = None,
    ) -> None:
        self.guardrail = guardrail
        self.timing = timing
        self.cancel_on_failure = cancel_on_failure
        self._timeout = timeout
        self._name = name or f"AsyncGuardrail({type(guardrail).__name__})"
        # State for concurrent execution
        self._guardrail_task: asyncio.Task[Any] | None = None
        self._guardrail_error: Exception | None = None

    @property
    def name(self) -> str:
        return self._name

    async def before_run(self, ctx: RunContext, prompt: str | Sequence[Any]) -> str | Sequence[Any]:
        if self.timing == GuardrailTiming.BLOCKING:
            # Traditional: guardrail must pass before LLM starts
            return await self._run_guardrail_check(ctx, prompt)
        elif self.timing == GuardrailTiming.CONCURRENT:
            # Launch guardrail in background; it will raise if it fails
            self._guardrail_error = None
            self._guardrail_task = asyncio.create_task(
                self._run_guardrail_background(ctx, prompt)
            )
            return prompt
        else:
            # ASYNC_POST: do nothing before run
            return prompt

    async def after_run(self, ctx: RunContext, prompt: str | Sequence[Any], output: Any) -> Any:
        if self.timing == GuardrailTiming.CONCURRENT:
            # Wait for background guardrail to complete
            if self._guardrail_task is not None:
                try:
                    if self._timeout:
                        await asyncio.wait_for(self._guardrail_task, timeout=self._timeout)
                    else:
                        await self._guardrail_task
                except asyncio.TimeoutError:
                    raise GuardrailTimeout(self._name, self._timeout or 0.0)
                except InputBlocked:
                    raise  # Re-raise — guardrail blocked the input
                finally:
                    self._guardrail_task = None

            if self._guardrail_error is not None:
                raise self._guardrail_error

        elif self.timing == GuardrailTiming.ASYNC_POST:
            # Run guardrail after LLM, non-blocking (monitoring)
            try:
                await self._run_guardrail_check(ctx, prompt)
            except InputBlocked as e:
                logger.warning(f"Post-run guardrail violation: {e}")
                # Don't raise — ASYNC_POST is non-blocking

        return output

    async def _run_guardrail_check(
        self, ctx: RunContext, prompt: str | Sequence[Any]
    ) -> str | Sequence[Any]:
        """Run guardrail synchronously (blocking)."""
        if self._timeout:
            try:
                return await asyncio.wait_for(
                    self.guardrail.before_run(ctx, prompt),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                raise GuardrailTimeout(self._name, self._timeout)
        return await self.guardrail.before_run(ctx, prompt)

    async def _run_guardrail_background(
        self, ctx: RunContext, prompt: str | Sequence[Any]
    ) -> None:
        """Run guardrail in background for concurrent mode."""
        try:
            await self.guardrail.before_run(ctx, prompt)
        except InputBlocked as e:
            self._guardrail_error = e
            if self.cancel_on_failure:
                raise  # Propagate to cancel concurrent operations
        except Exception as e:
            self._guardrail_error = e
            logger.error(f"Guardrail error: {e}")
