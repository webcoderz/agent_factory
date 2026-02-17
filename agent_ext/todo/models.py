from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


TaskStatus = Literal["pending", "in_progress", "blocked", "done", "canceled", "failed"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Task(BaseModel):
    """
    Planning primitive:
    - supports subtasks (parent_id)
    - supports dependencies (depends_on)
    - supports multi-tenant scoping (case_id/session_id/user_id)
    """
    id: str
    title: str
    description: Optional[str] = None

    status: TaskStatus = "pending"
    priority: int = 50

    parent_id: Optional[str] = None
    depends_on: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

    # Multi-tenant / scoping
    case_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None

    # Links to your audit/evidence world
    artifact_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)

    # Generic metadata for planner/router/judge notes
    meta: Dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: int = 50
    parent_id: Optional[str] = None
    depends_on: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)

    case_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class TaskPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[int] = None
    parent_id: Optional[str] = None

    depends_on: Optional[List[str]] = None
    tags: Optional[List[str]] = None

    artifact_ids: Optional[List[str]] = None
    evidence_ids: Optional[List[str]] = None
    meta: Optional[Dict[str, Any]] = None


class TaskQuery(BaseModel):
    """
    Filter used by list/search.
    """
    case_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None

    status: Optional[TaskStatus] = None
    parent_id: Optional[str] = None
    tag: Optional[str] = None

    text: Optional[str] = None  # simple substring match for title/description
    limit: int = 200
    offset: int = 0
