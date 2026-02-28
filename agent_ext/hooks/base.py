"""Async middleware base class and legacy sync Protocol.

The new ``AgentMiddleware`` ABC is the primary base:
- All hooks are async
- ``tool_names`` filter (None = all tools)
- ``timeout`` per hook
- Full lifecycle: before_run, after_run, before_model_request,
  before_tool_call, after_tool_call, on_tool_error, on_error

The old ``Hook`` sync Protocol is kept for backward-compat but users
should migrate to ``AgentMiddleware``.
"""
from __future__ import annotations

from abc import ABC
from collections.abc import Sequence
from typing import Any, Optional, Protocol

from agent_ext.run_context import RunContext, ToolCall, ToolResult

# Re-export exceptions so ``from agent_ext.hooks.base import BlockedToolCall``
# still works.
from .exceptions import (  # noqa: F401
    BlockedPrompt,
    BlockedToolCall,
    BudgetExceededError,
    GuardrailTimeout,
    InputBlocked,
    MiddlewareError,
    MiddlewareTimeout,
    OutputBlocked,
    ToolBlocked,
)


# ---------------------------------------------------------------------------
# New async ABC (parity with pydantic-ai-middleware)
# ---------------------------------------------------------------------------

class AgentMiddleware(ABC):
    """Async middleware base class.

    Override only the hooks you need.  ``before_*`` hooks run in order,
    ``after_*`` hooks run in reverse order (onion model).

    Attributes:
        tool_names: Set of tool names this middleware applies to.
            ``None`` (default) means *all* tools.
        timeout: Max seconds for any single hook call (``None`` = unlimited).
    """

    tool_names: set[str] | None = None
    timeout: float | None = None

    def _should_handle_tool(self, tool_name: str) -> bool:
        if self.tool_names is None:
            return True
        return tool_name in self.tool_names

    # -- lifecycle hooks (all async) ----------------------------------------

    async def before_run(self, ctx: RunContext, prompt: str | Sequence[Any]) -> str | Sequence[Any]:
        """Called before the agent runs.  May modify or block the prompt."""
        return prompt

    async def after_run(self, ctx: RunContext, prompt: str | Sequence[Any], output: Any) -> Any:
        """Called after the agent finishes.  May modify or block the output."""
        return output

    async def before_model_request(self, ctx: RunContext, messages: list[Any]) -> list[Any]:
        """Called before each model request."""
        return messages

    async def before_tool_call(
        self,
        ctx: RunContext,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> dict[str, Any]:
        """Called before a tool is called.  Return modified args or raise ``ToolBlocked``."""
        return tool_args

    async def after_tool_call(
        self,
        ctx: RunContext,
        tool_name: str,
        tool_args: dict[str, Any],
        result: Any,
    ) -> Any:
        """Called after a tool returns.  May modify the result."""
        return result

    async def on_tool_error(
        self,
        ctx: RunContext,
        tool_name: str,
        tool_args: dict[str, Any],
        error: Exception,
    ) -> Exception | None:
        """Called when a tool raises.  Return a replacement exception or ``None`` to re-raise."""
        return None

    async def on_error(self, ctx: RunContext, error: Exception) -> Exception | None:
        """Called on any error.  Return replacement or ``None`` to re-raise."""
        return None


# ---------------------------------------------------------------------------
# Legacy sync Protocol (backward-compat)
# ---------------------------------------------------------------------------

class Hook(Protocol):
    """Sync hook protocol (legacy).  Prefer ``AgentMiddleware`` for new code."""

    def before_run(self, ctx: RunContext) -> None: ...
    def after_run(self, ctx: RunContext, outcome: Any) -> Any: ...
    def before_model_request(self, ctx: RunContext, request: Any) -> Any: ...
    def after_model_response(self, ctx: RunContext, response: Any) -> Any: ...
    def before_tool_call(self, ctx: RunContext, call: ToolCall) -> ToolCall: ...
    def after_tool_result(self, ctx: RunContext, result: ToolResult) -> ToolResult: ...
    def on_error(self, ctx: RunContext, err: Exception) -> Optional[Any]: ...
