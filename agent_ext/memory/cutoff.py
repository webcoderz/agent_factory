"""Safe cutoff algorithms for history processors.

Provides:
- Tool-call/response pair preservation when trimming
- Token-based cutoff via binary search
- Message-count cutoff with safety adjustment
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

# Type for token counters: (messages) -> int
TokenCounter = Callable[[Sequence[Any]], int]


def approximate_token_count(messages: Sequence[Any]) -> int:
    """Quick approximation: ~4 chars per token."""
    total = 0
    for m in messages:
        total += len(str(m))
    return total // 4


def _has_tool_call(msg: Any) -> bool:
    """Check if a message contains tool calls."""
    if isinstance(msg, dict):
        return bool(msg.get("tool_calls") or msg.get("tool_call_id"))
    if hasattr(msg, "parts"):
        for part in msg.parts:
            cls_name = type(part).__name__
            if "ToolCall" in cls_name:
                return True
    if hasattr(msg, "tool_calls"):
        return bool(msg.tool_calls)
    return False


def _has_tool_return(msg: Any) -> bool:
    """Check if a message contains tool returns."""
    if isinstance(msg, dict):
        role = msg.get("role", "")
        return role == "tool" or bool(msg.get("tool_call_id"))
    if hasattr(msg, "parts"):
        for part in msg.parts:
            cls_name = type(part).__name__
            if "ToolReturn" in cls_name:
                return True
    return False


def is_safe_cutoff_point(messages: list[Any], cutoff_index: int, search_range: int = 5) -> bool:
    """Check if cutting at *cutoff_index* would split a tool call/response pair.

    Returns ``True`` when the cutoff is safe (no pairs are split).
    """
    if cutoff_index >= len(messages) or cutoff_index <= 0:
        return True

    start = max(0, cutoff_index - search_range)
    end = min(len(messages), cutoff_index + search_range)

    # If the message right before cutoff has tool calls but the message
    # right after has tool returns — we'd split a pair.
    for i in range(start, min(cutoff_index, end)):
        if _has_tool_call(messages[i]):
            # Check if any message after cutoff is the return
            for j in range(cutoff_index, end):
                if _has_tool_return(messages[j]):
                    return False
    return True


def find_safe_cutoff(messages: list[Any], messages_to_keep: int) -> int:
    """Find a safe cutoff index preserving tool call/response pairs.

    Returns the index from which to slice: ``messages[cutoff:]``.
    """
    if messages_to_keep == 0:
        return len(messages)
    if len(messages) <= messages_to_keep:
        return 0

    target = len(messages) - messages_to_keep
    for i in range(target, -1, -1):
        if is_safe_cutoff_point(messages, i):
            return i
    return 0


def find_token_based_cutoff(
    messages: list[Any],
    target_tokens: int,
    token_counter: TokenCounter,
) -> int:
    """Binary search for cutoff index to retain ≤ *target_tokens*."""
    if not messages or token_counter(messages) <= target_tokens:
        return 0

    left, right = 0, len(messages)
    best = len(messages)

    for _ in range(len(messages).bit_length() + 2):
        if left >= right:
            break
        mid = (left + right) // 2
        if token_counter(messages[mid:]) <= target_tokens:
            best = mid
            right = mid
        else:
            left = mid + 1

    if best >= len(messages):
        best = max(0, len(messages) - 1)

    # Adjust for safety
    for i in range(best, -1, -1):
        if is_safe_cutoff_point(messages, i):
            return i
    return 0
