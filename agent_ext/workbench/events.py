from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Event:
    kind: str
    who: str
    msg: str
    data: dict[str, Any]


class EventBus:
    def __init__(self):
        self.q: asyncio.Queue[Event] = asyncio.Queue()

    async def emit(self, e: Event) -> None:
        await self.q.put(e)

    async def drain(self, limit: int = 50) -> list[Event]:
        out = []
        for _ in range(limit):
            if self.q.empty():
                break
            out.append(self.q.get_nowait())
        return out
