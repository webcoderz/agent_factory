# RLM — Recursive Language Model

Handle extremely large contexts with any LLM provider. The LLM writes Python code to programmatically explore and analyze data, optionally delegating semantic analysis to a sub-model via `llm_query()`.

## Features

- **REPL Environment**: Persistent Python sandbox with state between executions
- **Sub-Model Delegation**: `llm_query()` within the sandbox for semantic analysis
- **Grounded Citations**: `GroundedResponse` model with citation markers
- **Safety**: Restricted built-ins, controlled imports, output truncation
- **Sandboxed File Access**: Temp directory for intermediate results

## Quick Start

```python
from agent_ext.rlm import REPLEnvironment, RLMConfig

# Create REPL with context data
repl = REPLEnvironment(
    context=massive_document,  # str, dict, or list
    config=RLMConfig(
        sub_model="openai:gpt-4o-mini",  # for llm_query()
        code_timeout=60.0,
    ),
)

# LLM writes code to explore the data
result = repl.execute("""
print(f"Context length: {len(context)}")
print(f"First 200 chars: {context[:200]}")
""")

# State persists between executions
result2 = repl.execute("""
# Find specific information
lines = context.split('\\n')
relevant = [l for l in lines if 'revenue' in l.lower()]
print(f"Found {len(relevant)} revenue lines")

# Delegate semantic analysis to sub-model
if relevant:
    analysis = llm_query(f"Summarize these revenue figures: {relevant[:5]}")
    print(analysis)
""")

repl.cleanup()
```

## Grounded Response

```python
from agent_ext.rlm import GroundedResponse

response = GroundedResponse(
    info="Revenue grew [1] driven by expansion [2]",
    grounding={
        "1": "increased by 45% year-over-year",
        "2": "new markets in Asia-Pacific region",
    },
)
```
