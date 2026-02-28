"""Structured permission decisions for tool calls.

Instead of raising ``ToolBlocked`` or returning modified args,
middleware can return a ``ToolPermissionResult`` with a structured decision:
ALLOW, DENY, or ASK (defers to a ``PermissionHandler`` callback).
"""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ToolDecision(Enum):
    """Decision for a tool-call permission check."""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"  # defer to a PermissionHandler callback


@dataclass
class ToolPermissionResult:
    """Structured result from ``before_tool_call``.

    Examples::

        # Allow with modified args
        ToolPermissionResult(decision=ToolDecision.ALLOW,
                             modified_args={**tool_args, "sanitized": True})

        # Deny
        ToolPermissionResult(decision=ToolDecision.DENY,
                             reason="Not authorized")

        # Ask a human / system
        ToolPermissionResult(decision=ToolDecision.ASK,
                             reason="Requires explicit approval")
    """

    decision: ToolDecision
    reason: str = ""
    modified_args: dict[str, Any] | None = field(default=None)


@runtime_checkable
class PermissionHandler(Protocol):
    """Callback protocol for handling ASK decisions.

    Implement to decide whether to allow or deny a tool call when
    middleware returns ``ToolDecision.ASK``.
    """

    def __call__(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        reason: str,
    ) -> Awaitable[bool]:
        """Return ``True`` to allow, ``False`` to deny."""
        ...
