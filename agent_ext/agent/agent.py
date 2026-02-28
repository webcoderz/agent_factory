"""AgentPatterns — fully-wired pydantic-ai Agent with all subsystems.

Inherits from pydantic-ai ``Agent`` and auto-wires middleware, memory,
and any combination of toolsets (console, RLM, database, subagents, todo).

Example::

    from agent_ext.agent import AgentPatterns
    from agent_ext.backends import LocalFilesystemBackend
    from agent_ext.backends.console import ConsoleDeps

    agent = AgentPatterns(
        "openai:gpt-4o",
        instructions="You are a helpful coding assistant.",
        toolsets=["console", "todo"],
    )

    # Run with deps
    result = await agent.run(
        "List files in the current directory",
        deps=ConsoleDeps(backend=LocalFilesystemBackend(root=".", allow_write=True)),
    )
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent

from ..memory.base import MemoryManager
from .memory_adapter import build_history_processor

OutputT = TypeVar("OutputT", str, BaseModel)


# ---------------------------------------------------------------------------
# Toolset factory registry
# ---------------------------------------------------------------------------


def _get_toolset_factory(name: str) -> Any:
    """Lazy-load a toolset factory by name."""
    factories = {
        "console": ("agent_ext.backends.console", "create_console_toolset"),
        "rlm": ("agent_ext.rlm.toolset", "create_rlm_toolset"),
        "database": ("agent_ext.database.toolset", "create_database_toolset"),
        "subagents": ("agent_ext.subagents.toolset", "create_subagent_toolset"),
        "todo": ("agent_ext.todo.pai_toolset", "create_todo_toolset"),
    }
    if name not in factories:
        raise ValueError(f"Unknown toolset: {name!r}. Available: {sorted(factories.keys())}")
    mod_path, attr = factories[name]
    import importlib

    mod = importlib.import_module(mod_path)
    return getattr(mod, attr)


class AgentPatterns(Agent):
    """Pydantic-AI Agent with agent_patterns subsystems wired in.

    Pass toolset names as strings (auto-created) or FunctionToolset instances.
    Middleware and memory are auto-integrated.

    Args:
        model: Model name (e.g. ``"openai:gpt-4o"``).
        instructions: System prompt.
        toolsets: List of toolset names (``"console"``, ``"rlm"``, ``"database"``,
            ``"subagents"``, ``"todo"``) or FunctionToolset instances.
        middleware: List of ``AgentMiddleware`` instances for the hook chain.
        memory: ``MemoryManager`` instance (SlidingWindowMemory, SummarizingMemory).
        output_type: Pydantic model for structured output (default: ``str``).
        **kwargs: Additional args passed to ``pydantic_ai.Agent``.

    Example::

        # Kitchen-sink agent with everything
        agent = AgentPatterns(
            "openai:gpt-4o",
            instructions="You are a full-stack AI assistant.",
            toolsets=["console", "rlm", "database", "todo"],
            memory=SlidingWindowMemory(max_messages=50),
        )

        # Minimal agent with just console tools
        agent = AgentPatterns(
            "openai:gpt-4o",
            toolsets=["console"],
        )
    """

    def __init__(
        self,
        model: str,
        *,
        instructions: str | None = None,
        toolsets: list[str | Any] | None = None,
        middleware: list[Any] | None = None,
        memory: MemoryManager | None = None,
        output_type: type = str,
        **kwargs: Any,
    ) -> None:
        # Resolve toolsets: strings become factory calls, objects pass through
        resolved_toolsets: list[Any] = []
        for ts in toolsets or []:
            if isinstance(ts, str):
                factory = _get_toolset_factory(ts)
                resolved_toolsets.append(factory())
            else:
                resolved_toolsets.append(ts)

        # Wire memory as history processor
        history_processors = list(kwargs.pop("history_processors", []))
        if memory is not None:
            history_processors.insert(0, build_history_processor(memory))

        # Store for post-run checkpoint
        self._ap_memory = memory
        self._ap_middleware = middleware or []

        super().__init__(
            model,
            output_type=output_type,
            instructions=instructions or "",
            toolsets=resolved_toolsets or None,
            history_processors=history_processors or None,
            **kwargs,
        )

    # -- Convenience factory methods ----------------------------------------

    @classmethod
    def with_console(
        cls,
        model: str = "openai:gpt-4o",
        *,
        instructions: str = "You are a helpful coding assistant with filesystem access.",
        memory: MemoryManager | None = None,
        **kwargs: Any,
    ) -> AgentPatterns:
        """Create an agent with console tools (ls, read, write, edit, grep, execute)."""
        return cls(model, instructions=instructions, toolsets=["console"], memory=memory, **kwargs)

    @classmethod
    def with_rlm(
        cls,
        model: str = "openai:gpt-4o",
        *,
        instructions: str = "You analyze data by writing Python code. Use execute_code to explore the context variable.",
        sub_model: str | None = None,
        memory: MemoryManager | None = None,
        **kwargs: Any,
    ) -> AgentPatterns:
        """Create an agent with RLM code execution tools."""
        from ..rlm.toolset import create_rlm_toolset

        rlm_ts = create_rlm_toolset(sub_model=sub_model)
        return cls(model, instructions=instructions, toolsets=[rlm_ts], memory=memory, **kwargs)

    @classmethod
    def with_database(
        cls,
        model: str = "openai:gpt-4o",
        *,
        instructions: str = "You help users query and understand databases. Use the database tools to explore schemas and run queries.",
        memory: MemoryManager | None = None,
        **kwargs: Any,
    ) -> AgentPatterns:
        """Create an agent with database query tools."""
        return cls(model, instructions=instructions, toolsets=["database"], memory=memory, **kwargs)

    @classmethod
    def with_all(
        cls,
        model: str = "openai:gpt-4o",
        *,
        instructions: str = "You are a powerful AI assistant with access to filesystem, code execution, database queries, and task management.",
        memory: MemoryManager | None = None,
        **kwargs: Any,
    ) -> AgentPatterns:
        """Create an agent with ALL available toolsets."""
        return cls(
            model,
            instructions=instructions,
            toolsets=["console", "rlm", "database", "todo"],
            memory=memory,
            **kwargs,
        )
