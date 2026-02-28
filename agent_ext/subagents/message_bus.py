"""Message bus for inter-agent communication.

Provides in-memory message passing between parent agents and subagents
with request-response correlation (ask/answer pattern).
"""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .types import AgentMessage, MessageType, TaskHandle, TaskStatus


@dataclass
class InMemoryMessageBus:
    """In-memory message bus using asyncio queues.

    Suitable for single-process applications.  For distributed systems,
    swap with a Redis-based implementation.
    """

    _queues: dict[str, asyncio.Queue[AgentMessage]] = field(default_factory=dict)
    _pending_questions: dict[str, asyncio.Future[AgentMessage]] = field(default_factory=dict)
    _handlers: list[Callable[[AgentMessage], Awaitable[None]]] = field(default_factory=list)

    # -- send / receive -----------------------------------------------------

    async def send(self, message: AgentMessage) -> None:
        """Send a message to a specific agent."""
        if message.receiver not in self._queues:
            raise KeyError(f"Agent '{message.receiver}' is not registered")
        await self._queues[message.receiver].put(message)
        for handler in self._handlers:
            try:
                await handler(message)
            except Exception:
                pass

    async def ask(
        self,
        sender: str,
        receiver: str,
        question: Any,
        task_id: str,
        timeout: float = 30.0,
    ) -> AgentMessage:
        """Send a question and wait for a response (request-response pattern)."""
        if receiver not in self._queues:
            raise KeyError(f"Agent '{receiver}' is not registered")

        correlation_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        response_future: asyncio.Future[AgentMessage] = loop.create_future()
        self._pending_questions[correlation_id] = response_future

        try:
            msg = AgentMessage(
                type=MessageType.QUESTION,
                sender=sender,
                receiver=receiver,
                payload=question,
                task_id=task_id,
                correlation_id=correlation_id,
            )
            await self.send(msg)
            return await asyncio.wait_for(response_future, timeout=timeout)
        finally:
            self._pending_questions.pop(correlation_id, None)

    async def answer(self, original: AgentMessage, answer_payload: Any) -> None:
        """Answer a previously received question."""
        if original.sender not in self._queues:
            raise KeyError(f"Agent '{original.sender}' is not registered")

        response = AgentMessage(
            type=MessageType.ANSWER,
            sender=original.receiver,
            receiver=original.sender,
            payload=answer_payload,
            task_id=original.task_id,
            correlation_id=original.correlation_id,
        )

        if original.correlation_id and original.correlation_id in self._pending_questions:
            future = self._pending_questions[original.correlation_id]
            if not future.done():
                future.set_result(response)
        else:
            await self.send(response)

    # -- registration -------------------------------------------------------

    def register_agent(self, agent_id: str) -> asyncio.Queue[AgentMessage]:
        """Register an agent to receive messages."""
        if agent_id in self._queues:
            raise ValueError(f"Agent '{agent_id}' is already registered")
        queue: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._queues[agent_id] = queue
        return queue

    def unregister_agent(self, agent_id: str) -> None:
        self._queues.pop(agent_id, None)

    def is_registered(self, agent_id: str) -> bool:
        return agent_id in self._queues

    def registered_agents(self) -> list[str]:
        return list(self._queues.keys())

    # -- handlers -----------------------------------------------------------

    def add_handler(self, handler: Callable[[AgentMessage], Awaitable[None]]) -> None:
        self._handlers.append(handler)

    def remove_handler(self, handler: Callable[[AgentMessage], Awaitable[None]]) -> None:
        if handler in self._handlers:
            self._handlers.remove(handler)

    # -- drain --------------------------------------------------------------

    async def get_messages(self, agent_id: str, timeout: float = 0.0) -> list[AgentMessage]:
        """Get pending messages for an agent (non-blocking)."""
        if agent_id not in self._queues:
            raise KeyError(f"Agent '{agent_id}' is not registered")
        queue = self._queues[agent_id]
        messages: list[AgentMessage] = []
        if timeout > 0 and queue.empty():
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=timeout)
                messages.append(msg)
            except asyncio.TimeoutError:
                return messages
        while not queue.empty():
            try:
                messages.append(queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return messages


def create_message_bus(backend: str = "memory", **kwargs: Any) -> InMemoryMessageBus:
    """Factory for message bus implementations."""
    if backend == "memory":
        return InMemoryMessageBus()
    raise ValueError(f"Unknown message bus backend: {backend}")


# ---------------------------------------------------------------------------
# Task manager
# ---------------------------------------------------------------------------

@dataclass
class TaskManager:
    """Manages background tasks: creation, status, soft/hard cancellation."""

    tasks: dict[str, asyncio.Task[Any]] = field(default_factory=dict)
    handles: dict[str, TaskHandle] = field(default_factory=dict)
    message_bus: InMemoryMessageBus = field(default_factory=InMemoryMessageBus)
    _cancel_events: dict[str, asyncio.Event] = field(default_factory=dict)

    def create_task(
        self,
        task_id: str,
        coro: Any,
        handle: TaskHandle,
    ) -> asyncio.Task[Any]:
        """Create and track a new background task."""
        task = asyncio.create_task(coro)
        self.tasks[task_id] = task
        self.handles[task_id] = handle
        self._cancel_events[task_id] = asyncio.Event()
        handle.status = TaskStatus.RUNNING
        handle.started_at = datetime.now()
        return task

    def get_handle(self, task_id: str) -> TaskHandle | None:
        return self.handles.get(task_id)

    def get_cancel_event(self, task_id: str) -> asyncio.Event | None:
        return self._cancel_events.get(task_id)

    async def soft_cancel(self, task_id: str) -> bool:
        """Cooperative cancellation via event flag."""
        if task_id not in self._cancel_events:
            return False
        self._cancel_events[task_id].set()
        handle = self.handles.get(task_id)
        if handle and self.message_bus.is_registered(handle.subagent_name):
            try:
                await self.message_bus.send(AgentMessage(
                    type=MessageType.CANCEL_REQUEST,
                    sender="task_manager",
                    receiver=handle.subagent_name,
                    payload={"reason": "soft_cancel"},
                    task_id=task_id,
                ))
            except KeyError:
                pass
        return True

    async def hard_cancel(self, task_id: str) -> bool:
        """Immediately cancel a task."""
        if task_id not in self.tasks:
            return False
        task = self.tasks[task_id]
        if not task.done():
            task.cancel()
        handle = self.handles.get(task_id)
        if handle:
            handle.status = TaskStatus.CANCELLED
            handle.completed_at = datetime.now()
        return True

    def cleanup_task(self, task_id: str) -> None:
        self.tasks.pop(task_id, None)
        self._cancel_events.pop(task_id, None)

    def list_active_tasks(self) -> list[str]:
        return [tid for tid, t in self.tasks.items() if not t.done()]
