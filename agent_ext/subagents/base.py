from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel


class SubagentResult(BaseModel):
    ok: bool = True
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = {}


class Subagent(Protocol):
    name: str

    async def run(self, *, input: Any, metadata: dict[str, Any]) -> SubagentResult: ...
