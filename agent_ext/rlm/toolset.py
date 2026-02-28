"""RLM toolset — gives any pydantic-ai agent a sandboxed code execution tool.

Example::

    from pydantic_ai import Agent
    from agent_ext.rlm import create_rlm_toolset, RLMDependencies

    toolset = create_rlm_toolset()
    agent = Agent("openai:gpt-4o", toolsets=[toolset])

    deps = RLMDependencies(context={"users": [...]})
    result = await agent.run("Analyze the user data", deps=deps)
"""

from __future__ import annotations

import asyncio

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from .models import REPLResult, RLMConfig, RLMDependencies
from .repl import REPLEnvironment, format_repl_result

EXECUTE_CODE_DESCRIPTION = """
Execute Python code in a sandboxed REPL environment.

## Environment
- A `context` variable is pre-loaded with the data to analyze
- Variables persist between executions within the same session
- Standard library modules are available (json, re, collections, etc.)
- Use print() to display output

## When to Use
- Analyzing or processing structured data (JSON, dicts, lists)
- Performing calculations or data transformations
- Extracting specific information from large datasets
- Testing hypotheses about the data structure

## Best Practices
1. Start by exploring the context: `print(type(context))`, `print(len(context))`
2. Break complex operations into smaller steps
3. Use print() liberally to understand intermediate results
4. Handle potential errors gracefully with try/except

## Available Functions
- `llm_query(prompt)`: Query the LLM for reasoning assistance (if configured)
- Important: Do not use `llm_query` in the first code execution. Use it only after you have
  explored the context and identified specific sections that need semantic analysis.
"""

# Global registry to track REPL environments for cleanup
_repl_registry: dict[int, REPLEnvironment] = {}


def create_rlm_toolset(
    *,
    code_timeout: float = 60.0,
    sub_model: str | None = None,
    toolset_id: str | None = None,
) -> FunctionToolset[RLMDependencies]:
    """Create an RLM toolset for code execution in a sandboxed REPL.

    Args:
        code_timeout: Timeout in seconds for code execution.
        sub_model: Model to use for llm_query() within the REPL.
        toolset_id: Optional unique identifier for the toolset.

    Returns:
        FunctionToolset compatible with any pydantic-ai agent.
    """
    toolset: FunctionToolset[RLMDependencies] = FunctionToolset(id=toolset_id)

    def _get_or_create_repl(ctx: RunContext[RLMDependencies]) -> REPLEnvironment:
        deps_id = id(ctx.deps)
        if deps_id not in _repl_registry:
            config = ctx.deps.config or RLMConfig()
            if sub_model and not config.sub_model:
                config = RLMConfig(sub_model=sub_model)
            _repl_registry[deps_id] = REPLEnvironment(
                context=ctx.deps.context,
                config=config,
            )
        return _repl_registry[deps_id]

    @toolset.tool(description=EXECUTE_CODE_DESCRIPTION)
    async def execute_code(ctx: RunContext[RLMDependencies], code: str) -> str:
        repl_env = _get_or_create_repl(ctx)
        try:
            loop = asyncio.get_running_loop()
            result: REPLResult = await asyncio.wait_for(
                loop.run_in_executor(None, repl_env.execute, code),
                timeout=code_timeout,
            )
            return format_repl_result(result)
        except TimeoutError:
            return f"Error: Code execution timed out after {code_timeout} seconds."
        except Exception as e:
            return f"Error executing code: {e!s}"

    return toolset


def cleanup_repl_environments() -> None:
    """Clean up all REPL environments."""
    for repl_env in _repl_registry.values():
        repl_env.cleanup()
    _repl_registry.clear()
