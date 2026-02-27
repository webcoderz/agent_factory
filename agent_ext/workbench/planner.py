from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Task:
    id: str
    kind: str               # analyze/search/design/implement/gates/improve
    title: str
    input: Any
    status: str = "pending"  # pending/in_progress/done/failed/cancelled
    meta: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None

    @property
    def elapsed_s(self) -> float | None:
        """Seconds between start and finish (or now if in progress)."""
        if self.started_at is None:
            return None
        end = self.finished_at if self.finished_at is not None else time.time()
        return end - self.started_at


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
                    t.started_at = time.time()
                    return t
            return None

    def normalize_id(self, task_id: str) -> str:
        """Allow 't0004' or '0004' -> 't0004'."""
        s = (task_id or "").strip()
        if s.isdigit():
            return f"t{s}"
        return s if s.startswith("t") else f"t{s}"

    def get_by_id(self, task_id: str) -> Optional[Task]:
        """Return task by id (accepts t0004 or 0004), or None."""
        tid = self.normalize_id(task_id)
        return next((t for t in self._tasks if t.id == tid), None)

    async def cancel_by_id(self, task_id: str) -> Optional[bool]:
        """Cancel a task by id. Returns True if it was pending and is now cancelled, False if found but not pending, None if not found. Thread-safe."""
        tid = self.normalize_id(task_id)
        async with self._lock:
            for t in self._tasks:
                if t.id == tid:
                    if t.status == "pending":
                        t.status = "cancelled"
                        t.finished_at = time.time()
                        return True
                    return False
            return None

    async def retry_by_id(self, task_id: str) -> Optional[bool]:
        """Reset a failed/cancelled task to pending. Returns True if reset, False if not in retryable state, None if not found."""
        tid = self.normalize_id(task_id)
        async with self._lock:
            for t in self._tasks:
                if t.id == tid:
                    if t.status in ("failed", "cancelled"):
                        t.status = "pending"
                        t.started_at = None
                        t.finished_at = None
                        return True
                    return False
            return None

    async def retry_all_failed(self) -> int:
        """Reset all failed tasks to pending. Returns count."""
        count = 0
        async with self._lock:
            for t in self._tasks:
                if t.status == "failed":
                    t.status = "pending"
                    t.started_at = None
                    t.finished_at = None
                    count += 1
        return count
