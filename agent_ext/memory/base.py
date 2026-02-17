from __future__ import annotations
from typing import Any, List, Protocol


class MemoryManager(Protocol):
    def shape_messages(self, messages: List[Any]) -> List[Any]: ...
    def checkpoint(self, messages: List[Any], *, outcome: Any) -> None: ...
