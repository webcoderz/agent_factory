from __future__ import annotations

from typing import Any, Protocol


class MemoryManager(Protocol):
    def shape_messages(self, messages: list[Any]) -> list[Any]: ...
    def checkpoint(self, messages: list[Any], *, outcome: Any) -> None: ...
