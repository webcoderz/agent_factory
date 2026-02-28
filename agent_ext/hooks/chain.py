"""Composable async middleware chains.

``MiddlewareChain`` groups multiple ``AgentMiddleware`` instances into a
reusable unit.  ``before_*`` hooks run in order, ``after_*`` / ``on_*``
hooks run in reverse order (onion model).  Chains can be nested —
adding a chain flattens it.

The legacy sync ``HookChain`` is preserved at the bottom of this file.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator, Sequence
from typing import Any, overload

from agent_ext.run_context import RunContext, ToolCall, ToolResult

from .base import AgentMiddleware, Hook
from .exceptions import MiddlewareTimeout
from .permissions import ToolPermissionResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _flatten(
    items: Sequence[AgentMiddleware | MiddlewareChain],
) -> list[AgentMiddleware]:
    flat: list[AgentMiddleware] = []
    for item in items:
        if isinstance(item, MiddlewareChain):
            flat.extend(item._middleware)
        elif isinstance(item, AgentMiddleware):
            flat.append(item)
        else:
            raise TypeError(f"Expected AgentMiddleware or MiddlewareChain, got {type(item).__name__}")
    return flat


async def _with_timeout(coro, timeout: float | None, mw_name: str, hook_name: str):
    """Run *coro* with optional timeout, raising ``MiddlewareTimeout`` on expiry."""
    if timeout is None:
        return await coro
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except TimeoutError as e:
        raise MiddlewareTimeout(mw_name, timeout, hook_name) from e


# ---------------------------------------------------------------------------
# Async MiddlewareChain (parity with pydantic-ai-middleware)
# ---------------------------------------------------------------------------


class MiddlewareChain(AgentMiddleware):
    """A composable, ordered chain of async middleware.

    Supports ``add``, ``insert``, ``remove``, ``replace``, ``pop``,
    ``clear``, ``copy``, ``+``, ``+=``, indexing, iteration, and ``len``.
    """

    def __init__(
        self,
        middleware: Sequence[AgentMiddleware | MiddlewareChain] | None = None,
        *,
        name: str | None = None,
    ) -> None:
        self._middleware: list[AgentMiddleware] = _flatten(middleware or [])
        self._name = name or f"MiddlewareChain({len(self._middleware)})"

    @property
    def name(self) -> str:
        return self._name

    @property
    def middleware(self) -> list[AgentMiddleware]:
        return list(self._middleware)

    # -- mutators -----------------------------------------------------------

    def add(self, mw: AgentMiddleware | MiddlewareChain) -> MiddlewareChain:
        if isinstance(mw, MiddlewareChain):
            self._middleware.extend(mw._middleware)
        elif isinstance(mw, AgentMiddleware):
            self._middleware.append(mw)
        else:
            raise TypeError(f"Expected AgentMiddleware or MiddlewareChain, got {type(mw).__name__}")
        return self

    def insert(self, index: int, mw: AgentMiddleware | MiddlewareChain) -> MiddlewareChain:
        if isinstance(mw, MiddlewareChain):
            self._middleware[index:index] = mw._middleware
        elif isinstance(mw, AgentMiddleware):
            self._middleware.insert(index, mw)
        else:
            raise TypeError(f"Expected AgentMiddleware or MiddlewareChain, got {type(mw).__name__}")
        return self

    def remove(self, mw: AgentMiddleware) -> MiddlewareChain:
        self._middleware.remove(mw)
        return self

    def pop(self, index: int = -1) -> AgentMiddleware:
        return self._middleware.pop(index)

    def replace(self, old: AgentMiddleware, new: AgentMiddleware | MiddlewareChain) -> MiddlewareChain:
        idx = self._middleware.index(old)
        if isinstance(new, MiddlewareChain):
            self._middleware[idx : idx + 1] = new._middleware
        elif isinstance(new, AgentMiddleware):
            self._middleware[idx] = new
        else:
            raise TypeError(f"Expected AgentMiddleware or MiddlewareChain, got {type(new).__name__}")
        return self

    def clear(self) -> MiddlewareChain:
        self._middleware.clear()
        return self

    def copy(self) -> MiddlewareChain:
        return MiddlewareChain(list(self._middleware), name=self._name)

    # -- dunder -------------------------------------------------------------

    def __add__(self, other: AgentMiddleware | MiddlewareChain) -> MiddlewareChain:
        if isinstance(other, MiddlewareChain):
            return MiddlewareChain([*self._middleware, *other._middleware])
        if isinstance(other, AgentMiddleware):
            return MiddlewareChain([*self._middleware, other])
        return NotImplemented

    def __iadd__(self, other: AgentMiddleware | MiddlewareChain) -> MiddlewareChain:
        return self.add(other)

    def __len__(self) -> int:
        return len(self._middleware)

    def __bool__(self) -> bool:
        return bool(self._middleware)

    @overload
    def __getitem__(self, index: int) -> AgentMiddleware: ...
    @overload
    def __getitem__(self, index: slice) -> list[AgentMiddleware]: ...
    def __getitem__(self, index):
        return self._middleware[index]

    def __iter__(self) -> Iterator[AgentMiddleware]:
        return iter(self._middleware)

    def __contains__(self, item: object) -> bool:
        return item in self._middleware

    def __repr__(self) -> str:
        return f"MiddlewareChain({self._middleware!r})"

    def __str__(self) -> str:
        if not self._middleware:
            return f"{self.name} (empty)"
        flow = " → ".join(type(mw).__name__ for mw in self._middleware)
        return f"{self.name}: {flow}"

    # -- hook dispatch (async) ----------------------------------------------

    async def before_run(self, ctx: RunContext, prompt: str | Sequence[Any]) -> str | Sequence[Any]:
        current = prompt
        for mw in self._middleware:
            current = await _with_timeout(
                mw.before_run(ctx, current),
                mw.timeout,
                type(mw).__name__,
                "before_run",
            )
        return current

    async def after_run(self, ctx: RunContext, prompt: str | Sequence[Any], output: Any) -> Any:
        current = output
        for mw in reversed(self._middleware):
            current = await _with_timeout(
                mw.after_run(ctx, prompt, current),
                mw.timeout,
                type(mw).__name__,
                "after_run",
            )
        return current

    async def before_model_request(self, ctx: RunContext, messages: list[Any]) -> list[Any]:
        current = messages
        for mw in self._middleware:
            current = await _with_timeout(
                mw.before_model_request(ctx, current),
                mw.timeout,
                type(mw).__name__,
                "before_model_request",
            )
        return current

    async def before_tool_call(
        self,
        ctx: RunContext,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> dict[str, Any] | ToolPermissionResult:
        current_args = tool_args
        for mw in self._middleware:
            if not mw._should_handle_tool(tool_name):
                continue
            result = await _with_timeout(
                mw.before_tool_call(ctx, tool_name, current_args),
                mw.timeout,
                type(mw).__name__,
                "before_tool_call",
            )
            if isinstance(result, ToolPermissionResult):
                return result  # short-circuit
            current_args = result
        return current_args

    async def after_tool_call(
        self,
        ctx: RunContext,
        tool_name: str,
        tool_args: dict[str, Any],
        result: Any,
    ) -> Any:
        current = result
        for mw in reversed(self._middleware):
            if not mw._should_handle_tool(tool_name):
                continue
            current = await _with_timeout(
                mw.after_tool_call(ctx, tool_name, tool_args, current),
                mw.timeout,
                type(mw).__name__,
                "after_tool_call",
            )
        return current

    async def on_tool_error(
        self,
        ctx: RunContext,
        tool_name: str,
        tool_args: dict[str, Any],
        error: Exception,
    ) -> Exception | None:
        for mw in self._middleware:
            if not mw._should_handle_tool(tool_name):
                continue
            handled = await _with_timeout(
                mw.on_tool_error(ctx, tool_name, tool_args, error),
                mw.timeout,
                type(mw).__name__,
                "on_tool_error",
            )
            if handled is not None:
                return handled
        return None

    async def on_error(self, ctx: RunContext, error: Exception) -> Exception | None:
        for mw in self._middleware:
            handled = await _with_timeout(
                mw.on_error(ctx, error),
                mw.timeout,
                type(mw).__name__,
                "on_error",
            )
            if handled is not None:
                return handled
        return None


# ---------------------------------------------------------------------------
# Legacy sync HookChain (backward-compat with the old Hook Protocol)
# ---------------------------------------------------------------------------


class HookChain:
    """Sync hook chain (legacy).  Prefer ``MiddlewareChain`` for new code."""

    def __init__(self, hooks: list[Hook]):
        self.hooks = hooks

    def before_run(self, ctx: RunContext) -> None:
        for h in self.hooks:
            h.before_run(ctx)

    def after_run(self, ctx: RunContext, outcome: Any) -> Any:
        for h in reversed(self.hooks):
            outcome = h.after_run(ctx, outcome)
        return outcome

    def before_model_request(self, ctx: RunContext, request: Any) -> Any:
        for h in self.hooks:
            request = h.before_model_request(ctx, request)
        return request

    def after_model_response(self, ctx: RunContext, response: Any) -> Any:
        for h in reversed(self.hooks):
            response = h.after_model_response(ctx, response)
        return response

    def before_tool_call(self, ctx: RunContext, call: ToolCall) -> ToolCall:
        for h in self.hooks:
            call = h.before_tool_call(ctx, call)
        return call

    def after_tool_result(self, ctx: RunContext, result: ToolResult) -> ToolResult:
        for h in reversed(self.hooks):
            result = h.after_tool_result(ctx, result)
        return result

    def on_error(self, ctx: RunContext, err: Exception) -> Any | None:
        for h in reversed(self.hooks):
            maybe = h.on_error(ctx, err)
            if maybe is not None:
                return maybe
        return None
