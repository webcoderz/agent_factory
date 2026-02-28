from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

TaskStatus = Literal["pending", "running", "done", "failed", "skipped"]
TaskKind = Literal[
    "search",  # web/retrieval (if allowed)
    "browse",  # computer-use (playwright/cdp)
    "ingest_document",  # OCR pipeline
    "analyze",  # reasoning over evidence / RLM
    "extract",  # structured extraction
    "subagent",  # delegate to local/server specialist
    "tool",  # direct tool call
    "synthesize",  # generate narrative/structured report
]

EvidenceKind = Literal[
    "finding",
    "claim",
    "note",
    "validation",
    "web_capture",
    "doc_extract",
    "structured",
    "text",
]


class ResearchBudget(BaseModel):
    max_steps: int = 40
    max_tool_calls: int = 60
    max_runtime_s: int = 180
    max_cost_usd: float | None = None  # optional if you track cost


class ResearchTask(BaseModel):
    id: str
    kind: TaskKind
    goal: str
    query: str | None = None  # for search/browse
    inputs: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    status: TaskStatus = "pending"
    attempts: int = 0
    max_attempts: int = 2
    priority: int = 50  # lower = earlier
    tags: list[str] = Field(default_factory=list)
    error: str | None = None


class ResearchPlan(BaseModel):
    question: str
    tasks: list[ResearchTask] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    """
    Claim ledger entry (atomic statement).
    """

    id: str
    text: str
    confidence: float = 0.7
    citations: list[dict[str, Any]] = Field(default_factory=list)  # store as dicts to avoid tight coupling
    tags: list[str] = Field(default_factory=list)
    derived_from_evidence_ids: list[str] = Field(default_factory=list)


class ResearchOutcome(BaseModel):
    question: str
    answer: str
    structured: dict[str, Any] = Field(default_factory=dict)
    claims: list[Claim] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    steps_taken: int = 0
    plan: ResearchPlan | None = None
