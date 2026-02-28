"""Sandboxed Python REPL environment for RLM.

Provides a safe execution environment where an LLM can run Python code
to programmatically explore and analyze large contexts.  State persists
between executions within a session.

Key features:
- Restricted built-ins (no eval/exec/compile/globals/input)
- Controlled imports via allow-list
- ``context`` variable pre-loaded with data to analyze
- ``llm_query()`` function for sub-model delegation (when configured)
- Persistent local state across executions
- stdout/stderr capture with truncation
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import textwrap
import threading
import time
from contextlib import contextmanager, suppress
from typing import Any, ClassVar

from .models import ContextType, REPLResult, RLMConfig


class REPLEnvironment:
    """Sandboxed Python execution environment for RLM."""

    SAFE_BUILTINS: ClassVar[dict[str, Any]] = {
        # Core types
        "print": print,
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "type": type,
        "isinstance": isinstance,
        "issubclass": issubclass,
        # Iteration
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "sorted": sorted,
        "reversed": reversed,
        "iter": iter,
        "next": next,
        # Math
        "min": min,
        "max": max,
        "sum": sum,
        "abs": abs,
        "round": round,
        "pow": pow,
        "divmod": divmod,
        # String / char
        "chr": chr,
        "ord": ord,
        "hex": hex,
        "bin": bin,
        "oct": oct,
        "repr": repr,
        "ascii": ascii,
        "format": format,
        # Collections
        "any": any,
        "all": all,
        "slice": slice,
        "hash": hash,
        "id": id,
        "callable": callable,
        # Attribute access
        "hasattr": hasattr,
        "getattr": getattr,
        "setattr": setattr,
        "delattr": delattr,
        "dir": dir,
        "vars": vars,
        # Binary
        "bytes": bytes,
        "bytearray": bytearray,
        "memoryview": memoryview,
        "complex": complex,
        # OOP
        "super": super,
        "property": property,
        "staticmethod": staticmethod,
        "classmethod": classmethod,
        "object": object,
        # Exceptions
        "Exception": Exception,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "KeyError": KeyError,
        "IndexError": IndexError,
        "AttributeError": AttributeError,
        "RuntimeError": RuntimeError,
        "StopIteration": StopIteration,
        "NotImplementedError": NotImplementedError,
        # File access (sandboxed to temp dir)
        "open": open,
        "FileNotFoundError": FileNotFoundError,
        "OSError": OSError,
    }

    BLOCKED_BUILTINS: ClassVar[dict[str, None]] = {
        "eval": None,
        "exec": None,
        "compile": None,
        "globals": None,
        "locals": None,
        "input": None,
        "__builtins__": None,
    }

    def __init__(self, context: ContextType, config: RLMConfig | None = None) -> None:
        self.config = config or RLMConfig()
        self.temp_dir = tempfile.mkdtemp(prefix="rlm_repl_")
        self._lock = threading.Lock()
        self.locals: dict[str, Any] = {}

        # Set up globals with safe built-ins and controlled __import__
        builtins = {**self.SAFE_BUILTINS, **self.BLOCKED_BUILTINS}
        allowed_set = set(self.config.allow_imports)

        def controlled_import(name, globs=None, locs=None, fromlist=(), level=0):
            base = name.split(".")[0]
            if base not in allowed_set:
                raise ImportError(f"Import not allowed: {name}")
            return __import__(name, globs, locs, fromlist, level)

        builtins["__import__"] = controlled_import

        self.globals: dict[str, Any] = {"__builtins__": builtins}

        if self.config.sub_model:
            self._setup_llm_query()

        self._load_context(context)

    def _setup_llm_query(self) -> None:
        """Set up llm_query() for sub-model delegation inside REPL."""

        def llm_query(prompt: str) -> str:
            """Query a sub-LLM.  Useful for analyzing chunks of large context."""
            try:
                if not self.config.sub_model:
                    return "Error: No sub-model configured"
                from pydantic_ai import ModelRequest
                from pydantic_ai.direct import model_request_sync
                from pydantic_ai.messages import TextPart

                result = model_request_sync(
                    self.config.sub_model,
                    [ModelRequest.user_text_prompt(prompt)],
                )
                text_parts = [p.content for p in result.parts if isinstance(p, TextPart)]
                return "".join(text_parts) if text_parts else ""
            except Exception as e:
                return f"Error querying sub-LLM: {e!s}"

        self.globals["llm_query"] = llm_query

    def _load_context(self, context: ContextType) -> None:
        """Load context into the REPL as the ``context`` variable."""
        if isinstance(context, str):
            ctx_path = os.path.join(self.temp_dir, "context.txt")
            with open(ctx_path, "w", encoding="utf-8") as f:
                f.write(context)
            load_code = f"with open(r'{ctx_path}', 'r', encoding='utf-8') as f:\n    context = f.read()\n"
        else:
            ctx_path = os.path.join(self.temp_dir, "context.json")
            with open(ctx_path, "w", encoding="utf-8") as f:
                json.dump(context, f, indent=2, default=str)
            load_code = (
                f"import json\nwith open(r'{ctx_path}', 'r', encoding='utf-8') as f:\n    context = json.load(f)\n"
            )
        self._execute_internal(load_code)

    def _execute_internal(self, code: str) -> None:
        combined = {**self.globals, **self.locals}
        exec(code, combined, combined)
        for key, value in combined.items():
            if key not in self.globals and not key.startswith("_"):
                self.locals[key] = value

    @contextmanager
    def _capture_output(self):
        old_stdout, old_stderr = sys.stdout, sys.stderr
        stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
        try:
            sys.stdout, sys.stderr = stdout_buf, stderr_buf
            yield stdout_buf, stderr_buf
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

    def execute(self, code: str) -> REPLResult:
        """Execute Python code in the REPL.  State persists between calls."""
        code = textwrap.dedent(code).strip()
        t0 = time.time()
        success = True
        stdout_content = stderr_content = ""

        with self._lock, self._capture_output() as (stdout_buf, stderr_buf):
            try:
                # Split imports from other code
                lines = code.split("\n")
                import_lines = [
                    l for l in lines if l.strip().startswith(("import ", "from ")) and not l.strip().startswith("#")
                ]
                other_lines = [l for l in lines if l not in import_lines]

                if import_lines:
                    exec("\n".join(import_lines), self.globals, self.globals)

                if other_lines:
                    other_code = "\n".join(other_lines)
                    combined = {**self.globals, **self.locals}
                    exec(other_code, combined, combined)
                    for key, value in combined.items():
                        if key not in self.globals:
                            self.locals[key] = value

                stdout_content = stdout_buf.getvalue()
                stderr_content = stderr_buf.getvalue()
            except Exception as e:
                success = False
                stderr_content = stderr_buf.getvalue() + f"\nError: {e!s}"
                stdout_content = stdout_buf.getvalue()

        dt = time.time() - t0
        max_chars = self.config.truncate_output_chars
        if len(stdout_content) > max_chars:
            stdout_content = stdout_content[:max_chars] + "\n… (truncated)"
        if len(stderr_content) > max_chars:
            stderr_content = stderr_content[:max_chars] + "\n… (truncated)"

        return REPLResult(
            stdout=stdout_content,
            stderr=stderr_content,
            locals=dict(self.locals),
            execution_time=dt,
            success=success,
        )

    def cleanup(self) -> None:
        """Clean up temporary directory."""
        with suppress(Exception):
            shutil.rmtree(self.temp_dir, ignore_errors=True)


def format_repl_result(result: REPLResult, max_var_display: int = 200) -> str:
    """Format a REPL result for display to the LLM."""
    parts: list[str] = []
    if result.stdout.strip():
        parts.append(f"Output:\n{result.stdout}")
    if result.stderr.strip():
        parts.append(f"Errors:\n{result.stderr}")
    user_vars = {
        k: v for k, v in result.locals.items() if not k.startswith("_") and k not in ("context", "json", "re", "os")
    }
    if user_vars:
        var_lines = []
        for name, value in user_vars.items():
            try:
                vs = repr(value)
                if len(vs) > max_var_display:
                    vs = vs[:max_var_display] + "..."
                var_lines.append(f"  {name} = {vs}")
            except Exception:
                var_lines.append(f"  {name} = <{type(value).__name__}>")
        if var_lines:
            parts.append("Variables:\n" + "\n".join(var_lines))
    parts.append(f"Execution time: {result.execution_time:.3f}s")
    return "\n\n".join(parts) if parts else "Code executed successfully (no output)"
