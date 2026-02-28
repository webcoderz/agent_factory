"""Type definitions for the subagent system.

Covers messages, task handles, execution modes, and configuration.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict

# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------


class MessageType(StrEnum):
    """Types of messages between agents."""

    TASK_ASSIGNED = "task_assigned"
    TASK_UPDATE = "task_update"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    QUESTION = "question"
    ANSWER = "answer"
    CANCEL_REQUEST = "cancel_request"
    CANCEL_FORCED = "cancel_forced"


class TaskStatus(StrEnum):
    """Status of a background task."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_ANSWER = "waiting_for_answer"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    """Priority levels for background tasks."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


ExecutionMode = Literal["sync", "async", "auto"]


# ---------------------------------------------------------------------------
# Task characteristics (for auto-mode selection)
# ---------------------------------------------------------------------------


@dataclass
class TaskCharacteristics:
    """Characteristics that help decide sync vs async execution.

    Used by ``decide_execution_mode`` to auto-select.
    """

    estimated_complexity: Literal["simple", "moderate", "complex"] = "moderate"
    requires_user_context: bool = False
    is_time_sensitive: bool = False
    can_run_independently: bool = True
    may_need_clarification: bool = False


def decide_execution_mode(
    characteristics: TaskCharacteristics,
    config: SubAgentConfig,
    force_mode: ExecutionMode | None = None,
) -> Literal["sync", "async"]:
    """Decide whether to run sync or async based on task characteristics."""
    if force_mode and force_mode != "auto":
        return force_mode

    config_pref = config.get("preferred_mode", "auto")
    if config_pref != "auto":
        return config_pref  # type: ignore[return-value]

    if characteristics.requires_user_context:
        return "sync"
    if characteristics.may_need_clarification and characteristics.is_time_sensitive:
        return "sync"
    if characteristics.estimated_complexity == "complex" and characteristics.can_run_independently:
        return "async"
    if characteristics.estimated_complexity == "simple":
        return "sync"
    if characteristics.can_run_independently:
        return "async"
    return "sync"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class SubAgentConfig(TypedDict, total=False):
    """Configuration for a subagent.

    Required: name, description, instructions.
    Optional: model, toolsets, execution preferences, etc.
    """

    name: str
    description: str
    instructions: str
    model: NotRequired[str]
    can_ask_questions: NotRequired[bool]
    max_questions: NotRequired[int]
    preferred_mode: NotRequired[ExecutionMode]
    typical_complexity: NotRequired[Literal["simple", "moderate", "complex"]]
    typically_needs_context: NotRequired[bool]
    toolsets: NotRequired[list[Any]]
    agent_kwargs: NotRequired[dict[str, Any]]
    context_files: NotRequired[list[str]]
    extra: NotRequired[dict[str, Any]]


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


def _generate_message_id() -> str:
    return uuid.uuid4().hex


@dataclass
class AgentMessage:
    """Message passed between agents via the message bus."""

    type: MessageType
    sender: str
    receiver: str
    payload: Any
    task_id: str
    id: str = field(default_factory=_generate_message_id)
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: str | None = None


# ---------------------------------------------------------------------------
# Task handle
# ---------------------------------------------------------------------------


@dataclass
class TaskHandle:
    """Handle for managing a background task.

    Returned when a task is started in async mode.
    """

    task_id: str
    subagent_name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: str | None = None
    error: str | None = None
    pending_question: str | None = None


@dataclass
class CompiledSubAgent:
    """A pre-compiled subagent ready for use."""

    name: str
    description: str
    config: SubAgentConfig
    agent: object | None = None
