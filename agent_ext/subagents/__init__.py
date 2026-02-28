"""Multi-agent orchestration — registries, message bus, task manager, prompts."""

from .base import Subagent, SubagentResult
from .message_bus import InMemoryMessageBus, TaskManager, create_message_bus
from .orchestrator import SubagentOrchestrator
from .prompts import (
    SUBAGENT_SYSTEM_PROMPT,
    TASK_TOOL_DESCRIPTION,
    get_subagent_system_prompt,
    get_task_instructions_prompt,
)
from .protocols import SubAgentDepsProtocol
from .registry import DynamicAgentRegistry, SubagentRegistry
from .toolset import SubAgentDeps, create_subagent_toolset
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
