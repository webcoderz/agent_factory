"""Sliding window memory — message-count or token-aware trimming.

Zero LLM cost, near-zero latency.  Preserves tool call/response pairs.
"""
from __future__ import annotations

from typing import Any, List

from .base import MemoryManager
from .cutoff import (
    TokenCounter,
    approximate_token_count,
    find_safe_cutoff,
    find_token_based_cutoff,
)


class SlidingWindowMemory(MemoryManager):
    """Keeps the most recent messages, discarding older ones.

    Supports both message-count and token-count modes.
    Preserves tool call/response pairs (never splits a pair).

    Args:
        max_messages: Max messages to keep (message-count mode).
        max_tokens: Max tokens to keep (token mode, overrides max_messages).
        token_counter: Custom token counting function.
        trigger_messages: Only trim when this many messages are reached.
            ``None`` means always trim when over *max_messages*.
        trigger_tokens: Only trim when this many tokens are reached.
    """

    def __init__(
        self,
        max_messages: int = 50,
        *,
        max_tokens: int | None = None,
        token_counter: TokenCounter | None = None,
        trigger_messages: int | None = None,
        trigger_tokens: int | None = None,
    ):
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.token_counter = token_counter or approximate_token_count
        self.trigger_messages = trigger_messages
        self.trigger_tokens = trigger_tokens

    def _should_trim(self, messages: List[Any]) -> bool:
        """Check if trimming should happen."""
        if self.trigger_tokens is not None:
            if self.token_counter(messages) >= self.trigger_tokens:
                return True
        if self.trigger_messages is not None:
            if len(messages) >= self.trigger_messages:
                return True
        # Default: trim when exceeding max
        if self.trigger_messages is None and self.trigger_tokens is None:
            if self.max_tokens is not None:
                return self.token_counter(messages) > self.max_tokens
            return len(messages) > self.max_messages
        return False

    def shape_messages(self, messages: List[Any]) -> List[Any]:
        if not self._should_trim(messages):
            return messages

        if self.max_tokens is not None:
            cutoff = find_token_based_cutoff(messages, self.max_tokens, self.token_counter)
        else:
            cutoff = find_safe_cutoff(messages, self.max_messages)

        return messages[cutoff:] if cutoff > 0 else messages

    def checkpoint(self, messages: List[Any], *, outcome: Any) -> None:
        # Sliding window doesn't checkpoint — no persistent state needed
        return None
