from __future__ import annotations
from typing import List, Protocol

from agent_ext.run_context import RunContext
from .models import DocumentInput, PageImage


class PDFRenderer(Protocol):
    def render_to_png_bytes(self, *, pdf_bytes: bytes, page_index: int, dpi: int) -> bytes: ...
    def page_count(self, *, pdf_bytes: bytes) -> int: ...


class PDFToImages:
    def __init__(self, renderer: PDFRenderer, *, dpi: int = 200):
        self.renderer = renderer
        self.dpi = dpi

    def run(self, ctx: RunContext, doc: DocumentInput) -> List[PageImage]:
        if not doc.artifact_id:
            raise ValueError("PDFToImages currently expects doc.artifact_id for auditability")

        pdf_bytes = ctx.artifacts.get_bytes(doc.artifact_id)
        n = self.renderer.page_count(pdf_bytes=pdf_bytes)

        pages: List[PageImage] = []
        for i in range(n):
            png = self.renderer.render_to_png_bytes(pdf_bytes=pdf_bytes, page_index=i, dpi=self.dpi)
            img_id = ctx.artifacts.put_bytes(
                png,
                metadata={
                    "kind": "page_image",
                    "source_doc": doc.artifact_id,
                    "page_index": i,
                    "dpi": self.dpi,
                },
            )
            pages.append(PageImage(page_index=i, image_artifact_id=img_id))
        return pages
