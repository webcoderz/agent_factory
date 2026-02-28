from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

InitFn = Callable[[Any], None]  # ctx-like (RunContext)


@dataclass(frozen=True)
class ModuleProvides:
    # Names only; actual registrations happen in init()
    tools: list[str] = field(default_factory=list)
    subagents: list[str] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ModuleSpec:
    name: str
    version: str = "0.1.0"
    description: str = ""
    provides: ModuleProvides = field(default_factory=ModuleProvides)

    # Optional hard requirements (kept simple for now)
    requires_exec: bool = False
    requires_tools: bool = True

    # Called when module is enabled; should mutate ctx by attaching tools/subagents/hooks/etc.
    init: InitFn | None = None


@dataclass
class ModuleState:
    spec: ModuleSpec
    enabled: bool = True
    loaded_from: str = ""  # import path
    meta: dict[str, Any] = field(default_factory=dict)
