from __future__ import annotations

import subprocess

from .base import ExecBackend, ExecResult


class LocalSubprocessExecBackend(ExecBackend):
    def __init__(self, *, enabled: bool):
        self.enabled = enabled

    def run(
        self, cmd: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None, timeout_s: int = 30
    ) -> ExecResult:
        if not self.enabled:
            raise PermissionError("Exec disabled by policy")
        p = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return ExecResult(
            ok=(p.returncode == 0),
            returncode=p.returncode,
            stdout=p.stdout[-50_000:],
            stderr=p.stderr[-50_000:],
        )
