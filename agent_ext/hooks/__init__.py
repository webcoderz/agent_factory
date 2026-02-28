"""Middleware / hooks system — async lifecycle hooks for AI agents."""

from .base import AgentMiddleware, Hook
from .chain import HookChain, MiddlewareChain
from .context import ContextAccessError, HookType, MiddlewareContext, ScopedContext
from .cost_tracking import CostInfo, CostTrackingMiddleware, create_cost_tracking_middleware
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
from .parallel import AggregationStrategy, ParallelMiddleware
from .permissions import PermissionHandler, ToolDecision, ToolPermissionResult
from .builtins import (
    AuditHook,
    ConditionalMiddleware,
    ContentFilterFn,
    ContentFilterHook,
    PolicyHook,
    make_blocklist_filter,
)

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
    # Parallel
    "AggregationStrategy",
    "ParallelMiddleware",
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
