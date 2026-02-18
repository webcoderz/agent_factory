from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from .runtime import build_ctx
from .models import build_openai_chat_model, model_from_env


@dataclass
class Workbench:
    """
    Notebook-friendly wrapper.

    Usage in Jupyter:
      wb = Workbench.from_env()
      await wb.plan("add bm25 search tool")
      await wb.exec("general", "find where RunContext is defined")
    """
    ctx: any

    @classmethod
    def from_env(cls, *, use_openai_chat_model: bool = True):
        model = None
        if use_openai_chat_model:
            cfg = model_from_env()
            model = build_openai_chat_model(cfg)
        ctx = build_ctx(model=model)
        return cls(ctx=ctx)

    async def refresh_index(self):
        # incremental rebuild
        changed, removed = self.ctx.search.rebuild_incremental()
        return {"changed": changed, "removed": removed}

    async def bm25(self, query: str, k: int = 20):
        return self.ctx.search.search(query, top_k=k)

    async def mcp_call(self, tool: str, args: dict):
        return await self.ctx.mcp_client.call(tool, args)

    # If you have the workflow planner/executor wired:
    async def exec(self, task_type: str, text: str, hints=()):
        from agent_ext.workflow.types import TaskRequest
        req = TaskRequest(text=text, task_type=task_type, hints=tuple(hints))
        wf = self.ctx.workflow_planner.choose(self.ctx, req)
        result = await self.ctx.workflow_executor.execute(self.ctx, wf, req)
        # simple reward
        reward = (1.0 if result.ok else 0.0)
        self.ctx.workflow_experience.record(req, result, reward)
        self.ctx.workflow_planner.observe(req, wf.name, reward)
        return result
