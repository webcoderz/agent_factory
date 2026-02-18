from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

@dataclass(frozen=True)
class Mode:
    name: str
    parallel_writers: int
    max_files: int
    deep_context: bool
    pytest: bool

FAST = Mode("fast", parallel_writers=1, max_files=4, deep_context=False, pytest=False)
DEEP = Mode("deep", parallel_writers=2, max_files=8, deep_context=True, pytest=False)
REPAIR = Mode("repair", parallel_writers=2, max_files=8, deep_context=True, pytest=True)
EXPLORE = Mode("explore", parallel_writers=3, max_files=6, deep_context=False, pytest=False)

def choose_mode(*, fail_streak: int, triggers: list, bm25_confidence: float) -> Mode:
    if fail_streak >= 2:
        return REPAIR
    if any(t.kind == "repo_changed" for t in triggers) and bm25_confidence < 0.25:
        return DEEP
    if bm25_confidence > 0.6:
        return FAST
    return EXPLORE
