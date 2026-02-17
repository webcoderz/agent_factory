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

## Memory and conversation history

Plug in our memory so the agent uses **history_processors** (window/summarized context) and **checkpoint** after each run:

```python
from agent_ext import (
    PydanticAIAgentBase,
    RunContext,
    SlidingWindowMemory,
    SummarizingMemory,
    SummarizeConfig,
)

# Option 1: sliding window (last N messages only)
memory = SlidingWindowMemory(max_messages=20)

# Option 2: summarizing memory (dossier + last N messages)
# memory = SummarizingMemory(cfg=SummarizeConfig(), summarize_fn=your_summarize_fn)

class MyAgent(PydanticAIAgentBase[MyOutput]):
    def __init__(self):
        super().__init__(
            "openai:gpt-4o",
            output_type=MyOutput,
            instructions="Be helpful.",
            memory=memory,
        )

agent = MyAgent()
result1 = agent.run_sync(ctx, "What is 2+2?")
# Next turn: pass message_history so the agent sees the conversation
result2 = agent.run_sync(ctx, "And in hex?", message_history=result1.new_messages())
```

- **shape_messages** runs as a pydantic-ai history_processor before each model request (window or dossier + tail).
- **checkpoint** is called after each `run_sync` / `run` with the full message history and result (so `SummarizingMemory` can update the dossier and persist it via `ctx.artifacts`).

To use the adapter standalone (e.g. to add your own history processor):  
`from agent_ext.agent import build_history_processor, checkpoint_after_run`.

**Tool calls and safe truncation**  
- History is truncated so **tool call pairs** are never split: we only drop from the front at boundaries where the first kept message is a `ModelRequest`. That way a `ModelResponse` with `ToolCallPart` is never kept without the following `ModelRequest` with `ToolReturnPart`.
- Full message structure (including tool calls) is preserved through the processor by keeping `_original` in generic dicts; only synthetic messages (e.g. dossier) are rebuilt from role/content.
- Helpers for inspecting messages: `message_kind(msg)`, `has_tool_calls(msg)`, `has_tool_returns(msg)`, and `safe_truncate_messages(messages, max_messages)` are available from `agent_ext.agent`.

## Imports

- **Run context and types** live in `agent_patterns.run_context` (and are re-exported from `agent_ext`). The root module was renamed from `types` to avoid shadowing the stdlib `types` module.
- **Agent extension** entrypoint is `agent_ext`: hooks, ingest, subagents, skills, memory, backends, and `PydanticAIAgentBase`.