"""
Streaming and agent DAG hooks for the workbench.

Uses pydantic-ai's run_stream() for token-level streaming and agent.iter() for
node-by-node access to the execution graph (UserPromptNode, ModelRequestNode,
CallToolsNode, End). Lets you tap into the agent DAG for observability, custom
logging, or self-replicating agent frameworks.

See: https://ai.pydantic.dev (run_stream, stream_text, agent.iter, graph nodes)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

# Node type names matching pydantic-ai graph (agent.iter())
NODE_USER_PROMPT = "user_prompt"
NODE_MODEL_REQUEST = "model_request"
NODE_CALL_TOOLS = "call_tools"
NODE_END = "end"


async def run_agent_streaming(
    ctx: Any,
    agent: Any,
    prompt: str,
    kind: str = "llm",
    *,
    prompt_max_len: int = 8000,
    response_max_len: int = 12000,
) -> str:
    """
    Run a pydantic-ai agent with streaming; append a trace to ctx.llm_traces
    and update trace["response"] as tokens arrive. Returns the full text output.

    Use this when you want a single LLM call to stream into the workbench trace
    (e.g. for custom subagents or tools that use Agent).
    """
    traces = getattr(ctx, "llm_traces", None)
    trace_entry: dict[str, Any] | None = None
    if traces is not None:
        max_traces = 30
        if len(traces) >= max_traces:
            traces.pop(0)
        trace_entry = {
            "kind": kind,
            "prompt": (prompt or "")[:prompt_max_len],
            "response": "",
        }
        traces.append(trace_entry)

    text_out = ""
    async with agent.run_stream(prompt) as result:
        async for text in result.stream_text():
            text_out = text
            if trace_entry is not None:
                trace_entry["response"] = (text or "")[:response_max_len]
    if trace_entry is not None and not trace_entry["response"] and text_out:
        trace_entry["response"] = (text_out or "")[:response_max_len]
    return text_out


async def iter_agent_dag(
    agent: Any,
    prompt: str,
    **kwargs: Any,
) -> AsyncIterator[tuple[str, Any]]:
    """
    Iterate over the agent execution graph (DAG) node by node. Yields
    (node_type, node) for each step: user_prompt, model_request, call_tools, end.

    Lets you tap into the agent DAG for observability, metrics, or custom
    handling (e.g. streaming from ModelRequestNode via node.stream(run.ctx)).

    Example:
        async for node_type, node in iter_agent_dag(agent, "What is 2+2?"):
            if node_type == NODE_MODEL_REQUEST:
                async with node.stream(run.ctx) as stream:
                    async for event in stream:
                        ...
    """
    from pydantic_ai import Agent

    async with agent.iter(prompt, **kwargs) as run:
        async for node in run:
            if getattr(Agent, "is_user_prompt_node", lambda n: False)(node):
                yield (NODE_USER_PROMPT, node)
            elif getattr(Agent, "is_model_request_node", lambda n: False)(node):
                yield (NODE_MODEL_REQUEST, node)
            elif getattr(Agent, "is_call_tools_node", lambda n: False)(node):
                yield (NODE_CALL_TOOLS, node)
            elif getattr(Agent, "is_end_node", lambda n: False)(node) or type(node).__name__ == "End":
                yield (NODE_END, node)
