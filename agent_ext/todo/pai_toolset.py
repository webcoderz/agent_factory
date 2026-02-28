"""Todo FunctionToolset factory for pydantic-ai agents.

Example::

    from pydantic_ai import Agent
    from agent_ext.todo import create_todo_toolset, TodoDeps, InMemoryTaskStore

    store = InMemoryTaskStore()
    toolset = create_todo_toolset()
    agent = Agent("openai:gpt-4o", toolsets=[toolset])

    deps = TodoDeps(store=store, case_id="case-1")
    result = await agent.run("Create a task to review the PR", deps=deps)
"""
from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, SkipValidation
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from .models import Task, TaskCreate, TaskPatch, TaskQuery, TaskStatus
from .store_base import TaskStore

TODO_SYSTEM_PROMPT = """
## Todo Tools

You can manage tasks using the following tools:
* `create_task` — create a new task
* `list_tasks` — list tasks with optional filtering
* `update_task` — update a task's status or details
* `complete_task` — mark a task as done
"""


class TodoDeps(BaseModel):
    """Dependencies for the todo toolset."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    store: Annotated[Any, SkipValidation]  # TaskStore
    case_id: str | None = None
    session_id: str | None = None
    user_id: str | None = None


def create_todo_toolset(*, toolset_id: str | None = None) -> FunctionToolset[TodoDeps]:
    """Create a todo toolset for AI agents.

    Returns:
        FunctionToolset with create_task, list_tasks, update_task, complete_task.
    """
    toolset: FunctionToolset[TodoDeps] = FunctionToolset(id=toolset_id)

    @toolset.tool
    async def create_task(
        ctx: RunContext[TodoDeps],
        title: str,
        description: str = "",
        priority: int = 50,
        tags: str = "",
    ) -> str:
        """Create a new task.

        Args:
            title: Task title.
            description: Optional description.
            priority: Priority (0-100, lower = higher priority).
            tags: Comma-separated tags.
        """
        data = TaskCreate(
            title=title,
            description=description or None,
            priority=priority,
            tags=[t.strip() for t in tags.split(",") if t.strip()],
            case_id=ctx.deps.case_id,
            session_id=ctx.deps.session_id,
            user_id=ctx.deps.user_id,
        )
        task = await ctx.deps.store.create_task(data)
        return f"Created task '{task.title}' (id: {task.id})"

    @toolset.tool
    async def list_tasks(
        ctx: RunContext[TodoDeps],
        status: str | None = None,
        limit: int = 20,
    ) -> str:
        """List tasks with optional status filter.

        Args:
            status: Filter by status (pending, in_progress, done, blocked, failed).
            limit: Max results.
        """
        q = TaskQuery(
            case_id=ctx.deps.case_id,
            session_id=ctx.deps.session_id,
            user_id=ctx.deps.user_id,
            status=status if status in ("pending", "in_progress", "done", "blocked", "canceled", "failed") else None,
            limit=limit,
        )
        tasks = await ctx.deps.store.list_tasks(q)
        if not tasks:
            return "No tasks found."
        lines = []
        for t in tasks:
            lines.append(f"[{t.id[:8]}] {t.title} (status={t.status}, priority={t.priority})")
        return "\n".join(lines)

    @toolset.tool
    async def update_task(
        ctx: RunContext[TodoDeps],
        task_id: str,
        status: str | None = None,
        title: str | None = None,
        description: str | None = None,
    ) -> str:
        """Update a task's status or details.

        Args:
            task_id: The task ID.
            status: New status.
            title: New title.
            description: New description.
        """
        patch = TaskPatch(
            status=status if status else None,  # type: ignore[arg-type]
            title=title,
            description=description,
        )
        task = await ctx.deps.store.update_task(task_id, patch)
        if not task:
            return f"Task '{task_id}' not found."
        return f"Updated task '{task.title}' to status={task.status}"

    @toolset.tool
    async def complete_task(ctx: RunContext[TodoDeps], task_id: str) -> str:
        """Mark a task as done.

        Args:
            task_id: The task ID to complete.
        """
        task = await ctx.deps.store.update_task(task_id, TaskPatch(status="done"))
        if not task:
            return f"Task '{task_id}' not found."
        return f"Completed task '{task.title}'"

    return toolset
