"""RLM — Recursive Language Model pattern for large-context analysis.

Provides a sandboxed REPL where an LLM can write Python code to explore
data, with optional ``llm_query()`` for sub-model delegation and
``GroundedResponse`` for citation-grounded output.
"""

from .policies import RLMPolicy
from .python_runner import RLMRunError, run_restricted_python
from .models import ContextType, GroundedResponse, REPLResult, RLMConfig, RLMDependencies
from .repl import REPLEnvironment, format_repl_result

__all__ = [
    "RLMPolicy",
    "RLMRunError",
    "run_restricted_python",
    "ContextType",
    "GroundedResponse",
    "REPLResult",
    "RLMConfig",
    "RLMDependencies",
    "REPLEnvironment",
    "format_repl_result",
]
