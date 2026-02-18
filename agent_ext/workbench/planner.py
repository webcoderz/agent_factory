from __future__ import annotations

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
    def __init__(self):
        self._tasks: List[Task] = []
        self._seq = 0

    def add(self, kind: str, title: str, input: Any, meta: Optional[Dict[str, Any]] = None) -> Task:
        self._seq += 1
        t = Task(id=f"t{self._seq:04d}", kind=kind, title=title, input=input, meta=meta or {})
        self._tasks.append(t)
        return t

    def list(self) -> List[Task]:
        return list(self._tasks)

    def next_pending(self) -> Optional[Task]:
        for t in self._tasks:
            if t.status == "pending":
                return t
        return None
