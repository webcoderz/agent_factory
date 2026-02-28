"""Built-in middleware implementations.

All middleware are now async ``AgentMiddleware`` subclasses.
Legacy sync imports (``AuditHook``, ``PolicyHook``, ``ContentFilterHook``,
``make_blocklist_filter``) still work — they subclass both ``AgentMiddleware``
and implement the old sync ``Hook`` interface for backward-compat.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from typing import Any, Literal

from agent_ext.run_context import RunContext

from .base import AgentMiddleware
from .exceptions import InputBlocked, ToolBlocked

# Type alias for content filter functions
ContentFilterFn = Callable[[RunContext, Any, Literal["request", "response"]], Any]


# ---------------------------------------------------------------------------
# AuditHook (async middleware + legacy sync interface)
# ---------------------------------------------------------------------------


class AuditHook(AgentMiddleware):
    """Logs lifecycle events: run start/end, model requests, tool calls."""

    async def before_run(self, ctx: RunContext, prompt: str | Sequence[Any]) -> str | Sequence[Any]:
        ctx.tags["t0"] = time.time()
        ctx.logger.info("agent.run.start", case_id=ctx.case_id, session_id=ctx.session_id, trace_id=ctx.trace_id)
        return prompt

    async def after_run(self, ctx: RunContext, prompt: str | Sequence[Any], output: Any) -> Any:
        dt = time.time() - float(ctx.tags.get("t0", time.time()))
        ctx.logger.info("agent.run.end", seconds=dt, trace_id=ctx.trace_id)
        return output

    async def before_model_request(self, ctx: RunContext, messages: list[Any]) -> list[Any]:
        ctx.logger.info("model.request", trace_id=ctx.trace_id)
        return messages

    async def before_tool_call(self, ctx: RunContext, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        ctx.logger.info("tool.call", name=tool_name, trace_id=ctx.trace_id)
        return tool_args

    async def after_tool_call(self, ctx: RunContext, tool_name: str, tool_args: dict[str, Any], result: Any) -> Any:
        ctx.logger.info("tool.result", name=tool_name, trace_id=ctx.trace_id)
        return result

    async def on_error(self, ctx: RunContext, error: Exception) -> Exception | None:
        ctx.logger.error("agent.error", error=str(error), trace_id=ctx.trace_id)
        return None


# ---------------------------------------------------------------------------
# PolicyHook
# ---------------------------------------------------------------------------


class PolicyHook(AgentMiddleware):
    """Enforces ``ctx.policy`` — blocks tools when ``allow_tools=False``."""

    async def before_tool_call(self, ctx: RunContext, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        if not ctx.policy.allow_tools:
            raise ToolBlocked(tool_name, "Tools are disabled by policy")
        return tool_args


# ---------------------------------------------------------------------------
# Content filtering
# ---------------------------------------------------------------------------


def _default_extract_text(payload: Any, phase: Literal["request", "response"]) -> str:
    """Best-effort text extraction from a request/response payload."""
    if phase != "request":
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        parts: list[str] = []
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
    patterns: Sequence[str | re.Pattern[str]],
    *,
    extract_text: Callable[[Any, Literal["request", "response"]], str] | None = None,
    reason: str = "Request blocked by policy",
) -> ContentFilterFn:
    """Build a content filter that blocks requests matching any pattern.

    Raises ``InputBlocked`` so the request never reaches the LLM.
    """
    extract = extract_text or _default_extract_text
    compiled: list[re.Pattern[str]] = []
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
                raise InputBlocked(
                    reason,
                    matched_rule=pat.pattern if hasattr(pat, "pattern") else str(pat),
                    details={"phase": phase},
                )
        return payload

    return filter_fn


class ContentFilterHook(AgentMiddleware):
    """Content filtering / redaction middleware.

    Runs ``filter_fn`` on every ``before_model_request`` (always) and on
    ``after_run`` when ``ctx.policy.redaction_level`` is not ``"none"``.

    ``filter_fn`` may raise ``InputBlocked`` to block the request.
    """

    def __init__(self, filter_fn: ContentFilterFn | None = None) -> None:
        self.filter_fn = filter_fn or (lambda ctx, payload, phase: payload)

    async def before_model_request(self, ctx: RunContext, messages: list[Any]) -> list[Any]:
        return self.filter_fn(ctx, messages, "request")

    async def after_run(self, ctx: RunContext, prompt: str | Sequence[Any], output: Any) -> Any:
        if ctx.policy.redaction_level == "none":
            return output
        return self.filter_fn(ctx, output, "response")


# ---------------------------------------------------------------------------
# Conditional middleware
# ---------------------------------------------------------------------------


class ConditionalMiddleware(AgentMiddleware):
    """Wraps another middleware, only executing it when ``condition(ctx)`` is True.

    Example::

        cond = ConditionalMiddleware(
            PII_Filter(),
            condition=lambda ctx: ctx.policy.redaction_level != "none",
        )
    """

    def __init__(
        self,
        inner: AgentMiddleware,
        condition: Callable[[RunContext], bool],
    ) -> None:
        self.inner = inner
        self.condition = condition

    async def before_run(self, ctx, prompt):
        if self.condition(ctx):
            return await self.inner.before_run(ctx, prompt)
        return prompt

    async def after_run(self, ctx, prompt, output):
        if self.condition(ctx):
            return await self.inner.after_run(ctx, prompt, output)
        return output

    async def before_model_request(self, ctx, messages):
        if self.condition(ctx):
            return await self.inner.before_model_request(ctx, messages)
        return messages

    async def before_tool_call(self, ctx, tool_name, tool_args):
        if self.condition(ctx):
            return await self.inner.before_tool_call(ctx, tool_name, tool_args)
        return tool_args

    async def after_tool_call(self, ctx, tool_name, tool_args, result):
        if self.condition(ctx):
            return await self.inner.after_tool_call(ctx, tool_name, tool_args, result)
        return result

    async def on_tool_error(self, ctx, tool_name, tool_args, error):
        if self.condition(ctx):
            return await self.inner.on_tool_error(ctx, tool_name, tool_args, error)
        return None

    async def on_error(self, ctx, error):
        if self.condition(ctx):
            return await self.inner.on_error(ctx, error)
        return None
