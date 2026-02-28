"""Pydantic models and data types for the RLM system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ContextType = str | dict[str, Any] | list[Any]


@dataclass
class RLMConfig:
    """Configuration for RLM behavior."""

    code_timeout: float = 60.0
    """Timeout in seconds for code execution."""

    truncate_output_chars: int = 50_000
    """Maximum characters to return from code execution output."""

    sub_model: str | None = None
    """Model for llm_query() within the REPL environment."""

    allow_imports: list[str] = field(
        default_factory=lambda: [
            "math",
            "json",
            "re",
            "statistics",
            "collections",
            "itertools",
            "functools",
            "operator",
            "string",
            "textwrap",
            "datetime",
            "hashlib",
            "csv",
        ]
    )
    """Modules the REPL is allowed to import."""


@dataclass
class RLMDependencies:
    """Dependencies injected into RLM tools via RunContext."""

    context: ContextType
    """The context to analyze (string, dict, or list)."""

    config: RLMConfig = field(default_factory=RLMConfig)
    """RLM configuration options."""

    def __post_init__(self):
        if self.context is None:
            raise ValueError("context cannot be None")


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass
class REPLResult:
    """Result from REPL code execution."""

    stdout: str
    """Standard output from execution."""

    stderr: str
    """Standard error from execution."""

    locals: dict[str, Any]
    """Local variables after execution."""

    execution_time: float
    """Time taken to execute in seconds."""

    success: bool = True
    """Whether execution completed without errors."""


# ---------------------------------------------------------------------------
# Grounded response (citations)
# ---------------------------------------------------------------------------


class GroundedResponse(BaseModel):
    """A response with citation markers mapping to exact quotes from source documents.

    Example::

        GroundedResponse(
            info="Revenue grew [1] driven by expansion [2]",
            grounding={"1": "increased by 45%", "2": "new markets in Asia"},
        )
    """

    info: str = Field(description="Response text with citation markers like [1]")
    grounding: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping from citation markers to exact quotes from the source",
    )
