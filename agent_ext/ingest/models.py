from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agent_ext.evidence.models import Evidence


class DocumentInput(BaseModel):
    """
    A single item to ingest. Backed by an artifact id or an accessible path.
    Prefer artifact ids for auditability.
    """

    artifact_id: str | None = None
    path: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PageImage(BaseModel):
    page_index: int
    image_artifact_id: str
    width: int | None = None
    height: int | None = None


class OCRSpan(BaseModel):
    text: str
    bbox: tuple[int, int, int, int] | None = None  # x1,y1,x2,y2
    confidence: float = 0.7


class OCRPage(BaseModel):
    page_index: int
    spans: list[OCRSpan] = Field(default_factory=list)
    full_text: str = ""
    engine: str = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PageOCRElement(BaseModel):
    """Single element on a page (table, paragraph, image description, etc.) for structured vision OCR."""

    element_type: str = ""
    element_content: str = ""


class PageOCROutput(BaseModel):
    """
    Structured output from a vision/LLM OCR agent per page.
    Use with PydanticAIAgentBase[PageOCROutput] for schema-validated OCR (see README §10).
    """

    file_type: str = ""
    file_content_md: str = ""
    file_elements: list[PageOCRElement] = Field(default_factory=list)


class IngestResult(BaseModel):
    """
    Primary outputs for the rest of your system:
    - per-page OCR
    - Evidence chunks (normalized)
    """

    doc_artifact_id: str
    page_images: list[PageImage] = Field(default_factory=list)
    ocr_pages: list[OCRPage] = Field(default_factory=list)
    evidence_chunks: list[Evidence] = Field(default_factory=list)
