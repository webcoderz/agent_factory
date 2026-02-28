from __future__ import annotations

import uuid

from agent_ext.todo.models import Task, TaskCreate, TaskPatch, TaskQuery, now_utc


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

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

    async def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    async def list_tasks(self, q: TaskQuery) -> list[Task]:
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

    async def update_task(self, task_id: str, patch: TaskPatch) -> Task | None:
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

    async def add_dependency(self, task_id: str, depends_on_task_id: str) -> Task | None:
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

    async def next_runnable_tasks(self, q: TaskQuery) -> list[Task]:
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

    async def get_task_tree(self, root_task_id: str, include_rollup: bool = False) -> dict | None:
        root = await self.get_task(root_task_id)
        if not root:
            return None

        # build adjacency by parent_id
        children_by_parent: dict[str, list[Task]] = {}
        for t in self._tasks.values():
            if t.parent_id:
                children_by_parent.setdefault(t.parent_id, []).append(t)

        for k in children_by_parent:
            children_by_parent[k].sort(key=lambda x: (x.priority, x.created_at))

        by_id = {t.id: t for t in self._tasks.values()}

        def deps_blockers(t: Task) -> list[str]:
            blockers = []
            for dep_id in t.depends_on:
                dep = by_id.get(dep_id)
                if not dep or dep.status != "done":
                    blockers.append(dep_id)
            return blockers

        def build(node: Task) -> dict:
            kids = children_by_parent.get(node.id, [])
            out = {"task": node.model_dump(), "children": [build(c) for c in kids]}

            if include_rollup:
                blocked_by = deps_blockers(node)
                is_terminal = node.status in {"done", "canceled", "failed"}
                is_runnable = (node.status in {"pending", "in_progress"}) and not blocked_by

                # subtree stats
                totals = {
                    "total": 1,
                    "done": 1 if node.status == "done" else 0,
                    "blocked": 1 if (node.status == "blocked" or blocked_by) else 0,
                    "failed": 1 if node.status == "failed" else 0,
                    "open": 0 if is_terminal else 1,
                }

                for ch in out["children"]:
                    r = ch.get("rollup") or {}
                    totals["total"] += r.get("total", 0)
                    totals["done"] += r.get("done", 0)
                    totals["blocked"] += r.get("blocked", 0)
                    totals["failed"] += r.get("failed", 0)
                    totals["open"] += r.get("open", 0)

                progress_pct = (totals["done"] / max(1, totals["total"])) * 100.0

                out["rollup"] = {
                    "is_runnable": is_runnable,
                    "blocked_by": blocked_by,
                    "subtree_total": totals["total"],
                    "subtree_done": totals["done"],
                    "subtree_open": totals["open"],
                    "subtree_blocked": totals["blocked"],
                    "subtree_failed": totals["failed"],
                    "progress_pct": round(progress_pct, 2),
                }

            return out

        return build(root)
