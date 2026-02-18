from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple

Json = Dict[str, Any]


@dataclass(frozen=True)
class Capability:
    """
    Declares what a component can do.
    Example tags: "plan", "ocr", "memory", "search_repo", "patch", "gates", "summarize"
    """
    name: str
    tags: Tuple[str, ...]
    cost_hint: int = 1              # rough relative cost
    quality_hint: float = 0.5       # rough prior
    requires_model: bool = False


class Component(Protocol):
    """
    A runnable building block: takes ctx + state; returns updated state.
    """
    capability: Capability

    async def run(self, ctx, state: Json) -> Json: ...


@dataclass(frozen=True)
class StepSpec:
    component_name: str
    input_keys: Tuple[str, ...] = ()
    output_key: Optional[str] = None
    meta: Json = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowSpec:
    """
    A workflow is a DAG in disguise (for now sequence; can grow to DAG later).
    """
    name: str
    steps: Tuple[StepSpec, ...]
    meta: Json = field(default_factory=dict)


@dataclass(frozen=True)
class TaskRequest:
    text: str
    task_type: str = "general"              # e.g. "ocr", "code_change", "research"
    hints: Tuple[str, ...] = ()             # e.g. ("needs_ocr", "needs_memory")
    constraints: Json = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    workflow_name: str
    outputs: Json
    metrics: Json
    trace: List[Json]                       # per-step trace for learning/debug
