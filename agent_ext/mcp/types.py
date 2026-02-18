from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

Json = Dict[str, Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: Json = field(default_factory=dict)
    output_schema: Json = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCall:
    tool: str
    args: Json
    call_id: str


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    ok: bool
    result: Any = None
    error: Optional[str] = None
