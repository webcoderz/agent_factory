"""Auto-triggering LLM summarization processor.

Monitors token/message counts and automatically summarizes older messages
when thresholds are reached.  Works as a pydantic-ai ``history_processor``
or standalone via ``shape_messages``.

Example::

    from agent_ext.memory.processor import create_summarization_processor

    processor = create_summarization_processor(
        model="openai:gpt-4o",
        trigger=("tokens", 100_000),
        keep=("messages", 20),
    )

    agent = Agent("openai:gpt-4o", history_processors=[processor])
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from .cutoff import (
    TokenCounter,
    approximate_token_count,
    find_safe_cutoff,
    find_token_based_cutoff,
    is_safe_cutoff_point,
)

# ---------------------------------------------------------------------------
# Context size types (parity with summarization-pydantic-ai)
# ---------------------------------------------------------------------------

ContextSize = tuple[Literal["messages"], int] | tuple[Literal["tokens"], int] | tuple[Literal["fraction"], float]
"""Specify a context size as messages, tokens, or fraction of max."""

# ---------------------------------------------------------------------------
# Default prompt
# ---------------------------------------------------------------------------

DEFAULT_SUMMARY_PROMPT = (
    "<role>\nContext Extraction Assistant\n</role>\n\n"
    "<primary_objective>\n"
    "Extract the most relevant context from the conversation history below.\n"
    "</primary_objective>\n\n"
    "<instructions>\n"
    "The conversation history will be replaced with your extracted context. "
    "Extract and record the most important context. Focus on information "
    "relevant to the overall goal. Avoid repeating completed actions.\n"
    "</instructions>\n\n"
    "Respond ONLY with the extracted context. No additional information.\n\n"
    "<messages>\n{messages}\n</messages>"
)

_DEFAULT_KEEP = 20
_DEFAULT_TRIGGER_TOKENS = 170_000

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_context_size(cs: ContextSize, name: str) -> ContextSize:
    kind, value = cs
    if kind == "fraction":
        if not 0 < value <= 1:
            raise ValueError(f"{name} fraction must be in (0, 1], got {value}")
    elif kind in ("tokens", "messages"):
        if value < 0:
            raise ValueError(f"{name} must be non-negative, got {value}")
    else:
        raise ValueError(f"Unsupported context size type: {kind}")
    return cs


def _should_trigger(
    conditions: list[ContextSize],
    messages: list[Any],
    total_tokens: int,
    max_input_tokens: int | None,
) -> bool:
    """OR logic: any condition met → trigger."""
    for kind, value in conditions:
        if (
            (kind == "messages" and len(messages) >= value)
            or (kind == "tokens" and total_tokens >= value)
            or (kind == "fraction" and max_input_tokens and total_tokens >= int(max_input_tokens * value))
        ):
            return True
    return False


def _determine_cutoff(
    messages: list[Any],
    keep: ContextSize,
    token_counter: TokenCounter,
    max_input_tokens: int | None,
    default_keep: int,
) -> int:
    kind, value = keep
    if kind == "messages":
        return find_safe_cutoff(messages, int(value))
    elif kind == "tokens":
        return find_token_based_cutoff(messages, int(value), token_counter)
    elif kind == "fraction" and max_input_tokens:
        return find_token_based_cutoff(messages, int(max_input_tokens * value), token_counter)
    return find_safe_cutoff(messages, default_keep)


def format_messages_for_summary(messages: Sequence[Any]) -> str:
    """Format messages into a readable string for summarization.

    Works with pydantic-ai ModelMessages, dicts, or plain strings.
    """
    lines: list[str] = []
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get("role", "message")
            content = msg.get("content", "")
            lines.append(f"{role.title()}: {content}")
        elif isinstance(msg, str):
            lines.append(msg)
        elif hasattr(msg, "parts"):
            # pydantic-ai ModelRequest / ModelResponse
            cls_name = type(msg).__name__
            role = "User" if "Request" in cls_name else "Assistant"
            parts_text = []
            for part in msg.parts:
                if hasattr(part, "content"):
                    parts_text.append(str(part.content))
                elif hasattr(part, "tool_name"):
                    parts_text.append(f"[Tool: {part.tool_name}]")
            lines.append(f"{role}: {' '.join(parts_text)}")
        else:
            lines.append(str(msg))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SummarizationProcessor
# ---------------------------------------------------------------------------


@dataclass
class SummarizationProcessor:
    """Auto-triggering LLM summarization processor.

    Monitors token/message counts and automatically summarizes older messages
    when thresholds are reached.  Injects a summary as a system message at
    the front of the history.

    Can be used as:
    - pydantic-ai ``history_processor`` (``__call__``)
    - standalone via ``process(messages)``
    """

    model: str | Any
    """Model for generating summaries (string name or pydantic-ai Model)."""

    trigger: ContextSize | list[ContextSize] | None = None
    """Threshold(s) that trigger summarization (OR logic)."""

    keep: ContextSize = ("messages", _DEFAULT_KEEP)
    """How much recent context to keep after summarization."""

    token_counter: TokenCounter = field(default=approximate_token_count)
    summary_prompt: str = DEFAULT_SUMMARY_PROMPT
    max_input_tokens: int | None = None
    trim_tokens_to_summarize: int | None = 4000

    _trigger_conditions: list[ContextSize] = field(default_factory=list, init=False)
    _summary_cache: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.trigger is None:
            self._trigger_conditions = []
        elif isinstance(self.trigger, list):
            self._trigger_conditions = [_validate_context_size(t, "trigger") for t in self.trigger]
        else:
            self._trigger_conditions = [_validate_context_size(self.trigger, "trigger")]
        self.keep = _validate_context_size(self.keep, "keep")
        if (
            any(t[0] == "fraction" for t in self._trigger_conditions) or self.keep[0] == "fraction"
        ) and self.max_input_tokens is None:
            raise ValueError("max_input_tokens required for fraction-based trigger/keep")

    def _should_summarize(self, messages: list[Any], total_tokens: int) -> bool:
        return _should_trigger(self._trigger_conditions, messages, total_tokens, self.max_input_tokens)

    def _determine_cutoff(self, messages: list[Any]) -> int:
        return _determine_cutoff(messages, self.keep, self.token_counter, self.max_input_tokens, _DEFAULT_KEEP)

    async def _create_summary(self, messages_to_summarize: list[Any]) -> str:
        """Generate summary using the configured LLM."""
        if not messages_to_summarize:
            return "No previous conversation history."

        formatted = format_messages_for_summary(messages_to_summarize)
        if self.trim_tokens_to_summarize and len(formatted) > self.trim_tokens_to_summarize * 4:
            formatted = formatted[-(self.trim_tokens_to_summarize * 4) :]

        prompt = self.summary_prompt.format(messages=formatted)

        try:
            from pydantic_ai import Agent

            agent = Agent(self.model, instructions="You summarize conversations concisely.")
            result = await agent.run(prompt)
            return (getattr(result, "output", None) or str(result)).strip()
        except Exception as e:
            return f"Error generating summary: {e!s}"

    async def process(self, messages: list[Any]) -> list[Any]:
        """Process messages: summarize if thresholds are exceeded."""
        total_tokens = self.token_counter(messages)
        if not self._should_summarize(messages, total_tokens):
            return messages

        cutoff = self._determine_cutoff(messages)
        if cutoff <= 0:
            return messages

        to_summarize = messages[:cutoff]
        preserved = messages[cutoff:]
        summary = await self._create_summary(to_summarize)
        self._summary_cache = summary

        # Inject summary as a system-like message at front
        summary_msg = {"role": "system", "content": f"Summary of previous conversation:\n\n{summary}"}
        return [summary_msg, *preserved]

    async def __call__(self, *args: Any) -> list[Any]:
        """pydantic-ai history_processor interface.

        Accepts either (messages,) or (ctx, messages).
        """
        if len(args) == 1:
            messages = args[0]
        elif len(args) == 2:
            messages = args[1]
        else:
            return list(args[0]) if args else []
        return await self.process(messages)


def create_summarization_processor(
    model: str | Any = "openai:gpt-4o",
    trigger: ContextSize | list[ContextSize] | None = ("tokens", _DEFAULT_TRIGGER_TOKENS),
    keep: ContextSize = ("messages", _DEFAULT_KEEP),
    max_input_tokens: int | None = None,
    token_counter: TokenCounter | None = None,
    summary_prompt: str | None = None,
) -> SummarizationProcessor:
    """Factory for SummarizationProcessor with sensible defaults."""
    kwargs: dict[str, Any] = {"model": model, "trigger": trigger, "keep": keep}
    if max_input_tokens is not None:
        kwargs["max_input_tokens"] = max_input_tokens
    if token_counter is not None:
        kwargs["token_counter"] = token_counter
    if summary_prompt is not None:
        kwargs["summary_prompt"] = summary_prompt
    return SummarizationProcessor(**kwargs)
