from __future__ import annotations
from typing import Any, Dict, Optional, Protocol
from pydantic import BaseModel


class SubagentResult(BaseModel):
    ok: bool = True
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class Subagent(Protocol):
    name: str
    async def run(self, *, input: Any, metadata: Dict[str, Any]) -> SubagentResult: ...
