from __future__ import annotations

import io
import time
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from .policies import RLMPolicy


class RLMRunError(RuntimeError):
    pass


def run_restricted_python(code: str, *, policy: RLMPolicy, globals_in: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Minimal safe-ish runner:
    - allows only a controlled import set via custom __import__
    - captures stdout/stderr
    NOTE: For real sandboxing, run this in your sandbox_exec backend / container.
    """
    allowed = set(policy.allow_imports)

    def limited_import(name, globals=None, locals=None, fromlist=(), level=0):
        base = name.split(".")[0]
        if base not in allowed:
            raise ImportError(f"Import not allowed: {name}")
        return __import__(name, globals, locals, fromlist, level)

    g: dict[str, Any] = dict(globals_in or {})
    g["__builtins__"] = dict(__builtins__)
    g["__builtins__"]["__import__"] = limited_import

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    t0 = time.time()
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(code, g, g)
    except Exception as e:
        raise RLMRunError(str(e)) from e
    finally:
        dt = time.time() - t0
        if dt > policy.max_runtime_s:
            raise RLMRunError(f"RLM code exceeded runtime: {dt:.2f}s")

    stdout = stdout_buf.getvalue()[: policy.max_stdout_chars]
    stderr = stderr_buf.getvalue()[: policy.max_stdout_chars]
    return {"stdout": stdout, "stderr": stderr, "globals": {k: v for k, v in g.items() if k not in {"__builtins__"}}}
