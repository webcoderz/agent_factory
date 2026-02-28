"""Memory management — sliding window, summarization, and safe cutoff."""

from .base import MemoryManager
from .window import SlidingWindowMemory
from .summarize import SummarizingMemory, SummarizeConfig, Dossier
from .cutoff import (
    TokenCounter,
    approximate_token_count,
    find_safe_cutoff,
    find_token_based_cutoff,
    is_safe_cutoff_point,
)

__all__ = [
    "MemoryManager",
    "SlidingWindowMemory",
    "SummarizingMemory",
    "SummarizeConfig",
    "Dossier",
    "TokenCounter",
    "approximate_token_count",
    "find_safe_cutoff",
    "find_token_based_cutoff",
    "is_safe_cutoff_point",
]
