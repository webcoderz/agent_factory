from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STATE_DIR = Path(".agent_state")
REPO_INDEX_FILE = STATE_DIR / "repo_index.json"
BM25_INDEX_FILE = STATE_DIR / "bm25_index.json"
BM25_META_FILE = STATE_DIR / "bm25_meta.json"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return default
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


@dataclass
class RepoFileMeta:
    path: str
    sha256: str
    size: int
    mtime: float
    lang: str


@dataclass
class RepoIndexState:
    version: str = "0.1.0"
    files: dict[str, dict[str, Any]] = None  # path -> meta dict

    def __post_init__(self):
        if self.files is None:
            self.files = {}
