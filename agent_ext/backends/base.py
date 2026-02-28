from __future__ import annotations

import builtins
from typing import Protocol


class FilesystemBackend(Protocol):
    def read_text(self, path: str) -> str: ...
    def write_text(self, path: str, content: str) -> None: ...
    def list(self, path: str) -> builtins.list[str]: ...
    def glob(self, pattern: str) -> builtins.list[str]: ...


class ExecResult(dict):
    pass


class ExecBackend(Protocol):
    def run(
        self, cmd: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None, timeout_s: int = 30
    ) -> ExecResult: ...
