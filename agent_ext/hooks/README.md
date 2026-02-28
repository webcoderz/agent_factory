# Middleware / Hooks System

Full-featured async middleware for intercepting, transforming, and guarding every step of an AI agent's lifecycle.

## Features

- **7 Lifecycle Hooks**: `before_run`, `after_run`, `before_model_request`, `before_tool_call`, `after_tool_call`, `on_tool_error`, `on_error`
- **Scoped Context**: Data sharing between hooks with strict access controls (each hook can only read from earlier hooks)
- **Cost Tracking**: Automatic token counting and USD cost monitoring with budget enforcement
- **Parallel Execution**: Run multiple validators concurrently with aggregation strategies
- **Permissions**: Structured ALLOW/DENY/ASK decisions for tool calls
- **Timeouts**: Per-hook timeout enforcement
- **Tool Filtering**: Apply middleware to specific tools only
- **Conditional Middleware**: Run only when a condition is met

## Quick Start

```python
from agent_ext.hooks.base import AgentMiddleware
from agent_ext.hooks.chain import MiddlewareChain
from agent_ext.hooks.exceptions import InputBlocked

class ContentFilter(AgentMiddleware):
    async def before_run(self, ctx, prompt):
        if "ignore instructions" in str(prompt).lower():
            raise InputBlocked("Prompt injection blocked")
        return prompt

chain = MiddlewareChain([ContentFilter(), AuditHook()])
```

## Built-in Middleware

| Middleware | Purpose |
|-----------|---------|
| `AuditHook` | Logs lifecycle events with timing |
| `PolicyHook` | Enforces `ctx.policy` (blocks tools, etc.) |
| `ContentFilterHook` | Content filtering with blocklists |
| `CostTrackingMiddleware` | Token + USD cost tracking |
| `ParallelMiddleware` | Run validators concurrently |
| `ConditionalMiddleware` | Run middleware only when condition met |

## Aggregation Strategies (Parallel)

| Strategy | Behavior |
|----------|----------|
| `ALL_MUST_PASS` | All must succeed, any failure fails |
| `FIRST_WINS` | First non-exception result used |
| `MERGE` | Combine all dict results |

## Permissions

```python
from agent_ext.hooks.permissions import ToolDecision, ToolPermissionResult

class ApprovalMiddleware(AgentMiddleware):
    async def before_tool_call(self, ctx, tool_name, tool_args):
        if tool_name == "delete_file":
            return ToolPermissionResult(
                decision=ToolDecision.ASK,
                reason="Destructive operation requires approval",
            )
        return tool_args
```

## Context System

```python
from agent_ext.hooks.context import MiddlewareContext, HookType

ctx = MiddlewareContext(config={"rate_limit": 100})
scoped = ctx.for_hook(HookType.BEFORE_RUN)
scoped.set("user_intent", "question")

# Later hook can read earlier data
later = ctx.for_hook(HookType.AFTER_RUN)
intent = later.get_from(HookType.BEFORE_RUN, "user_intent")
```
