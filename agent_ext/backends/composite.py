"""Composite backend — routes operations to different backends by path prefix.

Example::

    from agent_ext.backends import CompositeBackend, StateBackend, LocalFilesystemBackend

    backend = CompositeBackend(
        default=StateBackend(),
        routes={
            "/project/": LocalFilesystemBackend(root="/my/project", allow_write=True),
            "/temp/": StateBackend(),
        },
    )

    backend.write_text("/project/app.py", "...")  # → LocalFilesystemBackend
    backend.write_text("/scratch.txt", "...")       # → StateBackend (default)
"""

from __future__ import annotations

from .base import FilesystemBackend


class CompositeBackend(FilesystemBackend):
    """Backend that routes operations to different backends by path prefix.

    Longest-prefix match is used, falling back to ``default``.
    """

    def __init__(
        self,
        default: FilesystemBackend,
        routes: dict[str, FilesystemBackend] | None = None,
    ) -> None:
        self._default = default
        self._routes = routes or {}
        # Sort by length (longest first) for correct matching
        self._sorted_prefixes = sorted(self._routes.keys(), key=len, reverse=True)

    def _get_backend(self, path: str) -> FilesystemBackend:
        for prefix in self._sorted_prefixes:
            if path.startswith(prefix):
                return self._routes[prefix]
        return self._default

    def read_text(self, path: str) -> str:
        return self._get_backend(path).read_text(path)

    def write_text(self, path: str, content: str) -> None:
        self._get_backend(path).write_text(path, content)

    def list(self, path: str) -> list[str]:
        return self._get_backend(path).list(path)

    def glob(self, pattern: str) -> list[str]:
        # Aggregate from all backends
        results: set[str] = set()
        results.update(self._default.glob(pattern))
        for backend in self._routes.values():
            results.update(backend.glob(pattern))
        return sorted(results)
