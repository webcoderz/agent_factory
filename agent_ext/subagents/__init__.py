"""Multi-agent orchestration — registries, message bus, task manager, prompts."""

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
from .prompts import (
    SUBAGENT_SYSTEM_PROMPT,
    TASK_TOOL_DESCRIPTION,
    get_subagent_system_prompt,
    get_task_instructions_prompt,
)
from .protocols import SubAgentDepsProtocol
from .toolset import create_subagent_toolset, SubAgentDeps

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
