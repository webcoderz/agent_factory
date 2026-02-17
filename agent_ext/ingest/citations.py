from __future__ import annotations
from agent_ext.evidence.models import Citation
from .models import OCRSpan


def cite_span(doc_artifact_id: str, page_index: int, span: OCRSpan) -> Citation:
    loc = f"page:{page_index}"
    if span.bbox:
        x1, y1, x2, y2 = span.bbox
        loc += f";bbox:{x1},{y1},{x2},{y2}"
    quote = span.text[:200] if span.text else None
    return Citation(source_id=doc_artifact_id, locator=loc, quote=quote, confidence=span.confidence)
