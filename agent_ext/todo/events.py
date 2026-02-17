from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol

import httpx

from agent_ext.todo.models import Task


TaskEventName = str  # e.g., "task_created", "task_updated", "task_completed"


@dataclass(frozen=True)
class TaskEvent:
    name: TaskEventName
    task: Task
    payload: Dict[str, Any]


class TaskEventBus(Protocol):
    async def emit(self, event: TaskEvent) -> None: ...


class InProcessEventBus:
    def __init__(self) -> None:
        self._handlers: Dict[TaskEventName, List[Callable[[TaskEvent], Awaitable[None]]]] = {}

    def on(self, name: TaskEventName, handler: Callable[[TaskEvent], Awaitable[None]]) -> None:
        self._handlers.setdefault(name, []).append(handler)

    async def emit(self, event: TaskEvent) -> None:
        handlers = self._handlers.get(event.name, [])
        # run concurrently; do not fail task operations due to observer errors
        await asyncio.gather(*(h(event) for h in handlers), return_exceptions=True)


class WebhookEventBus:
    """
    Sends task events to one or more webhook URLs.
    """
    def __init__(self, urls: List[str], *, timeout_s: float = 10.0, headers: Optional[Dict[str, str]] = None) -> None:
        self.urls = urls
        self.timeout_s = timeout_s
        self.headers = headers or {}

    async def emit(self, event: TaskEvent) -> None:
        data = {
            "name": event.name,
            "task": event.task.model_dump(),
            "payload": event.payload,
        }
        async with httpx.AsyncClient(timeout=self.timeout_s, headers=self.headers) as client:
            # fire-and-forget-ish; still await for observability, but ignore failures
            reqs = [client.post(url, json=data) for url in self.urls]
            await asyncio.gather(*reqs, return_exceptions=True)
