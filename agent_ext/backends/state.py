"""In-memory file storage backend for testing and sandboxed execution.

Files are stored in a dictionary and are ephemeral.  Useful for tests,
preview environments, and stateless sandboxes.
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .base import FilesystemBackend


@dataclass
class FileData:
    content: list[str]
    created_at: str = ""
    modified_at: str = ""


@dataclass
class FileInfo:
    name: str
    path: str
    is_dir: bool
    size: int | None = None


@dataclass
class GrepMatch:
    path: str
    line_number: int
    line: str


@dataclass
class EditResult:
    path: str | None = None
    error: str | None = None
    occurrences: int = 0


@dataclass
class WriteResult:
    path: str | None = None
    error: str | None = None


def _normalize_path(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return path


def _validate_path(path: str) -> str | None:
    if ".." in path:
        return "Path cannot contain '..'"
    if path.startswith("~"):
        return "Path cannot start with '~'"
    return None


class StateBackend(FilesystemBackend):
    """In-memory file storage backend.

    Compatible with ``FilesystemBackend`` protocol and also provides
    rich operations: ``ls_info``, ``edit``, ``grep_raw``, ``glob_info``.

    Example::

        backend = StateBackend()
        backend.write_text("src/app.py", "print('hello')")
        content = backend.read_text("src/app.py")
    """

    def __init__(self, files: dict[str, FileData] | None = None) -> None:
        self._files: dict[str, FileData] = files or {}

    @property
    def files(self) -> dict[str, FileData]:
        return self._files

    def _ts(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # -- FilesystemBackend protocol -----------------------------------------

    def read_text(self, path: str) -> str:
        p = _normalize_path(path)
        fd = self._files.get(p)
        if fd is None:
            raise FileNotFoundError(f"File not found: {p}")
        return "\n".join(fd.content)

    def write_text(self, path: str, content: str) -> None:
        p = _normalize_path(path)
        err = _validate_path(p)
        if err:
            raise PermissionError(err)
        now = self._ts()
        lines = content.split("\n")
        existing = self._files.get(p)
        self._files[p] = FileData(
            content=lines,
            created_at=existing.created_at if existing else now,
            modified_at=now,
        )

    def list(self, path: str) -> list[str]:
        p = _normalize_path(path)
        prefix = p if p == "/" else p + "/"
        entries: set[str] = set()
        for fp in self._files:
            if fp.startswith(prefix):
                rel = fp[len(prefix):]
                top = rel.split("/")[0]
                entries.add(top)
        return sorted(entries)

    def glob(self, pattern: str) -> list[str]:
        results: list[str] = []
        for fp in self._files:
            if fnmatch.fnmatch(fp, pattern) or fnmatch.fnmatch(fp, "/" + pattern):
                results.append(fp.lstrip("/"))
        return sorted(results)

    # -- rich operations ----------------------------------------------------

    def read_numbered(self, path: str, offset: int = 0, limit: int = 2000) -> str:
        """Read file with line numbers (like the upstream ``read``)."""
        p = _normalize_path(path)
        fd = self._files.get(p)
        if fd is None:
            return f"Error: File '{p}' not found"
        lines = fd.content
        total = len(lines)
        if offset >= total:
            return f"Error: Offset {offset} exceeds file length ({total} lines)"
        end = min(offset + limit, total)
        result_lines = [f"{i + 1:>6}\t{lines[i]}" for i in range(offset, end)]
        result = "\n".join(result_lines)
        if end < total:
            result += f"\n\n... ({total - end} more lines)"
        return result

    def edit(self, path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        """Edit a file by replacing strings."""
        p = _normalize_path(path)
        fd = self._files.get(p)
        if fd is None:
            return EditResult(error=f"File '{p}' not found")
        content = "\n".join(fd.content)
        count = content.count(old_string)
        if count == 0:
            return EditResult(error=f"String not found in file")
        if count > 1 and not replace_all:
            return EditResult(error=f"String found {count} times. Use replace_all=True.")
        new_content = content.replace(old_string, new_string) if replace_all else content.replace(old_string, new_string, 1)
        fd.content = new_content.split("\n")
        fd.modified_at = self._ts()
        return EditResult(path=p, occurrences=count if replace_all else 1)

    def grep_raw(self, pattern: str, path: str | None = None) -> list[GrepMatch] | str:
        """Search for regex pattern in files."""
        try:
            rx = re.compile(pattern)
        except re.error as e:
            return f"Error: Invalid regex: {e}"
        results: list[GrepMatch] = []
        files_to_search = list(self._files.keys())
        if path:
            p = _normalize_path(path)
            files_to_search = [f for f in files_to_search if f.startswith(p)]
        for fp in files_to_search:
            for i, line in enumerate(self._files[fp].content):
                if rx.search(line):
                    results.append(GrepMatch(path=fp, line_number=i + 1, line=line))
        return results

    def ls_info(self, path: str) -> list[FileInfo]:
        """List files/dirs at path with metadata."""
        p = _normalize_path(path)
        prefix = p if p == "/" else p + "/"
        entries: dict[str, FileInfo] = {}
        for fp, fd in self._files.items():
            if not fp.startswith(prefix):
                continue
            rel = fp[len(prefix):]
            parts = rel.split("/")
            name = parts[0]
            if name not in entries:
                if len(parts) == 1:
                    entries[name] = FileInfo(name=name, path=fp, is_dir=False, size=sum(len(l) for l in fd.content))
                else:
                    entries[name] = FileInfo(name=name, path=prefix + name, is_dir=True)
        return sorted(entries.values(), key=lambda x: (not x.is_dir, x.name))
