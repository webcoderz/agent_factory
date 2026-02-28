from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

TaskStatus = Literal["pending", "in_progress", "blocked", "done", "canceled", "failed"]


def now_utc() -> datetime:
    return datetime.now(UTC)


class Task(BaseModel):
    """
    Planning primitive:
    - supports subtasks (parent_id)
    - supports dependencies (depends_on)
    - supports multi-tenant scoping (case_id/session_id/user_id)
    """

    id: str
    title: str
    description: str | None = None

    status: TaskStatus = "pending"
    priority: int = 50

    parent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    # Multi-tenant / scoping
    case_id: str | None = None
    session_id: str | None = None
    user_id: str | None = None

    # Links to your audit/evidence world
    artifact_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    # Generic metadata for planner/router/judge notes
    meta: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    priority: int = 50
    parent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    case_id: str | None = None
    session_id: str | None = None
    user_id: str | None = None


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: int | None = None
    parent_id: str | None = None

    depends_on: list[str] | None = None
    tags: list[str] | None = None

    artifact_ids: list[str] | None = None
    evidence_ids: list[str] | None = None
    meta: dict[str, Any] | None = None


class TaskQuery(BaseModel):
    """
    Filter used by list/search.
    """

    case_id: str | None = None
    session_id: str | None = None
    user_id: str | None = None

    status: TaskStatus | None = None
    parent_id: str | None = None
    tag: str | None = None

    text: str | None = None  # simple substring match for title/description
    limit: int = 200
    offset: int = 0
