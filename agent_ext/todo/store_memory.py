from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from agent_ext.todo.models import Task, TaskCreate, TaskPatch, TaskQuery, now_utc


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._tasks: Dict[str, Task] = {}

    async def create_task(self, data: TaskCreate) -> Task:
        tid = uuid.uuid4().hex
        t = Task(
            id=tid,
            title=data.title,
            description=data.description,
            priority=data.priority,
            parent_id=data.parent_id,
            depends_on=list(dict.fromkeys(data.depends_on)),
            tags=list(dict.fromkeys(data.tags)),
            meta=data.meta,
            case_id=data.case_id,
            session_id=data.session_id,
            user_id=data.user_id,
        )
        self._tasks[tid] = t
        return t

    async def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    async def list_tasks(self, q: TaskQuery) -> List[Task]:
        items = list(self._tasks.values())

        def match(t: Task) -> bool:
            if q.case_id and t.case_id != q.case_id:
                return False
            if q.session_id and t.session_id != q.session_id:
                return False
            if q.user_id and t.user_id != q.user_id:
                return False
            if q.status and t.status != q.status:
                return False
            if q.parent_id is not None and t.parent_id != q.parent_id:
                return False
            if q.tag and q.tag not in t.tags:
                return False
            if q.text:
                hay = f"{t.title}\n{t.description or ''}".lower()
                if q.text.lower() not in hay:
                    return False
            return True

        filtered = [t for t in items if match(t)]
        filtered.sort(key=lambda x: (x.priority, x.created_at))
        return filtered[q.offset : q.offset + q.limit]

    async def update_task(self, task_id: str, patch: TaskPatch) -> Optional[Task]:
        t = self._tasks.get(task_id)
        if not t:
            return None

        data = t.model_dump()
        p = patch.model_dump(exclude_unset=True)

        # merge, preserving list uniqueness
        for k, v in p.items():
            if k in {"depends_on", "tags", "artifact_ids", "evidence_ids"} and v is not None:
                data[k] = list(dict.fromkeys(v))
            else:
                data[k] = v

        data["updated_at"] = now_utc()
        nt = Task(**data)
        self._tasks[task_id] = nt
        return nt

    async def delete_task(self, task_id: str) -> bool:
        return self._tasks.pop(task_id, None) is not None

    async def add_dependency(self, task_id: str, depends_on_task_id: str) -> Optional[Task]:
        t = self._tasks.get(task_id)
        if not t:
            return None
        deps = list(dict.fromkeys([*t.depends_on, depends_on_task_id]))
        return await self.update_task(task_id, TaskPatch(depends_on=deps))

    async def add_subtask(self, parent_id: str, data: TaskCreate) -> Task:
        # Inherit scope automatically unless explicitly overridden
        parent = await self.get_task(parent_id)
        if not parent:
            raise ValueError(f"Parent task not found: {parent_id}")

        merged = TaskCreate(
            **data.model_dump(),
            parent_id=parent_id,
            case_id=data.case_id or parent.case_id,
            session_id=data.session_id or parent.session_id,
            user_id=data.user_id or parent.user_id,
        )
        return await self.create_task(merged)
    async def next_runnable_tasks(self, q: TaskQuery) -> List[Task]:
        """
        Runnable = status in {pending, in_progress} AND all dependencies are done.
        (in_progress included so you can resume partially-run tasks)
        """
        tasks = await self.list_tasks(q)

        # quick lookup
        by_id = {t.id: t for t in tasks}
        done = {"done"}

        def deps_done(t: Task) -> bool:
            for dep_id in t.depends_on:
                dep = self._tasks.get(dep_id) or by_id.get(dep_id)
                if not dep or dep.status not in done:
                    return False
            return True

        runnable = []
        for t in tasks:
            if t.status not in {"pending", "in_progress"}:
                continue
            if deps_done(t):
                runnable.append(t)

        runnable.sort(key=lambda x: (x.priority, x.created_at))
        return runnable[: q.limit]

    async def refresh_blocked_status(self, q: TaskQuery) -> int:
        """
        Optionally keep statuses consistent:
        - if deps not done and task is pending/in_progress => mark blocked
        - if deps done and task is blocked => mark pending
        Returns number of tasks updated.
        """
        tasks = await self.list_tasks(q)
        by_id = {t.id: t for t in self._tasks.values()}
        updated = 0

        def deps_done(t: Task) -> bool:
            for dep_id in t.depends_on:
                dep = by_id.get(dep_id)
                if not dep or dep.status != "done":
                    return False
            return True

        for t in tasks:
            ok = deps_done(t)
            if not ok and t.status in {"pending", "in_progress"}:
                await self.update_task(t.id, TaskPatch(status="blocked"))
                updated += 1
            elif ok and t.status == "blocked":
                await self.update_task(t.id, TaskPatch(status="pending"))
                updated += 1

        return updated