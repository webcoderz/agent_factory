"""
Base agent class built on pydantic-ai for use with agent_patterns RunContext and hooks.

Subclass PydanticAIAgentBase to create agents that:
- Use our RunContext (case_id, session_id, policy, logger, etc.) as pydantic-ai deps
- Can be wrapped with HookChain for audit, policy, etc.
- Use pydantic-ai's Agent for model calls, tools, and structured output

Example:
    from pydantic import BaseModel, Field
    from agent_ext import PydanticAIAgentBase, RunContext

    class MyOutput(BaseModel):
        answer: str = Field(description="The agent's answer")

    class MyAgent(PydanticAIAgentBase[MyOutput]):
        def __init__(self):
            super().__init__(
                "openai:gpt-4o",
                output_type=MyOutput,
                instructions="You are a helpful assistant.",
            )

    agent = MyAgent()
    result = agent.run_sync(ctx, "What is 2+2?")
"""
from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent

from agent_ext.run_context import RunContext

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

    Example:
        class MyAgent(PydanticAIAgentBase[MyOutput]):
            def __init__(self):
                super().__init__(
                    "openai:gpt-4o",
                    output_type=MyOutput,
                    instructions="Be helpful.",
                )

        @my_agent.tool
        async def lookup(ctx: RunContext[PatternsRunContext], query: str) -> str:
            # ctx.deps is our RunContext (logger, policy, etc.)
            ctx.deps.logger.info("tool.lookup", query=query)
            return "..."
    """

    def __init__(
        self,
        model: str,
        *,
        output_type: type[OutputT] = str,  # type: ignore[assignment]
        instructions: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model,
            deps_type=PatternsRunContext,
            output_type=output_type,
            instructions=instructions or "",
            **kwargs,
        )

    def run_sync(
        self,
        ctx: PatternsRunContext,
        message: str,
        **kwargs: Any,
    ) -> Any:
        """Run the agent synchronously with our RunContext as deps."""
        return super().run_sync(message, deps=ctx, **kwargs)

    async def run(
        self,
        ctx: PatternsRunContext,
        message: str,
        **kwargs: Any,
    ) -> Any:
        """Run the agent asynchronously with our RunContext as deps."""
        return await super().run(message, deps=ctx, **kwargs)
