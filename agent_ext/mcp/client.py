from __future__ import annotations

import uuid
from typing import Any

from .transport import LocalTransport
from .types import ToolCall, ToolResult


class MCPClient:
    def __init__(self, transport: LocalTransport):
        self.transport = transport

    async def call(self, tool: str, args: dict[str, Any]) -> ToolResult:
        call_id = uuid.uuid4().hex
        await self.transport.server_in.put(ToolCall(tool=tool, args=args, call_id=call_id))
        # naive: wait for matching call_id
        while True:
            res: ToolResult = await self.transport.server_out.get()
            if res.call_id == call_id:
                return res
