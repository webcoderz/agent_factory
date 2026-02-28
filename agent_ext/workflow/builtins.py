from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from .types import Capability, StepSpec, WorkflowSpec


@dataclass
class PlannerComponent:
    capability = Capability(
        name="planner_component", tags=("plan",), cost_hint=1, quality_hint=0.5, requires_model=False
    )

    async def run(self, ctx, state: dict[str, Any]) -> dict[str, Any]:
        # quick heuristic “plan” into scratch
        state["task"]["text"]
        state["scratch"]["plan"] = [
            "analyze intent",
            "search repo",
            "execute relevant workflow steps",
            "summarize output",
        ]
        await asyncio.sleep(0)
        return state


@dataclass
class MemoryComponent:
    capability = Capability(
        name="memory_component", tags=("memory",), cost_hint=1, quality_hint=0.5, requires_model=False
    )

    async def run(self, ctx, state: dict[str, Any]) -> dict[str, Any]:
        # placeholder: later wire SummarizingMemory / SlidingWindowMemory
        state["scratch"]["memory_used"] = True
        await asyncio.sleep(0)
        return state


@dataclass
class OcrComponent:
    capability = Capability(name="ocr_component", tags=("ocr",), cost_hint=3, quality_hint=0.5, requires_model=True)

    async def run(self, ctx, state: dict[str, Any]) -> dict[str, Any]:
        # stub: later wire actual ingest/vision OCR pipeline
        async with ctx.model_limiter:
            # don’t call model yet; just show wiring
            await asyncio.sleep(0)
        state.setdefault("outputs", {})
        state["outputs"]["ocr_text"] = "(stub ocr output)"
        return state


@dataclass
class RepoSearchComponent:
    capability = Capability(
        name="repo_search_component", tags=("search_repo",), cost_hint=1, quality_hint=0.5, requires_model=False
    )

    async def run(self, ctx, state: dict[str, Any]) -> dict[str, Any]:
        query = state["task"]["text"]
        res = await ctx.subagents.get("repo_grep").run(ctx, input=query, meta={"root": ".", "limit": 10})
        state.setdefault("outputs", {})
        state["outputs"]["repo_hits"] = res.output
        return state


@dataclass
class SummarizeComponent:
    capability = Capability(
        name="summarize_component", tags=("summarize",), cost_hint=1, quality_hint=0.5, requires_model=False
    )

    async def run(self, ctx, state: dict[str, Any]) -> dict[str, Any]:
        # cheap summary; later can be LLM
        outs = state.get("outputs", {})
        state["outputs"]["summary"] = f"done. outputs keys={list(outs.keys())}"
        await asyncio.sleep(0)
        return state


def register_builtins(registry) -> None:
    registry.register_component("plan", PlannerComponent())
    registry.register_component("memory", MemoryComponent())
    registry.register_component("ocr", OcrComponent())
    registry.register_component("repo_search", RepoSearchComponent())
    registry.register_component("summarize", SummarizeComponent())

    # Workflow A: generic plan + search + summarize
    registry.register_workflow(
        WorkflowSpec(
            name="wf_general",
            steps=(
                StepSpec("plan"),
                StepSpec("repo_search"),
                StepSpec("summarize"),
            ),
            meta={"task_type": "general"},
        )
    )

    # Workflow B: OCR-ish (includes memory)
    registry.register_workflow(
        WorkflowSpec(
            name="wf_ocr_with_memory",
            steps=(
                StepSpec("plan"),
                StepSpec("memory"),
                StepSpec("ocr"),
                StepSpec("summarize"),
            ),
            meta={"task_type": "ocr"},
        )
    )
