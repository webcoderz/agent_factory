"""Tests for all FunctionToolset factories."""

from __future__ import annotations

from pydantic_ai.toolsets import FunctionToolset

from agent_ext.backends.console import ConsoleDeps, create_console_toolset
from agent_ext.database.toolset import SQLDatabaseDeps, create_database_toolset
from agent_ext.rlm.toolset import cleanup_repl_environments, create_rlm_toolset
from agent_ext.subagents.toolset import SubAgentDeps, create_subagent_toolset
from agent_ext.todo.pai_toolset import TodoDeps, create_todo_toolset


class TestRLMToolset:
    def test_creates_function_toolset(self):
        ts = create_rlm_toolset()
        assert isinstance(ts, FunctionToolset)

    def test_custom_timeout(self):
        ts = create_rlm_toolset(code_timeout=120.0)
        assert isinstance(ts, FunctionToolset)

    def test_with_sub_model(self):
        ts = create_rlm_toolset(sub_model="openai:gpt-4o-mini")
        assert isinstance(ts, FunctionToolset)

    def test_cleanup(self):
        cleanup_repl_environments()  # Should not raise


class TestDatabaseToolset:
    def test_creates_function_toolset(self):
        ts = create_database_toolset()
        assert isinstance(ts, FunctionToolset)

    def test_with_id(self):
        ts = create_database_toolset(toolset_id="my_db")
        assert isinstance(ts, FunctionToolset)

    def test_deps_model(self):
        deps = SQLDatabaseDeps(database=None, read_only=True, max_rows=50)
        assert deps.read_only is True
        assert deps.max_rows == 50


class TestConsoleToolset:
    def test_creates_function_toolset(self):
        ts = create_console_toolset()
        assert isinstance(ts, FunctionToolset)

    def test_deps_model(self):
        from agent_ext.backends import StateBackend

        backend = StateBackend()
        deps = ConsoleDeps(backend=backend, exec_enabled=False)
        assert deps.exec_enabled is False


class TestSubagentToolset:
    def test_creates_function_toolset(self):
        ts = create_subagent_toolset()
        assert isinstance(ts, FunctionToolset)

    def test_with_configs(self):
        """Config compilation requires valid model — test with env var or skip."""
        import os

        from agent_ext.subagents import SubAgentConfig

        configs = [
            SubAgentConfig(name="helper", description="Helps", instructions="Be helpful"),
        ]
        if not os.environ.get("OPENAI_API_KEY"):
            # Can't compile agents without API key; test factory without configs
            ts = create_subagent_toolset(configs=[])
            assert isinstance(ts, FunctionToolset)
        else:
            ts = create_subagent_toolset(configs=configs)
            assert isinstance(ts, FunctionToolset)

    def test_deps_model(self):
        deps = SubAgentDeps(default_model="openai:gpt-4o-mini")
        assert deps.default_model == "openai:gpt-4o-mini"


class TestTodoToolset:
    def test_creates_function_toolset(self):
        ts = create_todo_toolset()
        assert isinstance(ts, FunctionToolset)

    def test_deps_model(self):
        deps = TodoDeps(store=None, case_id="case-1")
        assert deps.case_id == "case-1"
