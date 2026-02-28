"""Rich exception hierarchy for the middleware system.

Covers input/output blocking, tool blocking, permissions, budgets,
timeouts, parallel execution failures, and aggregation errors.
"""
from __future__ import annotations

from typing import Any, Optional


class MiddlewareError(Exception):
    """Base exception for all middleware errors."""


class MiddlewareConfigError(MiddlewareError):
    """Raised when middleware configuration is invalid."""


# ---------------------------------------------------------------------------
# Blocking
# ---------------------------------------------------------------------------

class InputBlocked(MiddlewareError):
    """Raised by *before_run* or *before_model_request* to block a prompt."""

    def __init__(self, reason: str = "Input blocked", *, matched_rule: Optional[str] = None, details: Any = None):
        self.reason = reason
        self.matched_rule = matched_rule
        self.details = details
        super().__init__(reason)


class ToolBlocked(MiddlewareError):
    """Raised when a tool call is blocked by middleware."""

    def __init__(self, tool_name: str, reason: str = "Tool blocked"):
        self.tool_name = tool_name
        self.reason = reason
        super().__init__(f"Tool '{tool_name}' blocked: {reason}")


class OutputBlocked(MiddlewareError):
    """Raised by *after_run* to block an agent output."""

    def __init__(self, reason: str = "Output blocked"):
        self.reason = reason
        super().__init__(reason)


# ---------------------------------------------------------------------------
# Budget / cost
# ---------------------------------------------------------------------------

class BudgetExceededError(MiddlewareError):
    """Raised when accumulated cost exceeds the configured budget limit."""

    def __init__(self, cost: float, budget: float):
        self.cost = cost
        self.budget = budget
        super().__init__(f"Budget exceeded: ${cost:.4f} >= ${budget:.4f} limit")


# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------

class MiddlewareTimeout(MiddlewareError):
    """Raised when a middleware hook exceeds its configured timeout."""

    def __init__(self, middleware_name: str, timeout: float, hook_name: str = ""):
        self.middleware_name = middleware_name
        self.timeout = timeout
        self.hook_name = hook_name
        detail = f" in {hook_name}" if hook_name else ""
        super().__init__(f"Middleware '{middleware_name}' timed out{detail} after {timeout:.2f}s")


class GuardrailTimeout(MiddlewareError):
    """Raised when an async guardrail times out."""

    def __init__(self, guardrail_name: str, timeout: float):
        self.guardrail_name = guardrail_name
        self.timeout = timeout
        super().__init__(f"Guardrail '{guardrail_name}' timed out after {timeout:.2f}s")


# ---------------------------------------------------------------------------
# Parallel execution
# ---------------------------------------------------------------------------

class ParallelExecutionFailed(MiddlewareError):
    """Raised when parallel middleware execution fails."""

    def __init__(
        self,
        errors: list[Exception],
        results: list[Any] | None = None,
        message: str = "Parallel middleware execution failed",
    ):
        self.errors = errors
        self.results = results or []
        self.failed_count = len(errors)
        self.success_count = len(self.results)
        super().__init__(f"{message}: {self.failed_count} failed, {self.success_count} succeeded")


# ---------------------------------------------------------------------------
# Backward-compat aliases (old names used in codebase)
# ---------------------------------------------------------------------------

# These map to the old names so existing code doesn't break.
BlockedToolCall = ToolBlocked
BlockedPrompt = InputBlocked
