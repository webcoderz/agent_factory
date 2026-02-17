from __future__ import annotations
from typing import Any, List, Optional

from .base import Hook
from agent_ext.run_context import RunContext, ToolCall, ToolResult


class HookChain:
    def __init__(self, hooks: List[Hook]):
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

    def on_error(self, ctx: RunContext, err: Exception) -> Optional[Any]:
        for h in reversed(self.hooks):
            maybe = h.on_error(ctx, err)
            if maybe is not None:
                return maybe
        return None
