from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    title: str = "Investigation Report"
    format: str  # "html" | "pdf" | "docx" | "pptx"
    include_claims: bool = True
    include_limitations: bool = True
    include_evidence_appendix: bool = False  # later


class ExportResult(BaseModel):
    format: str
    filename: str
    mime_type: str
    bytes_len: int
    artifact_id: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
