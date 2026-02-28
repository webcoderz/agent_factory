"""Memory management — sliding window, summarization, and safe cutoff."""

from .base import MemoryManager
from .cutoff import (
    TokenCounter,
    approximate_token_count,
    find_safe_cutoff,
    find_token_based_cutoff,
    is_safe_cutoff_point,
)
from .summarize import Dossier, SummarizeConfig, SummarizingMemory
from .window import SlidingWindowMemory

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
