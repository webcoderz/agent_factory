"""Multi-agent orchestration — registries, message bus, task manager."""

from .base import Subagent, SubagentResult
from .registry import SubagentRegistry, DynamicAgentRegistry
from .orchestrator import SubagentOrchestrator
from .types import (
    AgentMessage,
    CompiledSubAgent,
    ExecutionMode,
    MessageType,
    SubAgentConfig,
    TaskCharacteristics,
    TaskHandle,
    TaskPriority,
    TaskStatus,
    decide_execution_mode,
)
from .message_bus import InMemoryMessageBus, TaskManager, create_message_bus

__all__ = [
    "Subagent",
    "SubagentResult",
    "SubagentRegistry",
    "DynamicAgentRegistry",
    "SubagentOrchestrator",
    "AgentMessage",
    "CompiledSubAgent",
    "ExecutionMode",
    "MessageType",
    "SubAgentConfig",
    "TaskCharacteristics",
    "TaskHandle",
    "TaskPriority",
    "TaskStatus",
    "decide_execution_mode",
    "InMemoryMessageBus",
    "TaskManager",
    "create_message_bus",
]
