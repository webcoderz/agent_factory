"""Cost tracking middleware — automatic token usage and USD cost monitoring.

Tracks token usage across agent runs, calculates costs, supports callbacks
for real-time UI updates, and enforces budget limits.
"""
from __future__ import annotations

import inspect
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Union

from agent_ext.run_context import RunContext

from .base import AgentMiddleware
from .exceptions import BudgetExceededError

CostCallback = Union[Callable[["CostInfo"], Any], None]


@dataclass
class CostInfo:
    """Per-run and cumulative cost information.

    Attributes:
        run_cost_usd: USD cost of this run (``None`` if model unknown).
        total_cost_usd: Cumulative USD cost.
        run_request_tokens: Input tokens this run.
        run_response_tokens: Output tokens this run.
        total_request_tokens: Cumulative input tokens.
        total_response_tokens: Cumulative output tokens.
        run_count: Number of completed runs.
    """

    run_cost_usd: float | None
    total_cost_usd: float | None
    run_request_tokens: int
    run_response_tokens: int
    total_request_tokens: int
    total_response_tokens: int
    run_count: int


class CostTrackingMiddleware(AgentMiddleware):
    """Middleware that accumulates token counts and USD cost.

    Args:
        model_name: Model id for cost calculation (e.g. ``"openai:gpt-4o"``).
            ``None`` disables USD costing (tokens still tracked).
        budget_limit_usd: Max cumulative USD (``None`` = unlimited).
        on_cost_update: Callback after each run with a ``CostInfo``.
            Accepts sync or async callables.
        cost_per_1k_input: Manual $/1k input tokens (used when ``model_name`` is None).
        cost_per_1k_output: Manual $/1k output tokens.
    """

    def __init__(
        self,
        model_name: str | None = None,
        budget_limit_usd: float | None = None,
        on_cost_update: CostCallback = None,
        cost_per_1k_input: float = 0.0,
        cost_per_1k_output: float = 0.0,
    ) -> None:
        self.model_name = model_name
        self.budget_limit_usd = budget_limit_usd
        self.on_cost_update = on_cost_update
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output

        self._total_request_tokens: int = 0
        self._total_response_tokens: int = 0
        self._total_cost_usd: float = 0.0
        self._run_count: int = 0

    @property
    def total_cost(self) -> float:
        return self._total_cost_usd

    @property
    def total_request_tokens(self) -> int:
        return self._total_request_tokens

    @property
    def total_response_tokens(self) -> int:
        return self._total_response_tokens

    @property
    def run_count(self) -> int:
        return self._run_count

    def reset(self) -> None:
        self._total_request_tokens = 0
        self._total_response_tokens = 0
        self._total_cost_usd = 0.0
        self._run_count = 0

    async def before_run(self, ctx: RunContext, prompt: str | Sequence[Any]) -> str | Sequence[Any]:
        if self.budget_limit_usd is not None and self._total_cost_usd >= self.budget_limit_usd:
            raise BudgetExceededError(self._total_cost_usd, self.budget_limit_usd)
        return prompt

    async def after_run(self, ctx: RunContext, prompt: str | Sequence[Any], output: Any) -> Any:
        # Extract usage from ctx.tags (set by the agent runner)
        run_req = int(ctx.tags.get("run_request_tokens", 0))
        run_resp = int(ctx.tags.get("run_response_tokens", 0))

        self._total_request_tokens += run_req
        self._total_response_tokens += run_resp
        self._run_count += 1

        run_cost = self._calc_cost(run_req, run_resp)
        if run_cost is not None:
            self._total_cost_usd += run_cost

        total_cost = self._total_cost_usd if (self.model_name or self.cost_per_1k_input) else None

        info = CostInfo(
            run_cost_usd=run_cost,
            total_cost_usd=total_cost,
            run_request_tokens=run_req,
            run_response_tokens=run_resp,
            total_request_tokens=self._total_request_tokens,
            total_response_tokens=self._total_response_tokens,
            run_count=self._run_count,
        )
        await self._notify(info)
        return output

    def _calc_cost(self, input_tokens: int, output_tokens: int) -> float | None:
        """Calculate USD cost.  Uses genai-prices when available, else manual rates."""
        if self.model_name:
            try:
                from genai_prices import calc_price  # type: ignore[import-untyped]

                provider_id: str | None = None
                model_ref = self.model_name
                if ":" in self.model_name:
                    parts = self.model_name.split(":", 1)
                    provider_id, model_ref = parts[0], parts[1]

                # Build a minimal usage-like object
                class _Usage:
                    def __init__(self, inp, out):
                        self.input_tokens = inp
                        self.output_tokens = out

                result = calc_price(_Usage(input_tokens, output_tokens), model_ref, provider_id=provider_id)
                return float(result.total_price)
            except Exception:
                pass  # fall through to manual

        if self.cost_per_1k_input or self.cost_per_1k_output:
            return (input_tokens / 1000.0) * self.cost_per_1k_input + (output_tokens / 1000.0) * self.cost_per_1k_output
        return None

    async def _notify(self, info: CostInfo) -> None:
        if self.on_cost_update is None:
            return
        result = self.on_cost_update(info)
        if inspect.isawaitable(result):
            await result


def create_cost_tracking_middleware(
    model_name: str | None = None,
    budget_limit_usd: float | None = None,
    on_cost_update: CostCallback = None,
    cost_per_1k_input: float = 0.0,
    cost_per_1k_output: float = 0.0,
) -> CostTrackingMiddleware:
    """Convenience factory."""
    return CostTrackingMiddleware(
        model_name=model_name,
        budget_limit_usd=budget_limit_usd,
        on_cost_update=on_cost_update,
        cost_per_1k_input=cost_per_1k_input,
        cost_per_1k_output=cost_per_1k_output,
    )
