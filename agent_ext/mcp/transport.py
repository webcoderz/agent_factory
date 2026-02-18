from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from .types import ToolCall, ToolResult


@dataclass
class LocalTransport:
    """
    Simple in-process transport: client pushes ToolCall to server queue, gets ToolResult back.
    """
    server_in: asyncio.Queue[ToolCall]
    server_out: asyncio.Queue[ToolResult]
