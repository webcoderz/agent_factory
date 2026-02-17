from __future__ import annotations
from .models import Citation


def cite_artifact_page(artifact_id: str, page: int, *, quote: str | None = None, confidence: float = 0.7) -> Citation:
    return Citation(source_id=artifact_id, locator=f"page:{page}", quote=quote, confidence=confidence)
