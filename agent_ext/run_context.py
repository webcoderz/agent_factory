"""
Re-export RunContext and related types from the root package.

Use: from agent_ext.run_context import RunContext, ToolCall, ToolResult, Policy, ...

This avoids agent_ext code depending on agent_patterns package name and keeps
imports resolvable when the project is opened as agent_patterns (no parent on path).
"""
from __future__ import annotations

# Ensure root package is importable (same bootstrap as agent_ext/__init__.py)
def _ensure_root_importable() -> None:
    import sys
    from pathlib import Path
    _root = Path(__file__).resolve().parent.parent
    _parent = _root.parent
    if _parent not in (Path(p).resolve() for p in sys.path):
        sys.path.insert(0, str(_parent))


_ensure_root_importable()

# Re-export from root package (agent_patterns.run_context), not from self
from agent_patterns.run_context import (
    ArtifactStore,
    Cache,
    Logger,
    Policy,
    RunContext,
    ToolCall,
    ToolResult,
)

__all__ = [
    "ArtifactStore",
    "Cache",
    "Logger",
    "Policy",
    "RunContext",
    "ToolCall",
    "ToolResult",
]
