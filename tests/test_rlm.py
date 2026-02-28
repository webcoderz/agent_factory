"""Tests for the overhauled RLM system."""

from __future__ import annotations

import pytest

from agent_ext.rlm import (
    GroundedResponse,
    REPLEnvironment,
    REPLResult,
    RLMConfig,
    RLMPolicy,
    RLMRunError,
    format_repl_result,
    run_restricted_python,
)


class TestREPLEnvironment:
    def test_basic_execution(self):
        repl = REPLEnvironment(context="Hello World", config=RLMConfig())
        result = repl.execute("print(len(context))")
        assert result.success
        assert "11" in result.stdout
        repl.cleanup()

    def test_persistent_state(self):
        repl = REPLEnvironment(context="test data", config=RLMConfig())
        repl.execute("x = len(context)")
        result = repl.execute("print(x)")
        assert result.success
        assert "9" in result.stdout
        repl.cleanup()

    def test_dict_context(self):
        repl = REPLEnvironment(context={"key": "value", "num": 42})
        result = repl.execute("print(context['key'])")
        assert result.success
        assert "value" in result.stdout
        repl.cleanup()

    def test_list_context(self):
        repl = REPLEnvironment(context=[1, 2, 3])
        result = repl.execute("print(sum(context))")
        assert result.success
        assert "6" in result.stdout
        repl.cleanup()

    def test_allowed_import(self):
        repl = REPLEnvironment(context="test", config=RLMConfig(allow_imports=["math"]))
        result = repl.execute("import math\nprint(math.pi)")
        assert result.success
        assert "3.14" in result.stdout
        repl.cleanup()

    def test_blocked_import(self):
        repl = REPLEnvironment(context="test", config=RLMConfig(allow_imports=[]))
        result = repl.execute("import os")
        assert not result.success
        assert "not allowed" in result.stderr.lower() or "import" in result.stderr.lower()
        repl.cleanup()

    def test_error_handling(self):
        repl = REPLEnvironment(context="test")
        result = repl.execute("1/0")
        assert not result.success
        assert "ZeroDivision" in result.stderr or "division" in result.stderr
        repl.cleanup()

    def test_output_truncation(self):
        repl = REPLEnvironment(context="test", config=RLMConfig(truncate_output_chars=50))
        result = repl.execute("print('a' * 200)")
        assert len(result.stdout) <= 70  # 50 chars + truncation marker
        assert "truncated" in result.stdout
        repl.cleanup()


class TestFormatREPLResult:
    def test_formats_stdout(self):
        result = REPLResult(stdout="Hello", stderr="", locals={}, execution_time=0.1, success=True)
        formatted = format_repl_result(result)
        assert "Hello" in formatted
        assert "0.100s" in formatted

    def test_formats_variables(self):
        result = REPLResult(stdout="", stderr="", locals={"x": 42, "context": "skip"}, execution_time=0.01)
        formatted = format_repl_result(result)
        assert "x = 42" in formatted
        assert "context" not in formatted  # filtered out


class TestGroundedResponse:
    def test_construction(self):
        gr = GroundedResponse(info="Revenue grew [1]", grounding={"1": "by 45%"})
        assert "[1]" in gr.info
        assert gr.grounding["1"] == "by 45%"

    def test_serialization(self):
        gr = GroundedResponse(info="test [1]", grounding={"1": "quote"})
        data = gr.model_dump()
        gr2 = GroundedResponse.model_validate(data)
        assert gr2.info == gr.info


class TestLegacyRLM:
    def test_run_restricted_python(self):
        result = run_restricted_python("x = 1 + 1", policy=RLMPolicy())
        assert result["globals"]["x"] == 2

    def test_disallowed_import(self):
        with pytest.raises(RLMRunError):
            run_restricted_python("import subprocess", policy=RLMPolicy())
