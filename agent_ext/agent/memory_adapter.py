"""
Bridges agent_patterns memory (MemoryManager, SlidingWindowMemory, SummarizingMemory)
with pydantic-ai's message history and history_processors.

- Builds a history_processor callable that runs our shape_messages() so the agent
  sees windowed/summarized context (and optional dossier).
- Supports checkpoint() after each run so SummarizingMemory can persist dossiers.
- Safe truncation: preserves tool call pairs (never cuts between a ModelResponse
  with ToolCallPart and the following ModelRequest with ToolReturnPart).
- Full round-trip: generic dicts keep _original so tool calls are preserved.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_ext.memory.base import MemoryManager
    from agent_ext.run_context import RunContext


# --- Tool call inspection and safe truncation ---


def message_kind(msg: Any) -> str:
    """
    Classify a pydantic-ai message for inspection.
    Returns: "request" | "response" | "response_tool_calls" | "unknown"
    """
    name = type(msg).__name__
    if name == "ModelRequest":
        return "request"
    if name == "ModelResponse":
        if has_tool_calls(msg):
            return "response_tool_calls"
        return "response"
    return "unknown"


def has_tool_calls(msg: Any) -> bool:
    """True if message is a ModelResponse that contains any ToolCallPart."""
    if type(msg).__name__ != "ModelResponse":
        return False
    parts = getattr(msg, "parts", []) or []
    for p in parts:
        if type(p).__name__ == "ToolCallPart":
            return True
        if isinstance(p, dict) and p.get("tool_name") is not None:
            return True
    return False


def has_tool_returns(msg: Any) -> bool:
    """True if message is a ModelRequest that contains any ToolReturnPart."""
    if type(msg).__name__ != "ModelRequest":
        return False
    parts = getattr(msg, "parts", []) or []
    for p in parts:
        if type(p).__name__ == "ToolReturnPart":
            return True
        if isinstance(p, dict) and p.get("tool_call_id") is not None:
            return True
    return False


def safe_truncate_messages(
    messages: list[Any],
    max_messages: int,
    *,
    only_before_request: bool = True,
) -> list[Any]:
    """
    Truncate from the front so at most max_messages remain, without breaking tool call pairs.

    Safe cutoff: we only drop messages such that the first kept message is a ModelRequest.
    That way we never leave a ModelResponse (with ToolCallPart) without the following
    ModelRequest (ToolReturnPart). Optionally relax to allow starting at any message
    when only_before_request=False (still avoids cutting inside a single request/response).
    """
    if not messages or max_messages <= 0:
        return list(messages)
    n = len(messages)
    if n <= max_messages:
        return list(messages)

    # Find smallest index i such that M[i] is a ModelRequest and len(M[i:]) <= max_messages.
    best_i = 0
    last_request_i = 0
    for i in range(n):
        msg = messages[i]
        name = type(msg).__name__
        if only_before_request and name != "ModelRequest":
            continue
        last_request_i = i
        if n - i <= max_messages:
            best_i = i
            break
    else:
        # No i gave us <= max_messages; keep from last ModelRequest so we don't break a pair
        best_i = last_request_i
    return list(messages[best_i:])


def _model_message_to_dict(msg: Any) -> dict[str, Any]:
    """Convert a pydantic-ai ModelRequest/ModelResponse to a simple dict for our memory."""
    if hasattr(msg, "model_dump"):
        d = msg.model_dump()
        # ModelRequest has 'parts', ModelResponse has 'parts'
        parts = d.get("parts", [])
        content_parts: list[str] = []
        role = "message"
        for p in parts:
            if isinstance(p, dict):
                if "content" in p:
                    content_parts.append(str(p["content"]))
                # Infer role from part type
                if "UserPromptPart" in str(type(p)) or p.get("content") is not None:
                    pass
            elif hasattr(p, "content"):
                content_parts.append(str(getattr(p, "content", "")))
        # Prefer role from message type
        if type(msg).__name__ == "ModelRequest":
            role = "user"
        elif type(msg).__name__ == "ModelResponse":
            role = "assistant"
        return {"role": role, "content": "\n".join(content_parts) if content_parts else ""}
    return {"role": "message", "content": str(msg)}


def _extract_content_from_part(part: Any) -> str:
    if isinstance(part, dict):
        return str(part.get("content", ""))
    if hasattr(part, "content"):
        return str(getattr(part, "content", ""))
    return str(part)


def _model_message_to_dict_v2(msg: Any) -> dict[str, Any]:
    """Extract role and content from pydantic-ai message (handles parts)."""
    name = type(msg).__name__
    if name == "ModelRequest":
        parts = getattr(msg, "parts", []) or []
        content = " ".join(_extract_content_from_part(p) for p in parts).strip()
        return {"role": "user", "content": content or "(no content)"}
    if name == "ModelResponse":
        parts = getattr(msg, "parts", []) or []
        content = " ".join(_extract_content_from_part(p) for p in parts).strip()
        return {"role": "assistant", "content": content or "(no content)"}
    return {"role": "message", "content": str(msg)}


def _generic_dict_with_original(msg: Any) -> dict[str, Any]:
    """Build generic dict and attach _original for round-trip of tool calls."""
    d = _model_message_to_dict_v2(msg)
    d["_original"] = msg
    return d


def _dict_to_model_message(d: dict[str, Any]) -> Any:
    """Convert a dict (from our memory) back to a pydantic-ai ModelRequest/ModelResponse."""
    from pydantic_ai import ModelRequest, ModelResponse
    from pydantic_ai.messages import TextPart, UserPromptPart

    role = (d.get("role") or "message").lower()
    content = d.get("content") or ""

    if role == "system":
        try:
            from pydantic_ai.messages import SystemPromptPart

            return ModelRequest(parts=[SystemPromptPart(content=content)])
        except ImportError:
            return ModelRequest(parts=[UserPromptPart(content=f"[System]\n{content}")])
    if role in ("user", "request"):
        return ModelRequest(parts=[UserPromptPart(content=content)])
    return ModelResponse(parts=[TextPart(content=content)])


def _dict_to_model_message_safe(d: dict[str, Any]) -> Any:
    """Convert dict to ModelMessage using available pydantic_ai types."""
    try:
        return _dict_to_model_message(d)
    except Exception:
        try:
            from pydantic_ai.messages import (
                ModelRequest,
                ModelResponse,
                TextPart,
                UserPromptPart,
            )
        except ImportError:
            from pydantic_ai import ModelRequest, ModelResponse
            from pydantic_ai.messages import TextPart, UserPromptPart
        role = (d.get("role") or "message").lower()
        content = d.get("content") or ""
        if role == "system":
            return ModelRequest(parts=[UserPromptPart(content=f"[System]\n{content}")])
        if role in ("user", "request"):
            return ModelRequest(parts=[UserPromptPart(content=content)])
        return ModelResponse(parts=[TextPart(content=content)])


def model_messages_to_generic(
    messages: list[Any],
    *,
    preserve_originals: bool = True,
) -> list[dict[str, Any]]:
    """
    Convert pydantic-ai ModelMessage list to list of dicts for our memory.
    When preserve_originals=True (default), each dict has _original so tool calls
    and full structure round-trip through shape_messages.
    """
    if preserve_originals:
        return [_generic_dict_with_original(m) for m in messages]
    return [_model_message_to_dict_v2(m) for m in messages]


def generic_to_model_messages(generic: list[Any]) -> list[Any]:
    """
    Convert list of dicts (from our memory) back to pydantic-ai ModelMessage list.
    If a dict has _original, that message is used as-is (preserves tool calls).
    """
    out: list[Any] = []
    for m in generic:
        if isinstance(m, dict) and "_original" in m:
            out.append(m["_original"])
        elif isinstance(m, dict):
            out.append(_dict_to_model_message_safe(m))
        else:
            out.append(m)
    return out


def _get_memory_max_messages(memory: Any) -> int | None:
    """Get max_messages from SlidingWindowMemory or SummarizingMemory.cfg."""
    if hasattr(memory, "max_messages"):
        return memory.max_messages
    if hasattr(memory, "cfg") and memory.cfg is not None:
        return getattr(memory.cfg, "max_messages", None)
    return None


def build_history_processor(
    memory: MemoryManager,
    *,
    max_messages_for_safe_truncate: int | None = None,
) -> Callable[..., list[Any]]:
    """
    Build a pydantic-ai history_processor that uses our MemoryManager.shape_messages.

    - Safe truncation: if max_messages_for_safe_truncate is set (or inferred from
      memory.max_messages / memory.cfg.max_messages), messages are truncated from
      the front only at safe boundaries so tool call pairs are never split.
    - Full round-trip: generic dicts keep _original so ToolCallPart/ToolReturnPart
      are preserved through shape_messages.

    The returned callable can be used as Agent(history_processors=[...]).
    It accepts (ctx: RunContext[Deps], messages: list[ModelMessage]) and returns
    list[ModelMessage]. If the processor is called with (messages,) only, it also works.

    When memory is SummarizingMemory, bind_ctx(ctx.deps) is called when the processor
    runs so the dossier can use RunContext (e.g. artifacts).
    """
    max_m = max_messages_for_safe_truncate
    if max_m is None:
        max_m = _get_memory_max_messages(memory)

    def processor(
        ctx_or_messages: Any,
        messages: list[Any] | None = None,
    ) -> list[Any]:
        if messages is None:
            messages = ctx_or_messages
            ctx = None
        else:
            ctx = ctx_or_messages
        # Bind RunContext for SummarizingMemory
        if ctx is not None and hasattr(ctx, "deps") and hasattr(memory, "bind_ctx"):
            memory.bind_ctx(ctx.deps)
        # Safe cutoff first: preserve tool call pairs
        if max_m is not None and len(messages) > max_m:
            messages = safe_truncate_messages(messages, max_m)
        generic = model_messages_to_generic(messages, preserve_originals=True)
        shaped = memory.shape_messages(generic)
        return generic_to_model_messages(shaped)

    return processor


def checkpoint_after_run(
    memory: MemoryManager,
    ctx: RunContext,
    all_messages: list[Any],
    outcome: Any,
) -> None:
    """
    Call memory.checkpoint() after an agent run. Use with result.all_messages() and result.
    Uses generic dicts without _original so checkpoint storage stays serializable.
    """
    if hasattr(memory, "bind_ctx"):
        memory.bind_ctx(ctx)
    generic = model_messages_to_generic(all_messages, preserve_originals=False)
    memory.checkpoint(generic, outcome=outcome)
