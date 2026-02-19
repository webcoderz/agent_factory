from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Task:
    id: str
    kind: str               # analyze/search/design/implement/gates/improve
    title: str
    input: Any
    status: str = "pending" # pending/in_progress/done/failed
    meta: Dict[str, Any] = field(default_factory=dict)


class TaskQueue:
    """Queue of tasks; safe for many concurrent run loops (claim_next_pending is atomic)."""

    def __init__(self) -> None:
        self._tasks: List[Task] = []
        self._seq = 0
        self._lock = asyncio.Lock()

    def add(self, kind: str, title: str, input: Any, meta: Optional[Dict[str, Any]] = None) -> Task:
        self._seq += 1
        t = Task(id=f"t{self._seq:04d}", kind=kind, title=title, input=input, meta=meta or {})
        self._tasks.append(t)
        return t

    def list(self) -> List[Task]:
        return list(self._tasks)

    def next_pending(self) -> Optional[Task]:
        """First pending task (read-only; for display). Use claim_next_pending in run loops."""
        for t in self._tasks:
            if t.status == "pending":
                return t
        return None

    async def claim_next_pending(self) -> Optional[Task]:
        """Atomically take the first pending task and mark in_progress. Safe for many concurrent run loops."""
        async with self._lock:
            for t in self._tasks:
                if t.status == "pending":
                    t.status = "in_progress"
                    return t
            return None
