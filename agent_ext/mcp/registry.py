from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional

from .types import ToolSpec, ToolResult

ToolFn = Callable[[dict], Any]


class MCPToolRegistry:
    def __init__(self):
        self._specs: Dict[str, ToolSpec] = {}
        self._fns: Dict[str, ToolFn] = {}

    def register(self, spec: ToolSpec, fn: ToolFn) -> None:
        self._specs[spec.name] = spec
        self._fns[spec.name] = fn

    def list_specs(self) -> List[ToolSpec]:
        return [self._specs[k] for k in sorted(self._specs)]

    def call(self, tool: str, args: dict, call_id: str) -> ToolResult:
        fn = self._fns.get(tool)
        if not fn:
            return ToolResult(call_id=call_id, ok=False, error=f"unknown tool: {tool}")
        try:
            out = fn(args)
            return ToolResult(call_id=call_id, ok=True, result=out)
        except Exception as e:
            return ToolResult(call_id=call_id, ok=False, error=repr(e))
