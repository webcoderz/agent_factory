from typing import List

from extractors import PageExtractor
from ..evidence.models import Evidence
from models import OCRPage
from ...types import RunContext


class MultiExtractor:
    def __init__(self, extractors: List[PageExtractor]):
        self.extractors = extractors
        self.name = "multi_extractor"

    def extract(self, ctx: RunContext, *, doc_artifact_id: str, pages: List[OCRPage]) -> List[Evidence]:
        out: List[Evidence] = []
        for ex in self.extractors:
            out.extend(ex.extract(ctx, doc_artifact_id=doc_artifact_id, pages=pages))
        return out
