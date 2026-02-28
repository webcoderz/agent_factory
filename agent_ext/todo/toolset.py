from __future__ import annotations

from typing import Any

from agent_ext.todo.events import TaskEvent, TaskEventBus
from agent_ext.todo.models import Task, TaskCreate, TaskPatch, TaskQuery
from agent_ext.todo.store_base import TaskStore


class TodoToolset:
    """
    Provide CRUD + dependency/subtask helpers.
    """

    def __init__(self, store: TaskStore, *, events: TaskEventBus | None = None) -> None:
        self.store = store
        self.events = events

    async def create_task(self, data: TaskCreate) -> Task:
        t = await self.store.create_task(data)
        if self.events:
            await self.events.emit(TaskEvent(name="task_created", task=t, payload={}))
        return t

    async def get_task(self, task_id: str) -> Task | None:
        return await self.store.get_task(task_id)

    async def list_tasks(self, q: TaskQuery) -> list[Task]:
        return await self.store.list_tasks(q)

    async def update_task(self, task_id: str, patch: TaskPatch) -> Task | None:
        t = await self.store.update_task(task_id, patch)
        if t and self.events:
            payload: dict[str, Any] = {"patch": patch.model_dump(exclude_unset=True)}
            name = "task_updated"
            if patch.status == "done":
                name = "task_completed"
            elif patch.status in {"failed", "canceled"}:
                name = "task_terminal"
            await self.events.emit(TaskEvent(name=name, task=t, payload=payload))
        return t

    async def add_dependency(self, task_id: str, depends_on_task_id: str) -> Task | None:
        t = await self.store.add_dependency(task_id, depends_on_task_id)
        if t and self.events:
            await self.events.emit(
                TaskEvent(name="task_updated", task=t, payload={"depends_on_added": depends_on_task_id})
            )
        return t

    async def add_subtask(self, parent_id: str, data: TaskCreate) -> Task:
        t = await self.store.add_subtask(parent_id, data)
        if self.events:
            await self.events.emit(TaskEvent(name="task_created", task=t, payload={"parent_id": parent_id}))
        return t

    async def next_runnable_tasks(self, q: TaskQuery) -> list[Task]:
        return await self.store.next_runnable_tasks(q)

    async def refresh_blocked_status(self, q: TaskQuery) -> int:
        return await self.store.refresh_blocked_status(q)

    async def get_task_tree(self, root_task_id: str, include_rollup: bool = False) -> dict | None:
        return await self.store.get_task_tree(root_task_id, include_rollup=include_rollup)
