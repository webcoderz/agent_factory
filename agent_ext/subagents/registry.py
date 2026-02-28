"""Subagent registries — static and dynamic.

``SubagentRegistry`` is the simple name→agent map (existing, preserved).
``DynamicAgentRegistry`` adds runtime creation limits, compiled agents, and summaries.
"""

from __future__ import annotations

import builtins
from dataclasses import dataclass, field
from typing import Any, Protocol

from .types import CompiledSubAgent, SubAgentConfig

# ---------------------------------------------------------------------------
# Protocol (what a subagent must look like)
# ---------------------------------------------------------------------------


class SubagentProtocol(Protocol):
    """Minimal subagent interface."""

    name: str

    async def run(self, ctx: Any, *, input: Any, meta: dict[str, Any]) -> Any: ...


# ---------------------------------------------------------------------------
# Static registry (backward-compat)
# ---------------------------------------------------------------------------


class SubagentRegistry:
    """Simple static registry: name → subagent.

    This is the original registry used by the workbench.
    """

    def __init__(self) -> None:
        self._agents: dict[str, Any] = {}

    def register(self, agent: Any) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> Any:
        if name not in self._agents:
            raise KeyError(f"Unknown subagent: {name}")
        return self._agents[name]

    def list(self) -> builtins.list[str]:
        return sorted(self._agents.keys())

    def exists(self, name: str) -> bool:
        return name in self._agents

    def count(self) -> int:
        return len(self._agents)


# ---------------------------------------------------------------------------
# Dynamic registry (parity with subagents-pydantic-ai)
# ---------------------------------------------------------------------------


@dataclass
class DynamicAgentRegistry:
    """Registry for dynamically created agents with limits and compiled agents.

    Supports runtime agent creation, removal, and introspection.
    """

    agents: dict[str, Any] = field(default_factory=dict)
    configs: dict[str, SubAgentConfig] = field(default_factory=dict)
    _compiled: dict[str, CompiledSubAgent] = field(default_factory=dict)
    max_agents: int | None = None

    def register(self, config: SubAgentConfig, agent: Any) -> None:
        name = config["name"]
        if name in self.agents:
            raise ValueError(f"Agent '{name}' already exists")
        if self.max_agents and len(self.agents) >= self.max_agents:
            raise ValueError(
                f"Maximum number of agents ({self.max_agents}) reached. Remove an agent before creating a new one."
            )
        self.agents[name] = agent
        self.configs[name] = config
        self._compiled[name] = CompiledSubAgent(
            name=name,
            description=config["description"],
            agent=agent,
            config=config,
        )

    def get(self, name: str) -> Any | None:
        return self.agents.get(name)

    def get_config(self, name: str) -> SubAgentConfig | None:
        return self.configs.get(name)

    def get_compiled(self, name: str) -> CompiledSubAgent | None:
        return self._compiled.get(name)

    def remove(self, name: str) -> bool:
        if name not in self.agents:
            return False
        del self.agents[name]
        del self.configs[name]
        del self._compiled[name]
        return True

    def list_agents(self) -> list[str]:
        return list(self.agents.keys())

    def list_configs(self) -> list[SubAgentConfig]:
        return list(self.configs.values())

    def list_compiled(self) -> list[CompiledSubAgent]:
        return list(self._compiled.values())

    def exists(self, name: str) -> bool:
        return name in self.agents

    def count(self) -> int:
        return len(self.agents)

    def clear(self) -> None:
        self.agents.clear()
        self.configs.clear()
        self._compiled.clear()

    def get_summary(self) -> str:
        if not self.agents:
            return "No dynamically created agents."
        lines = [f"Dynamic Agents ({len(self.agents)}):"]
        for name, config in self.configs.items():
            model = config.get("model", "default")
            lines.append(f"- {name} [{model}]: {config['description']}")
        return "\n".join(lines)
