from __future__ import annotations
from typing import List, Sequence

from .models import SkillSpec


class SkillSelection:
    def __init__(self, *, include_catalog: bool, load_full: List[str]):
        self.include_catalog = include_catalog
        self.load_full = load_full


class SkillSelector:
    """
    Progressive disclosure:
    - always include catalog summaries
    - load full bodies only for selected skill IDs
    """
    def select(self, intent: str, *, catalog: Sequence[SkillSpec]) -> SkillSelection:
        # Replace with your router’s intent logic. This is a safe baseline.
        if intent in {"ingest_doc", "ocr", "parse_document"}:
            full = [s.id for s in catalog if "ocr" in s.tags or "ingest" in s.tags]
        elif intent in {"investigate", "deep_investigation"}:
            full = [s.id for s in catalog if "investigation" in s.tags][:2]
        else:
            full = []
        return SkillSelection(include_catalog=True, load_full=full)
