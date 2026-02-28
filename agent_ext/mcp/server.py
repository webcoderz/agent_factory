from __future__ import annotations

import asyncio

from .registry import MCPToolRegistry
from .transport import LocalTransport
from .types import ToolCall


class MCPServer:
    def __init__(self, registry: MCPToolRegistry, transport: LocalTransport):
        self.registry = registry
        self.transport = transport
        self._task: asyncio.Task | None = None

    async def serve_forever(self) -> None:
        while True:
            call: ToolCall = await self.transport.server_in.get()
            res = self.registry.call(call.tool, call.args, call.call_id)
            await self.transport.server_out.put(res)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self.serve_forever())
