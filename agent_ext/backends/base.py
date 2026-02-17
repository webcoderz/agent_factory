from __future__ import annotations
from typing import Any, Dict, List, Optional, Protocol


class FilesystemBackend(Protocol):
    def read_text(self, path: str) -> str: ...
    def write_text(self, path: str, content: str) -> None: ...
    def list(self, path: str) -> List[str]: ...
    def glob(self, pattern: str) -> List[str]: ...


class ExecResult(dict):
    pass


class ExecBackend(Protocol):
    def run(self, cmd: List[str], *, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None, timeout_s: int = 30) -> ExecResult: ...
