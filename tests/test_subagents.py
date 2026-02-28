"""Tests for the overhauled subagents system."""

from __future__ import annotations

import pytest

from agent_ext.subagents import (
    AgentMessage,
    DynamicAgentRegistry,
    InMemoryMessageBus,
    MessageType,
    SubAgentConfig,
    SubagentRegistry,
    TaskCharacteristics,
    decide_execution_mode,
)


class TestSubagentRegistry:
    def test_register_and_get(self):
        class FakeAgent:
            name = "test"

        reg = SubagentRegistry()
        reg.register(FakeAgent())
        assert reg.get("test").name == "test"

    def test_get_unknown_raises(self):
        reg = SubagentRegistry()
        with pytest.raises(KeyError):
            reg.get("nonexistent")

    def test_list_and_count(self):
        class A:
            name = "a"

        class B:
            name = "b"

        reg = SubagentRegistry()
        reg.register(A())
        reg.register(B())
        assert reg.list() == ["a", "b"]
        assert reg.count() == 2


class TestDynamicRegistry:
    def test_register_and_get(self):
        dyn = DynamicAgentRegistry()
        config = SubAgentConfig(name="worker", description="does work", instructions="work hard")
        dyn.register(config, "agent_obj")
        assert dyn.get("worker") == "agent_obj"
        assert dyn.exists("worker")
        assert dyn.count() == 1

    def test_max_agents_limit(self):
        dyn = DynamicAgentRegistry(max_agents=1)
        config1 = SubAgentConfig(name="a", description="a", instructions="a")
        dyn.register(config1, "obj1")
        config2 = SubAgentConfig(name="b", description="b", instructions="b")
        with pytest.raises(ValueError, match="Maximum"):
            dyn.register(config2, "obj2")

    def test_duplicate_name_raises(self):
        dyn = DynamicAgentRegistry()
        config = SubAgentConfig(name="x", description="x", instructions="x")
        dyn.register(config, "obj")
        with pytest.raises(ValueError, match="already exists"):
            dyn.register(config, "obj2")

    def test_remove(self):
        dyn = DynamicAgentRegistry()
        config = SubAgentConfig(name="x", description="x", instructions="x")
        dyn.register(config, "obj")
        assert dyn.remove("x") is True
        assert dyn.remove("x") is False
        assert dyn.count() == 0

    def test_clear(self):
        dyn = DynamicAgentRegistry()
        for i in range(3):
            config = SubAgentConfig(name=f"a{i}", description="d", instructions="i")
            dyn.register(config, f"obj{i}")
        dyn.clear()
        assert dyn.count() == 0

    def test_get_summary(self):
        dyn = DynamicAgentRegistry()
        assert "No dynamically" in dyn.get_summary()
        config = SubAgentConfig(name="w", description="worker", instructions="work")
        dyn.register(config, "obj")
        summary = dyn.get_summary()
        assert "w" in summary
        assert "worker" in summary


class TestMessageBus:
    @pytest.mark.asyncio
    async def test_send_and_receive(self):
        bus = InMemoryMessageBus()
        bus.register_agent("worker")
        msg = AgentMessage(
            type=MessageType.TASK_ASSIGNED,
            sender="parent",
            receiver="worker",
            payload="do something",
            task_id="t1",
        )
        await bus.send(msg)
        messages = await bus.get_messages("worker")
        assert len(messages) == 1
        assert messages[0].payload == "do something"

    @pytest.mark.asyncio
    async def test_send_to_unregistered_raises(self):
        bus = InMemoryMessageBus()
        msg = AgentMessage(
            type=MessageType.TASK_ASSIGNED,
            sender="parent",
            receiver="nobody",
            payload="x",
            task_id="t1",
        )
        with pytest.raises(KeyError):
            await bus.send(msg)

    @pytest.mark.asyncio
    async def test_register_duplicate_raises(self):
        bus = InMemoryMessageBus()
        bus.register_agent("a")
        with pytest.raises(ValueError):
            bus.register_agent("a")

    def test_registered_agents(self):
        bus = InMemoryMessageBus()
        bus.register_agent("a")
        bus.register_agent("b")
        assert sorted(bus.registered_agents()) == ["a", "b"]
        assert bus.is_registered("a")
        assert not bus.is_registered("c")


class TestDecideExecutionMode:
    def test_force_mode(self):
        chars = TaskCharacteristics()
        config = SubAgentConfig(name="x", description="x", instructions="x")
        assert decide_execution_mode(chars, config, force_mode="sync") == "sync"
        assert decide_execution_mode(chars, config, force_mode="async") == "async"

    def test_complex_independent_is_async(self):
        chars = TaskCharacteristics(estimated_complexity="complex", can_run_independently=True)
        config = SubAgentConfig(name="x", description="x", instructions="x")
        assert decide_execution_mode(chars, config) == "async"

    def test_simple_is_sync(self):
        chars = TaskCharacteristics(estimated_complexity="simple")
        config = SubAgentConfig(name="x", description="x", instructions="x")
        assert decide_execution_mode(chars, config) == "sync"

    def test_needs_context_is_sync(self):
        chars = TaskCharacteristics(requires_user_context=True, estimated_complexity="complex")
        config = SubAgentConfig(name="x", description="x", instructions="x")
        assert decide_execution_mode(chars, config) == "sync"
