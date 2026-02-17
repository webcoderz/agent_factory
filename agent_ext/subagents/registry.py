from __future__ import annotations
from typing import Dict

from .base import Subagent


class SubagentRegistry:
    def __init__(self):
        self._agents: Dict[str, Subagent] = {}

    def register(self, agent: Subagent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> Subagent:
        return self._agents[name]

    def list(self) -> list[str]:
        return sorted(self._agents.keys())
