"""System prompts for subagent communication.

Contains prompts that configure subagents and explain task delegation
to the parent agent.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import SubAgentConfig

SUBAGENT_SYSTEM_PROMPT = """You are a specialized subagent working on a delegated task.

## Your Role
You have been spawned by a parent agent to handle a specific task. Focus entirely
on completing the assigned task to the best of your ability.

## Communication
- If you need clarification, use the `ask_parent` tool to ask the parent agent
- Keep questions specific and actionable
- Do not ask unnecessary questions - use your judgment when possible
- If you cannot complete a task, explain why clearly

## Task Completion
- Complete the task thoroughly before returning
- Provide clear, structured results
- If the task cannot be completed, explain what was attempted and why it failed
"""

TASK_TOOL_DESCRIPTION = """\
Delegate a task to a specialized subagent. The subagent runs independently \
with its own context and tools, and returns a result when done.

## When to use
- Complex multi-step tasks that can run independently
- Research or exploration tasks
- Multiple independent subtasks that can run in parallel
- Tasks that require deep focus on a single area

## When NOT to use
- Trivial tasks you can do faster yourself
- Tasks that require your full conversation context
- Tasks that need back-and-forth with the user
"""

CHECK_TASK_DESCRIPTION = """\
Check the status of a background (async) task and get its result if completed."""

ANSWER_SUBAGENT_DESCRIPTION = """\
Answer a question from a background subagent that is waiting for clarification."""

LIST_ACTIVE_TASKS_DESCRIPTION = """\
List all currently active background tasks with their status."""

WAIT_TASKS_DESCRIPTION = """\
Wait for multiple background tasks to complete before continuing."""

SOFT_CANCEL_TASK_DESCRIPTION = """\
Request cooperative cancellation of a background task."""

HARD_CANCEL_TASK_DESCRIPTION = """\
Immediately cancel a background task."""

DEFAULT_GENERAL_PURPOSE_DESCRIPTION = """A general-purpose agent for a wide variety of tasks.
Use this when no specialized subagent matches the task requirements."""


def get_subagent_system_prompt(configs: list[SubAgentConfig], include_dual_mode: bool = True) -> str:
    """Generate system prompt section describing available subagents."""
    lines = ["## Available Subagents", ""]
    lines.append("Use the `task` tool to delegate work to these subagents:")
    lines.append("")
    for config in configs:
        name = config["name"]
        desc = config["description"]
        lines.append(f"- **{name}**: {desc}")
        if config.get("can_ask_questions") is False:
            lines[-1] += " *(cannot ask clarifying questions)*"
    return "\n".join(lines)


def get_task_instructions_prompt(
    task_description: str,
    can_ask_questions: bool = True,
    max_questions: int | None = None,
) -> str:
    """Generate task instructions for a subagent."""
    lines = ["## Your Task", "", task_description, ""]
    if can_ask_questions:
        lines.append("## Asking Questions")
        lines.append("If you need clarification, use the `ask_parent` tool.")
        if max_questions is not None:
            lines.append(f"You may ask up to {max_questions} questions.")
    else:
        lines.append("## Note")
        lines.append("Complete this task using your best judgment.")
        lines.append("You cannot ask the parent for clarification.")
    return "\n".join(lines)
