from __future__ import annotations

import asyncio


class ModelLimiter:
    """
    Shared limiter for *all* model calls across subagents.
    """
    def __init__(self, max_concurrency: int = 2):
        self._sem = asyncio.Semaphore(max_concurrency)

    async def __aenter__(self):
        await self._sem.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        self._sem.release()
