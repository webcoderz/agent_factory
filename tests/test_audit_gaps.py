"""Tests for gap-fill code: strategies, async guardrail, decorators, prompts, wiring."""
from __future__ import annotations

import asyncio
import pytest

from agent_ext.hooks import (
    AsyncGuardrailMiddleware, GuardrailTiming, AggregationStrategy,
    AgentMiddleware, InputBlocked, MiddlewareChain, middleware_from_functions,
)
from agent_ext.hooks.strategies import GuardrailTiming as GT
from agent_ext.subagents.prompts import (
    get_subagent_system_prompt, get_task_instructions_prompt,
    SUBAGENT_SYSTEM_PROMPT, TASK_TOOL_DESCRIPTION,
)
from agent_ext.subagents.protocols import SubAgentDepsProtocol
from agent_ext.subagents.types import SubAgentConfig
from agent_ext.run_context import RunContext, Policy


def _make_ctx():
    class _C(dict):
        def get(self, k, d=None): return super().get(k, d)
        def set(self, k, v): super().__setitem__(k, v)
    class _L:
        def info(self, msg, **k): pass
        def warning(self, msg, **k): pass
        def error(self, msg, **k): pass
    class _A:
        def put_json(self, k, o): return k
    return RunContext(
        case_id="c1", session_id="s1", user_id="u1",
        policy=Policy(allow_tools=True),
        cache=_C(), logger=_L(), artifacts=_A(),
    )


class TestGuardrailTiming:
    def test_enum_values(self):
        assert GT.BLOCKING.value == "blocking"
        assert GT.CONCURRENT.value == "concurrent"
        assert GT.ASYNC_POST.value == "async_post"


class TestAggregationStrategy:
    def test_new_values_exist(self):
        assert AggregationStrategy.ALL_MUST_PASS
        assert AggregationStrategy.FIRST_SUCCESS
        assert AggregationStrategy.RACE
        assert AggregationStrategy.COLLECT_ALL


class TestAsyncGuardrail:
    @pytest.mark.asyncio
    async def test_blocking_mode_passes(self):
        class PassGuardrail(AgentMiddleware):
            async def before_run(self, ctx, prompt):
                return prompt
        grd = AsyncGuardrailMiddleware(PassGuardrail(), timing=GuardrailTiming.BLOCKING)
        result = await grd.before_run(_make_ctx(), "hello")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_blocking_mode_blocks(self):
        class BlockGuardrail(AgentMiddleware):
            async def before_run(self, ctx, prompt):
                raise InputBlocked("blocked!")
        grd = AsyncGuardrailMiddleware(BlockGuardrail(), timing=GuardrailTiming.BLOCKING)
        with pytest.raises(InputBlocked):
            await grd.before_run(_make_ctx(), "hello")

    @pytest.mark.asyncio
    async def test_async_post_logs_but_passes(self):
        class BlockGuardrail(AgentMiddleware):
            async def before_run(self, ctx, prompt):
                raise InputBlocked("blocked!")
        grd = AsyncGuardrailMiddleware(BlockGuardrail(), timing=GuardrailTiming.ASYNC_POST)
        # before_run should pass (ASYNC_POST doesn't check before)
        result = await grd.before_run(_make_ctx(), "hello")
        assert result == "hello"
        # after_run should log but not raise
        output = await grd.after_run(_make_ctx(), "hello", "output")
        assert output == "output"


class TestDecoratorMiddleware:
    @pytest.mark.asyncio
    async def test_before_run_decorator(self):
        async def log_prompt(ctx, prompt):
            return f"[logged] {prompt}"
        mw = middleware_from_functions(before_run=log_prompt)
        result = await mw.before_run(_make_ctx(), "hello")
        assert result == "[logged] hello"

    @pytest.mark.asyncio
    async def test_multiple_hooks(self):
        calls = []
        async def br(ctx, prompt):
            calls.append("before_run")
            return prompt
        async def ar(ctx, prompt, output):
            calls.append("after_run")
            return output
        mw = middleware_from_functions(before_run=br, after_run=ar)
        await mw.before_run(_make_ctx(), "p")
        await mw.after_run(_make_ctx(), "p", "o")
        assert calls == ["before_run", "after_run"]

    @pytest.mark.asyncio
    async def test_noop_when_no_functions(self):
        mw = middleware_from_functions()
        result = await mw.before_run(_make_ctx(), "hello")
        assert result == "hello"


class TestSubagentPrompts:
    def test_system_prompt_not_empty(self):
        assert len(SUBAGENT_SYSTEM_PROMPT) > 50

    def test_get_subagent_system_prompt(self):
        configs = [
            SubAgentConfig(name="researcher", description="Researches topics", instructions="..."),
            SubAgentConfig(name="writer", description="Writes content", instructions="...", can_ask_questions=False),
        ]
        prompt = get_subagent_system_prompt(configs)
        assert "researcher" in prompt
        assert "writer" in prompt
        assert "cannot ask" in prompt

    def test_task_instructions(self):
        instructions = get_task_instructions_prompt("Fix the bug", can_ask_questions=True, max_questions=3)
        assert "Fix the bug" in instructions
        assert "3 questions" in instructions

    def test_task_instructions_no_questions(self):
        instructions = get_task_instructions_prompt("Do it", can_ask_questions=False)
        assert "best judgment" in instructions


class TestRuntimeWiring:
    def test_build_ctx_has_middleware(self):
        from agent_ext.workbench.runtime import build_ctx
        ctx = build_ctx()
        assert hasattr(ctx, "middleware_chain")
        assert len(ctx.middleware_chain) == 2
        assert hasattr(ctx, "middleware_context")
        assert hasattr(ctx, "message_bus")
        assert hasattr(ctx, "task_manager")
        assert hasattr(ctx, "module_registry")

    def test_modules_loaded(self):
        from agent_ext.workbench.runtime import build_ctx
        ctx = build_ctx()
        module_names = list(ctx.module_registry.modules.keys())
        assert "core" in module_names
        assert "self_improve" in module_names
