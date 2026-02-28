"""Decorator-based middleware for simple use cases.

Create middleware from individual async functions instead of subclassing.

Example::

    from agent_ext.hooks.decorators import middleware_from_functions

    async def log_prompt(ctx, prompt):
        print(f"Prompt: {prompt}")
        return prompt

    async def sanitize_output(ctx, prompt, output):
        return output.replace("SSN:", "[REDACTED]")

    mw = middleware_from_functions(before_run=log_prompt, after_run=sanitize_output)
"""

from __future__ import annotations

from collections.abc import Callable

from .base import AgentMiddleware


class _FunctionMiddleware(AgentMiddleware):
    """Middleware that delegates to individual functions."""

    def __init__(
        self,
        *,
        before_run_fn: Callable | None = None,
        after_run_fn: Callable | None = None,
        before_model_request_fn: Callable | None = None,
        before_tool_call_fn: Callable | None = None,
        after_tool_call_fn: Callable | None = None,
        on_tool_error_fn: Callable | None = None,
        on_error_fn: Callable | None = None,
        tool_names: set[str] | None = None,
    ):
        self._before_run_fn = before_run_fn
        self._after_run_fn = after_run_fn
        self._before_model_request_fn = before_model_request_fn
        self._before_tool_call_fn = before_tool_call_fn
        self._after_tool_call_fn = after_tool_call_fn
        self._on_tool_error_fn = on_tool_error_fn
        self._on_error_fn = on_error_fn
        if tool_names is not None:
            self.tool_names = tool_names

    async def before_run(self, ctx, prompt):
        if self._before_run_fn:
            return await self._before_run_fn(ctx, prompt)
        return prompt

    async def after_run(self, ctx, prompt, output):
        if self._after_run_fn:
            return await self._after_run_fn(ctx, prompt, output)
        return output

    async def before_model_request(self, ctx, messages):
        if self._before_model_request_fn:
            return await self._before_model_request_fn(ctx, messages)
        return messages

    async def before_tool_call(self, ctx, tool_name, tool_args):
        if self._before_tool_call_fn:
            return await self._before_tool_call_fn(ctx, tool_name, tool_args)
        return tool_args

    async def after_tool_call(self, ctx, tool_name, tool_args, result):
        if self._after_tool_call_fn:
            return await self._after_tool_call_fn(ctx, tool_name, tool_args, result)
        return result

    async def on_tool_error(self, ctx, tool_name, tool_args, error):
        if self._on_tool_error_fn:
            return await self._on_tool_error_fn(ctx, tool_name, tool_args, error)
        return None

    async def on_error(self, ctx, error):
        if self._on_error_fn:
            return await self._on_error_fn(ctx, error)
        return None


def middleware_from_functions(
    *,
    before_run: Callable | None = None,
    after_run: Callable | None = None,
    before_model_request: Callable | None = None,
    before_tool_call: Callable | None = None,
    after_tool_call: Callable | None = None,
    on_tool_error: Callable | None = None,
    on_error: Callable | None = None,
    tool_names: set[str] | None = None,
) -> AgentMiddleware:
    """Create middleware from individual async functions.

    Each function receives the same args as the corresponding
    ``AgentMiddleware`` hook method.
    """
    return _FunctionMiddleware(
        before_run_fn=before_run,
        after_run_fn=after_run,
        before_model_request_fn=before_model_request,
        before_tool_call_fn=before_tool_call,
        after_tool_call_fn=after_tool_call,
        on_tool_error_fn=on_tool_error,
        on_error_fn=on_error,
        tool_names=tool_names,
    )
