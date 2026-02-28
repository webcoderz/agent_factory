from __future__ import annotations

import asyncio
import contextlib
import os
from pathlib import Path
from typing import Any

from agent_ext.cog.state import CogState, RegressionMemory
from agent_ext.hooks.builtins import AuditHook, PolicyHook
from agent_ext.hooks.chain import MiddlewareChain
from agent_ext.hooks.context import MiddlewareContext
from agent_ext.mcp import LocalTransport, MCPClient, MCPServer, MCPToolRegistry, ToolSpec
from agent_ext.modules.registry import ModuleRegistry
from agent_ext.run_context import Policy, RunContext
from agent_ext.search import BM25Config, BM25Index, RepoIndexerConfig, TokenizerConfig
from agent_ext.subagents.message_bus import InMemoryMessageBus, TaskManager
from agent_ext.workbench.subagents_bm25 import BM25SearchSubagent
from agent_ext.workflow.builtins import register_builtins as register_workflow_builtins
from agent_ext.workflow.executor import WorkflowExecutor
from agent_ext.workflow.experience import ExperienceStore
from agent_ext.workflow.planner import WorkflowPlanner
from agent_ext.workflow.registry import Registry as WorkflowRegistry

from .limits import ModelLimiter
from .planner import TaskQueue
from .subagents import PlannerSubagent, RepoGrepSubagent, SubagentOrchestrator, SubagentRegistry
from .subagents_patch import LLMPatchSubagent

try:
    from agent_ext.self_improve.controller import SelfImproveController
except Exception:
    SelfImproveController = None  # type: ignore[misc, assignment]

use_tiktoken = bool(int(os.getenv("USE_TIKTOKEN", "0")))
tok_enc = os.getenv("TIKTOKEN_ENCODING", "o200k_base")


class _Logger:
    def info(self, msg: str, **kw):
        print(f"[info] {msg} {kw}")

    def warning(self, msg: str, **kw):
        print(f"[warn] {msg} {kw}")

    def error(self, msg: str, **kw):
        print(f"[error] {msg} {kw}")


class _Cache(dict):
    def get(self, k, default=None):
        return super().get(k, default)

    def set(self, k, v):
        super().__setitem__(k, v)


class _Artifacts:
    root = Path(".agent_state/runs")

    def put_json(self, key: str, obj):
        self.root.mkdir(parents=True, exist_ok=True)
        import json

        p = self.root / f"{key}.json"
        p.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        return str(p)


def build_ctx(
    *,
    case_id: str = "case-1",
    session_id: str = "sess-1",
    user_id: str = "user-1",
    model: Any | None = None,
    max_parallel_subagents: int = 4,
    max_parallel_model_calls: int = 2,
) -> RunContext:
    cog_state = CogState()
    cog_state.load()
    regression_memory = RegressionMemory()
    regression_memory.load()

    ctx = RunContext(
        case_id=case_id,
        session_id=session_id,
        user_id=user_id,
        policy=Policy(allow_tools=True, allow_exec=False, allow_fs_write=True),
        cache=_Cache(),
        logger=_Logger(),
        artifacts=_Artifacts(),
        trace_id=None,
        cog_state=cog_state,
        regression_memory=regression_memory,
    )

    # Workbench attachments
    ctx.model = model
    ctx.model_limiter = ModelLimiter(max_concurrency=max_parallel_model_calls)
    ctx.max_parallel_subagents = max_parallel_subagents

    ctx.task_queue = TaskQueue()

    # Subagents
    reg = SubagentRegistry()
    reg.register(PlannerSubagent())
    reg.register(RepoGrepSubagent())
    reg.register(BM25SearchSubagent())
    reg.register(LLMPatchSubagent())
    ctx.subagents = reg
    ctx.orchestrator = SubagentOrchestrator(reg)
    # Middleware chain (async hooks)
    ctx.middleware_chain = MiddlewareChain([AuditHook(), PolicyHook()])
    ctx.middleware_context = MiddlewareContext(
        config={
            "case_id": case_id,
            "session_id": session_id,
            "max_parallel_subagents": max_parallel_subagents,
        }
    )
    # Message bus for inter-agent communication
    ctx.message_bus = InMemoryMessageBus()
    ctx.task_manager = TaskManager(message_bus=ctx.message_bus)
    # Module registry (load builtins)
    ctx.module_registry = ModuleRegistry()
    with contextlib.suppress(Exception):
        ctx.module_registry.load_all_builtins(ctx)  # non-fatal if modules fail to load
    # Commands map (TUI)
    ctx.commands = {}
    # Run state for plan → design → implement (search results, design output, etc.)
    ctx.workbench_run_state = {}
    # Recent LLM call traces for TUI (prompt/response previews; capped at 30)
    ctx.llm_traces = []
    # Background runs: list of asyncio.Task (many parallel runs; queue claims atomically; /stop or /stop all)
    ctx.background_run_tasks: list = []
    # Recent task outputs for /watch (progress_callback appends; capped in TUI)
    ctx.watch_outputs: list = []
    # Self-improve: apply patches and run gates (optional)
    ctx.self_improve = SelfImproveController() if SelfImproveController else None
    # Workflow synthesis + learning
    ctx.workflow_registry = WorkflowRegistry()
    register_workflow_builtins(ctx.workflow_registry)

    ctx.workflow_experience = ExperienceStore()
    ctx.workflow_planner = WorkflowPlanner(ctx.workflow_experience)
    ctx.workflow_executor = WorkflowExecutor()

    ctx.search = BM25Index(
        bm25_cfg=BM25Config(top_k=int(os.getenv("BM25_TOP_K", "20"))),
        tok_cfg=TokenizerConfig(use_tiktoken=use_tiktoken, tiktoken_encoding=tok_enc),
        indexer_cfg=RepoIndexerConfig(),
    )
    # Index built on first search (keeps startup fast)

    ctx.mcp_registry = MCPToolRegistry()
    ctx.mcp_transport = LocalTransport(server_in=asyncio.Queue(), server_out=asyncio.Queue())
    ctx.mcp_server = MCPServer(ctx.mcp_registry, ctx.mcp_transport)
    ctx.mcp_client = MCPClient(ctx.mcp_transport)
    # MCP server started in run_tui() when event loop is running

    # example MCP tool: bm25_search
    ctx.mcp_registry.register(
        ToolSpec(
            name="bm25_search",
            description="Search repo via BM25 index",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}, "k": {"type": "integer"}}},
            output_schema={"type": "array", "items": {"type": "object"}},
        ),
        lambda a: ctx.search.search(a.get("query", ""), top_k=int(a.get("k", 20))),
    )

    return ctx
