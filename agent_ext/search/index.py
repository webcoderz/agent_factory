from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .store import REPO_INDEX_FILE, RepoIndexState, read_json, write_json

DEFAULT_EXTS = (".py", ".md", ".toml", ".yaml", ".yml", ".json", ".txt")


def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _file_lang(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".py":
        return "python"
    if ext in (".md",):
        return "markdown"
    if ext in (".toml",):
        return "toml"
    if ext in (".yaml", ".yml"):
        return "yaml"
    if ext in (".json",):
        return "json"
    return ext.lstrip(".")


@dataclass
class RepoIndexerConfig:
    root: str = "."
    exts: Tuple[str, ...] = DEFAULT_EXTS
    exclude_dirs: Tuple[str, ...] = (".git", ".agent_state", "__pycache__", "dist", "build", ".venv")
    max_file_bytes: int = 2_000_000  # 2MB cap per file for indexing
    max_files: int = 50_000


class RepoIndexer:
    def __init__(self, cfg: RepoIndexerConfig):
        self.cfg = cfg
        self.root = Path(cfg.root)

    def load_state(self) -> RepoIndexState:
        data = read_json(REPO_INDEX_FILE, {"version": "0.1.0", "files": {}})
        st = RepoIndexState(version=data.get("version", "0.1.0"), files=data.get("files", {}))
        return st

    def save_state(self, st: RepoIndexState) -> None:
        write_json(REPO_INDEX_FILE, {"version": st.version, "files": st.files})

    def _should_exclude(self, p: Path) -> bool:
        parts = set(p.parts)
        return any(ed in parts for ed in self.cfg.exclude_dirs)

    def scan(self) -> List[Path]:
        out: List[Path] = []
        for p in self.root.rglob("*"):
            if len(out) >= self.cfg.max_files:
                break
            if p.is_dir():
                continue
            if self._should_exclude(p):
                continue
            if p.suffix.lower() not in self.cfg.exts:
                continue
            out.append(p)
        return out

    def update_incremental(self) -> Tuple[RepoIndexState, List[str], List[str]]:
        """
        Returns (state, changed_paths, removed_paths)
        """
        st = self.load_state()
        existing = set(st.files.keys())
        seen = set()
        changed: List[str] = []

        for p in self.scan():
            rel = str(p.relative_to(self.root))
            seen.add(rel)

            try:
                stat = p.stat()
            except Exception:
                continue

            # quick skip by mtime/size
            prev = st.files.get(rel)
            if prev and int(prev.get("size", -1)) == int(stat.st_size) and float(prev.get("mtime", -1)) == float(stat.st_mtime):
                continue

            if stat.st_size > self.cfg.max_file_bytes:
                # record meta but skip hashing huge text
                st.files[rel] = {
                    "sha256": prev.get("sha256", "") if prev else "",
                    "size": int(stat.st_size),
                    "mtime": float(stat.st_mtime),
                    "lang": _file_lang(p),
                    "skipped": True,
                }
                changed.append(rel)
                continue

            try:
                b = p.read_bytes()
            except Exception:
                continue

            st.files[rel] = {
                "sha256": _sha256_bytes(b),
                "size": int(stat.st_size),
                "mtime": float(stat.st_mtime),
                "lang": _file_lang(p),
                "skipped": False,
            }
            changed.append(rel)

        removed = sorted(list(existing - seen))
        for rp in removed:
            st.files.pop(rp, None)

        self.save_state(st)
        return st, changed, removed

    def read_text(self, rel_path: str) -> Optional[str]:
        p = self.root / rel_path
        try:
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
