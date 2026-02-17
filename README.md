# agent_patterns

Shared patterns and extensions for AI agents: hooks, ingest pipelines, subagents, skills, and a [pydantic-ai](https://ai.pydantic.dev) base agent.

## Running / importing

From the repo root, ensure the **parent** of this directory is on `PYTHONPATH` so the `agent_patterns` package resolves:

```bash
# From the directory that contains agent_patterns (e.g. webcoderz):
export PYTHONPATH="$(pwd):$PYTHONPATH"
uv run python -c "from agent_ext import PydanticAIAgentBase, RunContext; print('OK')"
```

Or from inside `agent_patterns`:

```bash
export PYTHONPATH="$(cd .. && pwd):$PYTHONPATH"
uv run python your_script.py
```

## Pydantic-AI base agent

Subclass `PydanticAIAgentBase` to build agents that use our `RunContext` (case_id, session_id, policy, logger, etc.) as pydantic-ai dependencies:

```python
from pydantic import BaseModel, Field
from agent_ext import PydanticAIAgentBase, RunContext

class MyOutput(BaseModel):
    answer: str = Field(description="The agent's answer")

class MyAgent(PydanticAIAgentBase[MyOutput]):
    def __init__(self):
        super().__init__(
            "openai:gpt-4o",
            output_type=MyOutput,
            instructions="You are a helpful assistant.",
        )

# Run with your RunContext as deps
agent = MyAgent()
result = agent.run_sync(ctx, "What is 2+2?")
print(result.output)
```

Tools receive pydantic-ai's `RunContext`; `ctx.deps` is your `RunContext` (logger, policy, etc.):

```python
from pydantic_ai import RunContext as PAIRunContext
from agent_patterns.run_context import RunContext as PatternsRunContext

@my_agent.tool
async def lookup(ctx: PAIRunContext[PatternsRunContext], query: str) -> str:
    ctx.deps.logger.info("tool.lookup", query=query)
    return "..."
```

## Imports

- **Run context and types** live in `agent_patterns.run_context` (and are re-exported from `agent_ext`). The root module was renamed from `types` to avoid shadowing the stdlib `types` module.
- **Agent extension** entrypoint is `agent_ext`: hooks, ingest, subagents, skills, memory, backends, and `PydanticAIAgentBase`.