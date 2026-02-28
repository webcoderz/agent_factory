"""RLM policies and the legacy restricted runner.

For new code, use ``REPLEnvironment`` from ``rlm.repl`` instead of
``run_restricted_python``.
"""
from __future__ import annotations

from pydantic import BaseModel


class RLMPolicy(BaseModel):
    """Policy for restricted Python execution (legacy)."""
    allow_imports: list[str] = ["math", "json", "re", "statistics", "collections"]
    max_stdout_chars: int = 50_000
    max_runtime_s: int = 10
