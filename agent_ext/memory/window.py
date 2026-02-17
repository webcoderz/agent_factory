from __future__ import annotations
from typing import Any, List

from .base import MemoryManager


class SlidingWindowMemory(MemoryManager):
    def __init__(self, max_messages: int):
        self.max_messages = max_messages

    def shape_messages(self, messages: List[Any]) -> List[Any]:
        if len(messages) <= self.max_messages:
            return messages
        return messages[-self.max_messages :]

    def checkpoint(self, messages: List[Any], *, outcome: Any) -> None:
        # No-op baseline; you can persist summaries/dossiers via artifacts here.
        return None
