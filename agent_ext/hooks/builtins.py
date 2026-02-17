from __future__ import annotations
import re
import time
from typing import Any, Callable, List, Literal, Optional, Sequence, Union

from .base import BlockedPrompt, BlockedToolCall, Hook
from agent_ext.run_context import RunContext, ToolCall, ToolResult

# Content filter: (ctx, payload, phase) -> filtered payload. phase is "request" or "response".
# May raise BlockedPrompt to block the request before it reaches the LLM.
ContentFilterFn = Callable[[RunContext, Any, Literal["request", "response"]], Any]


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


def _identity_filter(ctx: RunContext, payload: Any, phase: Literal["request", "response"]) -> Any:
    return payload


def _default_extract_text(payload: Any, phase: Literal["request", "response"]) -> str:
    """Best-effort extract of text from a request/response payload for blocklist checks."""
    if phase != "request":
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        parts: List[str] = []
        for msg in payload:
            if isinstance(msg, str):
                parts.append(msg)
            elif isinstance(msg, dict):
                if "content" in msg:
                    c = msg["content"]
                    parts.append(c if isinstance(c, str) else str(c))
                elif "parts" in msg:
                    for p in msg["parts"]:
                        if isinstance(p, dict) and "text" in p:
                            parts.append(str(p["text"]))
                else:
                    parts.append(str(msg))
            else:
                parts.append(str(msg))
        return "\n".join(parts)
    if isinstance(payload, dict):
        for key in ("messages", "prompt", "input", "content"):
            if key in payload:
                return _default_extract_text(payload[key], phase)
        return str(payload)
    return str(payload)


def make_blocklist_filter(
    patterns: Sequence[Union[str, re.Pattern]],
    *,
    extract_text: Optional[Callable[[Any, Literal["request", "response"]], str]] = None,
    reason: str = "Request blocked by policy",
) -> ContentFilterFn:
    """
    Build a content filter that blocks requests whose text matches any pattern.
    Raises BlockedPrompt so the request never reaches the LLM. Use in ContentFilterHook.
    """
    extract = extract_text or _default_extract_text
    compiled: List[re.Pattern] = []
    for p in patterns:
        if isinstance(p, re.Pattern):
            compiled.append(p)
        else:
            compiled.append(re.compile(re.escape(p), re.IGNORECASE))

    def filter_fn(ctx: RunContext, payload: Any, phase: Literal["request", "response"]) -> Any:
        if phase != "request":
            return payload
        text = extract(payload, phase)
        for pat in compiled:
            if pat.search(text):
                raise BlockedPrompt(
                    reason,
                    matched_rule=pat.pattern if hasattr(pat, "pattern") else str(pat),
                    details={"phase": phase},
                )
        return payload

    return filter_fn


class ContentFilterHook(Hook):
    """
    Middleware hook for content filtering / redaction on model request and response.
    Uses ctx.policy.redaction_level: when "none", payloads pass through; otherwise
    the filter_fn is applied. Supply your own filter (e.g. PII redaction, topic blocklist,
    or moderation API) via the filter_fn constructor argument.
    Your filter_fn may raise BlockedPrompt to block the request before it reaches the LLM;
    the runner should catch BlockedPrompt and not call the model (e.g. return a safe message).
    """
    def __init__(self, filter_fn: Optional[ContentFilterFn] = None) -> None:
        self.filter_fn = filter_fn or _identity_filter

    def before_run(self, ctx: RunContext) -> None:
        return None

    def after_run(self, ctx: RunContext, outcome: Any) -> Any:
        return outcome

    def before_model_request(self, ctx: RunContext, request: Any) -> Any:
        # Always run request filter so blocking (BlockedPrompt) works even when redaction_level is "none"
        return self.filter_fn(ctx, request, "request")

    def after_model_response(self, ctx: RunContext, response: Any) -> Any:
        # Only redact response when policy requests it
        if ctx.policy.redaction_level == "none":
            return response
        return self.filter_fn(ctx, response, "response")

    def before_tool_call(self, ctx: RunContext, call: ToolCall) -> ToolCall:
        return call

    def after_tool_result(self, ctx: RunContext, result: ToolResult) -> ToolResult:
        return result

    def on_error(self, ctx: RunContext, err: Exception) -> Optional[Any]:
        return None
