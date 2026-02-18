from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Iterable, List


async def gather_bounded(
    coros: Iterable[Awaitable[Any]],
    *,
    max_concurrency: int = 4,
) -> List[Any]:
    """
    Bounded asyncio.gather: prevents saturating your local LLM server.
    """
    sem = asyncio.Semaphore(max_concurrency)

    async def _wrap(coro: Awaitable[Any]) -> Any:
        async with sem:
            return await coro

    return await asyncio.gather(*[_wrap(c) for c in coros])
