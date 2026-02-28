from __future__ import annotations

from typing import Protocol

from agent_ext.run_context import RunContext

from .models import OCRPage, PageImage


class OCREngine(Protocol):
    name: str

    def ocr_pages(self, ctx: RunContext, pages: list[PageImage]) -> list[OCRPage]: ...


class NullOCREngine:
    name = "null"

    def ocr_pages(self, ctx: RunContext, pages: list[PageImage]) -> list[OCRPage]:
        # Useful for testing pipeline wiring
        out: list[OCRPage] = []
        for p in pages:
            out.append(OCRPage(page_index=p.page_index, spans=[], full_text="", engine=self.name))
        return out
