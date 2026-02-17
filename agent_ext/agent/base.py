"""
Base agent class built on pydantic-ai for use with agent_patterns RunContext and hooks.

Subclass PydanticAIAgentBase to create agents that:
- Use our RunContext (case_id, session_id, policy, logger, etc.) as pydantic-ai deps
- Can be wrapped with HookChain for audit, policy, etc.
- Use pydantic-ai's Agent for model calls, tools, and structured output
- Optionally plug in our memory (SlidingWindowMemory, SummarizingMemory) for
  conversation history and history_processors

Example:
    from pydantic import BaseModel, Field
    from agent_ext import PydanticAIAgentBase, RunContext, SlidingWindowMemory

    class MyOutput(BaseModel):
        answer: str = Field(description="The agent's answer")

    memory = SlidingWindowMemory(max_messages=20)
    class MyAgent(PydanticAIAgentBase[MyOutput]):
        def __init__(self):
            super().__init__(
                "openai:gpt-4o",
                output_type=MyOutput,
                instructions="You are a helpful assistant.",
                memory=memory,
            )

    agent = MyAgent()
    result = agent.run_sync(ctx, "What is 2+2?")
    # Next turn: pass message_history so the agent sees the conversation
    result2 = agent.run_sync(ctx, "And that in hex?", message_history=result.new_messages())
"""
from __future__ import annotations

from typing import Any, Optional, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent

from ..run_context import RunContext
from .memory_adapter import build_history_processor, checkpoint_after_run

# Alias to avoid clash with pydantic_ai.RunContext
PatternsRunContext = RunContext

# Output type for the agent (str for plain text, or a Pydantic model)
OutputT = TypeVar("OutputT", str, BaseModel)


class PydanticAIAgentBase(Agent[PatternsRunContext, OutputT]):
    """
    pydantic-ai Agent that uses agent_patterns RunContext as dependencies.

    Use this as a base class for your agents so they receive our RunContext
    (case_id, session_id, policy, logger, artifacts, etc.) in tools and
    dynamic instructions via ctx.deps.

    When memory is set (e.g. SlidingWindowMemory or SummarizingMemory):
    - A history_processor is registered so shape_messages() runs before each model request.
    - After each run_sync/run, checkpoint() is called with the full message history and
      result so SummarizingMemory can update the dossier.
    Pass message_history=result.new_messages() on subsequent turns to keep conversation.
    """

    def __init__(
        self,
        model: str,
        *,
        output_type: type[OutputT] = str,  # type: ignore[assignment]
        instructions: str | None = None,
        memory: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        if memory is not None:
            our_processor = [build_history_processor(memory)]
            kwargs["history_processors"] = our_processor + list(kwargs.get("history_processors", []))
        super().__init__(
            model,
            deps_type=PatternsRunContext,
            output_type=output_type,
            instructions=instructions or "",
            **kwargs,
        )
        self._memory = memory

    def run_sync(
        self,
        ctx: PatternsRunContext,
        message: str,
        **kwargs: Any,
    ) -> Any:
        """Run the agent synchronously with our RunContext as deps."""
        result = super().run_sync(message, deps=ctx, **kwargs)
        if self._memory is not None:
            checkpoint_after_run(
                self._memory,
                ctx,
                result.all_messages(),
                result,
            )
        return result

    async def run(
        self,
        ctx: PatternsRunContext,
        message: str,
        **kwargs: Any,
    ) -> Any:
        """Run the agent asynchronously with our RunContext as deps."""
        result = await super().run(message, deps=ctx, **kwargs)
        if self._memory is not None:
            checkpoint_after_run(
                self._memory,
                ctx,
                result.all_messages(),
                result,
            )
        return result
