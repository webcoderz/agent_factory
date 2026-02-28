from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    source_id: str  # artifact id / uri / file id
    locator: str  # page:3, line:20-40, bbox:x1,y1,x2,y2, offset:...
    quote: str | None = None  # optional small excerpt
    confidence: float = 0.7


class Provenance(BaseModel):
    produced_by: str  # tool/subagent name
    artifact_ids: list[str] = Field(default_factory=list)
    timestamps: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    kind: str  # "text" | "entity" | "relation" | "finding" | ...
    content: Any
    citations: list[Citation] = Field(default_factory=list)
    provenance: Provenance
    confidence: float = 0.7
    tags: list[str] = Field(default_factory=list)  # pii|sensitive|domain:finance|...
