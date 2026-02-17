"""
Run context and shared types for agent_patterns.
Named run_context to avoid shadowing the stdlib 'types' module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Protocol, Sequence
from pydantic import BaseModel


class Cache(Protocol):
    def get(self, key: str) -> Any: ...
    def set(self, key: str, value: Any, ttl_s: Optional[int] = None) -> None: ...


class Logger(Protocol):
    def info(self, msg: str, **kwargs: Any) -> None: ...
    def warning(self, msg: str, **kwargs: Any) -> None: ...
    def error(self, msg: str, **kwargs: Any) -> None: ...


class ArtifactStore(Protocol):
    def put_bytes(self, content: bytes, *, metadata: Dict[str, Any]) -> str: ...
    def get_bytes(self, artifact_id: str) -> bytes: ...
    def put_json(self, obj: Dict[str, Any], *, metadata: Dict[str, Any]) -> str: ...
    def get_json(self, artifact_id: str) -> Dict[str, Any]: ...


class Policy(BaseModel):
    # Expand as needed (gov/enterprise mode, redaction level, etc.)
    allow_tools: bool = True
    allow_exec: bool = False
    allow_fs_write: bool = False
    max_tool_calls: int = 30
    max_runtime_s: int = 60
    redaction_level: str = "none"  # none|basic|strict


@dataclass
class RunContext:
    case_id: str
    session_id: str
    user_id: str

    policy: Policy
    cache: Cache
    logger: Logger
    artifacts: ArtifactStore

    trace_id: str = ""
    tags: Dict[str, Any] = field(default_factory=dict)

    # optional: injected subsystems (filled by composition root)
    skills: Any = None
    backends: Any = None
    subagents: Any = None
    memory: Any = None
    rlm: Any = None
    todo: Any = None  # TodoToolset for task CRUD


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: Dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    name: str
    ok: bool
    result: Any
    error: Optional[str] = None
