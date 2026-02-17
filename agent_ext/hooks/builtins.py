from __future__ import annotations
from typing import Any, Optional
import time

from base import BlockedToolCall, Hook
from ...types import RunContext, ToolCall, ToolResult


class AuditHook(Hook):
    def before_run(self, ctx: RunContext) -> None:
        ctx.tags["t0"] = time.time()
        ctx.logger.info("agent.run.start", case_id=ctx.case_id, session_id=ctx.session_id, trace_id=ctx.trace_id)

    def after_run(self, ctx: RunContext, outcome: Any) -> Any:
        dt = time.time() - float(ctx.tags.get("t0", time.time()))
        ctx.logger.info("agent.run.end", seconds=dt, trace_id=ctx.trace_id)
        return outcome

    def before_model_request(self, ctx: RunContext, request: Any) -> Any:
        ctx.logger.info("model.request", trace_id=ctx.trace_id)
        return request

    def after_model_response(self, ctx: RunContext, response: Any) -> Any:
        ctx.logger.info("model.response", trace_id=ctx.trace_id)
        return response

    def before_tool_call(self, ctx: RunContext, call: ToolCall) -> ToolCall:
        ctx.logger.info("tool.call", name=call.name, trace_id=ctx.trace_id)
        return call

    def after_tool_result(self, ctx: RunContext, result: ToolResult) -> ToolResult:
        ctx.logger.info("tool.result", name=result.name, ok=result.ok, trace_id=ctx.trace_id)
        return result

    def on_error(self, ctx: RunContext, err: Exception) -> Optional[Any]:
        ctx.logger.error("agent.error", error=str(err), trace_id=ctx.trace_id)
        return None


class PolicyHook(Hook):
    def before_run(self, ctx: RunContext) -> None:
        return None

    def after_run(self, ctx: RunContext, outcome: Any) -> Any:
        return outcome

    def before_model_request(self, ctx: RunContext, request: Any) -> Any:
        return request

    def after_model_response(self, ctx: RunContext, response: Any) -> Any:
        return response

    def before_tool_call(self, ctx: RunContext, call: ToolCall) -> ToolCall:
        if not ctx.policy.allow_tools:
            raise BlockedToolCall(f"Tools are disabled by policy: {call.name}")
        return call

    def after_tool_result(self, ctx: RunContext, result: ToolResult) -> ToolResult:
        return result

    def on_error(self, ctx: RunContext, err: Exception) -> Optional[Any]:
        return None
