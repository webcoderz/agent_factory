from __future__ import annotations
import glob
import os

from .base import FilesystemBackend


class LocalFilesystemBackend(FilesystemBackend):
    def __init__(self, root: str, *, allow_write: bool):
        self.root = os.path.abspath(root)
        self.allow_write = allow_write

    def _resolve(self, path: str) -> str:
        ap = os.path.abspath(os.path.join(self.root, path))
        if not ap.startswith(self.root + os.sep) and ap != self.root:
            raise PermissionError("Path escapes fs root")
        return ap

    def read_text(self, path: str) -> str:
        ap = self._resolve(path)
        with open(ap, "r", encoding="utf-8") as f:
            return f.read()

    def write_text(self, path: str, content: str) -> None:
        if not self.allow_write:
            raise PermissionError("FS write disabled by policy")
        ap = self._resolve(path)
        os.makedirs(os.path.dirname(ap), exist_ok=True)
        with open(ap, "w", encoding="utf-8") as f:
            f.write(content)

    def list(self, path: str) -> list[str]:
        ap = self._resolve(path)
        return sorted(os.listdir(ap))

    def glob(self, pattern: str) -> list[str]:
        ap = self._resolve(".")
        matches = glob.glob(os.path.join(ap, pattern), recursive=True)
        # return relative paths
        return [os.path.relpath(m, ap) for m in matches]
