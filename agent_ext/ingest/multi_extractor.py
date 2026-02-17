from __future__ import annotations

from typing import List

from .extractors import PageExtractor
from .models import OCRPage
from agent_ext.evidence.models import Evidence
from agent_ext.run_context import RunContext


class MultiExtractor:
    def __init__(self, extractors: List[PageExtractor]):
        self.extractors = extractors
        self.name = "multi_extractor"

    def extract(self, ctx: RunContext, *, doc_artifact_id: str, pages: List[OCRPage]) -> List[Evidence]:
        out: List[Evidence] = []
        for ex in self.extractors:
            out.extend(ex.extract(ctx, doc_artifact_id=doc_artifact_id, pages=pages))
        return out
