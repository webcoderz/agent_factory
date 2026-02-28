from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from agent_ext.evidence.models import Citation, Evidence, Provenance
from agent_ext.run_context import RunContext

from .models import OCRPage


class PageExtractor(Protocol):
    name: str

    def extract(self, ctx: RunContext, *, doc_artifact_id: str, pages: list[OCRPage]) -> list[Evidence]: ...


class MarkdownDumpExtractor:
    """
    Produces a straightforward per-page markdown Evidence chunk.
    """

    name = "markdown_dump"

    def extract(self, ctx: RunContext, *, doc_artifact_id: str, pages: list[OCRPage]) -> list[Evidence]:
        out: list[Evidence] = []
        for p in pages:
            cit = Citation(source_id=doc_artifact_id, locator=f"page:{p.page_index}", confidence=0.7)
            out.append(
                Evidence(
                    kind="text",
                    content={"page": p.page_index, "text": p.full_text},
                    citations=[cit],
                    provenance=Provenance(produced_by=self.name, artifact_ids=[doc_artifact_id]),
                    confidence=0.7,
                    tags=["ingest", "ocr"],
                )
            )
        return out


class StructuredModelExtractor:
    """
    Adapter: your team wires this to an LLM call (PydanticAI agent) that returns a specific BaseModel.
    """

    def __init__(self, *, model_type: type[BaseModel], llm_fn):
        self.model_type = model_type
        self.llm_fn = llm_fn
        self.name = f"structured:{model_type.__name__}"

    def extract(self, ctx: RunContext, *, doc_artifact_id: str, pages: list[OCRPage]) -> list[Evidence]:
        # join text for now; you can do page-aware prompting later
        text = "\n\n".join([f"[page {p.page_index}]\n{p.full_text}" for p in pages if p.full_text.strip()])
        obj = self.llm_fn(ctx, text, self.model_type)  # must return an instance of model_type

        cit = Citation(source_id=doc_artifact_id, locator="pages:all", confidence=0.6)
        return [
            Evidence(
                kind="structured",
                content=obj.model_dump(),
                citations=[cit],
                provenance=Provenance(produced_by=self.name, artifact_ids=[doc_artifact_id]),
                confidence=0.75,
                tags=["ingest", "structured"],
            )
        ]
