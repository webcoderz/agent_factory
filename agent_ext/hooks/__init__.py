"""Middleware / hooks system — async lifecycle hooks for AI agents."""

from .async_guardrail import AsyncGuardrailMiddleware
from .base import AgentMiddleware, Hook
from .builtins import (
    AuditHook,
    ConditionalMiddleware,
    ContentFilterFn,
    ContentFilterHook,
    PolicyHook,
    make_blocklist_filter,
)
from .chain import HookChain, MiddlewareChain
from .context import ContextAccessError, HookType, MiddlewareContext, ScopedContext
from .cost_tracking import CostInfo, CostTrackingMiddleware, create_cost_tracking_middleware
from .decorators import middleware_from_functions
from .exceptions import (
    BlockedPrompt,
    BlockedToolCall,
    BudgetExceededError,
    GuardrailTimeout,
    InputBlocked,
    MiddlewareConfigError,
    MiddlewareError,
    MiddlewareTimeout,
    OutputBlocked,
    ParallelExecutionFailed,
    ToolBlocked,
)
from .parallel import ParallelMiddleware
from .permissions import PermissionHandler, ToolDecision, ToolPermissionResult
from .strategies import AggregationStrategy, GuardrailTiming

__all__ = [
    # Base
    "AgentMiddleware",
    "Hook",
    # Chain
    "HookChain",
    "MiddlewareChain",
    # Context
    "ContextAccessError",
    "HookType",
    "MiddlewareContext",
    "ScopedContext",
    # Cost tracking
    "CostInfo",
    "CostTrackingMiddleware",
    "create_cost_tracking_middleware",
    # Exceptions
    "BlockedPrompt",
    "BlockedToolCall",
    "BudgetExceededError",
    "GuardrailTimeout",
    "InputBlocked",
    "MiddlewareConfigError",
    "MiddlewareError",
    "MiddlewareTimeout",
    "OutputBlocked",
    "ParallelExecutionFailed",
    "ToolBlocked",
    # Parallel + Strategies
    "AggregationStrategy",
    "GuardrailTiming",
    "ParallelMiddleware",
    # Async guardrail
    "AsyncGuardrailMiddleware",
    # Decorators
    "middleware_from_functions",
    # Permissions
    "PermissionHandler",
    "ToolDecision",
    "ToolPermissionResult",
    # Builtins
    "AuditHook",
    "ConditionalMiddleware",
    "ContentFilterFn",
    "ContentFilterHook",
    "PolicyHook",
    "make_blocklist_filter",
]
