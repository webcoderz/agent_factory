# AgentPatterns — Batteries-Included Pydantic-AI Agent

`AgentPatterns` inherits from pydantic-ai's `Agent` and auto-wires all agent_patterns subsystems: middleware, memory, console tools, RLM code execution, database queries, subagent delegation, and task management.

## Quick Start

```python
from agent_ext.agent import AgentPatterns

# Minimal: just a model
agent = AgentPatterns("openai:gpt-4o")

# With toolsets (pass names or FunctionToolset instances)
agent = AgentPatterns(
    "openai:gpt-4o",
    instructions="You are a coding assistant.",
    toolsets=["console", "todo"],
)

# With memory
from agent_ext.memory import SlidingWindowMemory

agent = AgentPatterns(
    "openai:gpt-4o",
    toolsets=["console"],
    memory=SlidingWindowMemory(max_messages=50),
)
```

## Factory Methods

```python
# Console agent (ls, read, write, edit, grep, execute)
agent = AgentPatterns.with_console()

# RLM agent (sandboxed Python execution)
agent = AgentPatterns.with_rlm(sub_model="openai:gpt-4o-mini")

# Database agent (SQL queries)
agent = AgentPatterns.with_database()

# Kitchen sink (everything)
agent = AgentPatterns.with_all()
```

## Available Toolsets

| Name | Tools | Use Case |
|------|-------|----------|
| `"console"` | ls, read_file, write_file, edit_file, grep, glob_files, execute | File operations + shell |
| `"rlm"` | execute_code | Sandboxed Python for data analysis |
| `"database"` | list_tables, describe_table, sample_table, query | SQL database access |
| `"subagents"` | task, check_task, list_active_tasks, cancel_task | Multi-agent delegation |
| `"todo"` | create_task, list_tasks, update_task, complete_task | Task management |
