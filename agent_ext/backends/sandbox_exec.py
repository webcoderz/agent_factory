from __future__ import annotations
import subprocess
from typing import Dict, List, Optional

from .base import ExecBackend, ExecResult


class LocalSubprocessExecBackend(ExecBackend):
    def __init__(self, *, enabled: bool):
        self.enabled = enabled

    def run(self, cmd: List[str], *, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None, timeout_s: int = 30) -> ExecResult:
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
