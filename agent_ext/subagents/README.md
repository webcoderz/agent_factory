# Subagents — Multi-Agent Orchestration

Spawn specialized subagents that run synchronously, asynchronously, or auto-select the best mode. Includes inter-agent communication via message bus.

## Features

- **Static + Dynamic Registries**: Register agents at setup or create them at runtime
- **Message Bus**: In-memory async message passing with ask/answer protocol
- **Task Manager**: Background task lifecycle with soft/hard cancellation
- **Auto-Mode Selection**: Intelligent sync/async decision based on task characteristics
- **Nested Subagents**: Subagents can spawn their own subagents

## Quick Start

```python
from agent_ext.subagents import (
    SubagentRegistry, DynamicAgentRegistry,
    InMemoryMessageBus, TaskManager,
    SubAgentConfig, TaskCharacteristics, decide_execution_mode,
)

# Static registry (simple)
reg = SubagentRegistry()
reg.register(my_agent)
result = await reg.get("my_agent").run(ctx, input="hello", meta={})

# Dynamic registry (runtime creation)
dyn = DynamicAgentRegistry(max_agents=10)
config = SubAgentConfig(name="researcher", description="...", instructions="...")
dyn.register(config, agent_instance)

# Message bus
bus = InMemoryMessageBus()
queue = bus.register_agent("worker-1")
await bus.send(AgentMessage(type=MessageType.TASK_ASSIGNED, ...))
response = await bus.ask("parent", "worker-1", question="help?", task_id="t1")
```

## Execution Modes

| Mode | When |
|------|------|
| `sync` | Simple tasks, needs user context |
| `async` | Complex independent tasks |
| `auto` | System decides based on `TaskCharacteristics` |
