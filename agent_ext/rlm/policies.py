from __future__ import annotations
from pydantic import BaseModel


class RLMPolicy(BaseModel):
    allow_imports: list[str] = ["math", "json", "re", "statistics"]
    max_stdout_chars: int = 50_000
    max_runtime_s: int = 10
