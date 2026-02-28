"""Subagent toolset — delegate tasks to specialized subagents via tool calls.

Supports sync (blocking), async (background), and auto execution modes.

Example::

    from pydantic_ai import Agent
    from agent_ext.subagents import create_subagent_toolset, SubAgentDeps

    toolset = create_subagent_toolset(configs=[...])
    agent = Agent("openai:gpt-4o", toolsets=[toolset])
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, SkipValidation
from pydantic_ai import Agent, RunContext
from pydantic_ai.toolsets import FunctionToolset

from .message_bus import InMemoryMessageBus, TaskManager
from .prompts import (
    TASK_TOOL_DESCRIPTION,
    CHECK_TASK_DESCRIPTION,
    LIST_ACTIVE_TASKS_DESCRIPTION,
    SOFT_CANCEL_TASK_DESCRIPTION,
    SUBAGENT_SYSTEM_PROMPT,
    get_task_instructions_prompt,
)
from .types import (
    AgentMessage,
    CompiledSubAgent,
    ExecutionMode,
    MessageType,
    SubAgentConfig,
    TaskCharacteristics,
    TaskHandle,
    TaskPriority,
    TaskStatus,
    decide_execution_mode,
)


class SubAgentDeps(BaseModel):
    """Dependencies for the subagent toolset."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    configs: list[Annotated[Any, SkipValidation]] = []
    compiled_agents: dict[str, Annotated[Any, SkipValidation]] = {}
    message_bus: Annotated[Any, SkipValidation] = None
    task_manager: Annotated[Any, SkipValidation] = None
    default_model: str = "openai:gpt-4o"


def _compile_subagent(config: SubAgentConfig, default_model: str) -> CompiledSubAgent:
    """Compile a subagent config into a ready-to-use agent."""
    model = config.get("model", default_model)
    agent_kwargs = config.get("agent_kwargs", {})
    agent: Agent[Any, str] = Agent(
        model,
        system_prompt=config["instructions"],
        **agent_kwargs,
    )
    return CompiledSubAgent(
        name=config["name"],
        description=config["description"],
        agent=agent,
        config=config,
    )


def create_subagent_toolset(
    configs: list[SubAgentConfig] | None = None,
    *,
    default_model: str = "openai:gpt-4o",
    toolset_id: str | None = None,
) -> FunctionToolset[SubAgentDeps]:
    """Create a subagent toolset for task delegation.

    Args:
        configs: List of subagent configurations.
        default_model: Default model for subagents.
        toolset_id: Optional toolset ID.

    Returns:
        FunctionToolset with task, check_task, list_tasks, cancel_task tools.
    """
    toolset: FunctionToolset[SubAgentDeps] = FunctionToolset(id=toolset_id)
    configs = configs or []

    # Pre-compile agents
    _compiled: dict[str, CompiledSubAgent] = {}
    for cfg in configs:
        compiled = _compile_subagent(cfg, default_model)
        _compiled[cfg["name"]] = compiled

    @toolset.tool(description=TASK_TOOL_DESCRIPTION)
    async def task(
        ctx: RunContext[SubAgentDeps],
        subagent_type: str,
        description: str,
        mode: str = "sync",
    ) -> str:
        """Delegate a task to a subagent.

        Args:
            subagent_type: Name of the subagent to use.
            description: Task description with all necessary context.
            mode: Execution mode: "sync", "async", or "auto".
        """
        compiled = _compiled.get(subagent_type) or (
            ctx.deps.compiled_agents.get(subagent_type)
        )
        if not compiled or not compiled.agent:
            available = list(_compiled.keys())
            return f"Error: Unknown subagent '{subagent_type}'. Available: {available}"

        instructions = get_task_instructions_prompt(
            description,
            can_ask_questions=compiled.config.get("can_ask_questions", False),
            max_questions=compiled.config.get("max_questions"),
        )

        if mode == "sync" or (mode == "auto" and not TaskCharacteristics().can_run_independently):
            # Synchronous execution
            try:
                result = await compiled.agent.run(instructions)
                output = getattr(result, "output", None) or str(result)
                return f"[{subagent_type}] {output}"
            except Exception as e:
                return f"[{subagent_type}] Error: {e!s}"
        else:
            # Async execution — return task handle
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            handle = TaskHandle(
                task_id=task_id,
                subagent_name=subagent_type,
                description=description[:200],
            )

            async def _run_async():
                try:
                    result = await compiled.agent.run(instructions)
                    output = getattr(result, "output", None) or str(result)
                    handle.result = str(output)
                    handle.status = TaskStatus.COMPLETED
                except Exception as e:
                    handle.error = str(e)
                    handle.status = TaskStatus.FAILED
                finally:
                    handle.completed_at = datetime.now()

            if ctx.deps.task_manager:
                ctx.deps.task_manager.create_task(task_id, _run_async(), handle)
            else:
                asyncio.create_task(_run_async())

            return f"Task '{task_id}' started in background. Use check_task('{task_id}') to get results."

    @toolset.tool(description=CHECK_TASK_DESCRIPTION)
    async def check_task(ctx: RunContext[SubAgentDeps], task_id: str) -> str:
        """Check status of a background task."""
        if not ctx.deps.task_manager:
            return "Error: Task manager not available."
        handle = ctx.deps.task_manager.get_handle(task_id)
        if not handle:
            return f"Error: Task '{task_id}' not found."
        status = f"Task: {task_id}\nAgent: {handle.subagent_name}\nStatus: {handle.status.value}"
        if handle.result:
            status += f"\nResult: {handle.result}"
        if handle.error:
            status += f"\nError: {handle.error}"
        return status

    @toolset.tool(description=LIST_ACTIVE_TASKS_DESCRIPTION)
    async def list_active_tasks(ctx: RunContext[SubAgentDeps]) -> str:
        """List all active background tasks."""
        if not ctx.deps.task_manager:
            return "No task manager available."
        active = ctx.deps.task_manager.list_active_tasks()
        if not active:
            return "No active tasks."
        lines = []
        for tid in active:
            handle = ctx.deps.task_manager.get_handle(tid)
            if handle:
                lines.append(f"- {tid}: {handle.subagent_name} ({handle.status.value})")
        return "\n".join(lines) if lines else "No active tasks."

    @toolset.tool(description=SOFT_CANCEL_TASK_DESCRIPTION)
    async def cancel_task(ctx: RunContext[SubAgentDeps], task_id: str) -> str:
        """Cancel a background task."""
        if not ctx.deps.task_manager:
            return "Error: Task manager not available."
        success = await ctx.deps.task_manager.hard_cancel(task_id)
        if success:
            return f"Task '{task_id}' cancelled."
        return f"Error: Task '{task_id}' not found or already completed."

    return toolset
