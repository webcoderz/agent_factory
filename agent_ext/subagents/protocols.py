"""Protocols for subagent dependencies.

Define the interface that dependencies must implement to work with
the subagent toolset.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .message_bus import InMemoryMessageBus, TaskManager
from .registry import DynamicAgentRegistry, SubagentRegistry
from .types import CompiledSubAgent, SubAgentConfig


@runtime_checkable
class SubAgentDepsProtocol(Protocol):
    """Protocol for dependencies that support subagent operations.

    Any deps object passed to a subagent-aware agent must implement
    this protocol (or a subset of it via duck typing).
    """

    @property
    def subagent_configs(self) -> list[SubAgentConfig]:
        """List of available subagent configurations."""
        ...

    @property
    def compiled_agents(self) -> dict[str, CompiledSubAgent]:
        """Pre-compiled subagent instances."""
        ...

    @property
    def message_bus(self) -> InMemoryMessageBus:
        """Message bus for inter-agent communication."""
        ...

    @property
    def task_manager(self) -> TaskManager:
        """Task manager for background task lifecycle."""
        ...

    @property
    def dynamic_registry(self) -> DynamicAgentRegistry | None:
        """Optional dynamic agent registry for runtime agent creation."""
        ...
