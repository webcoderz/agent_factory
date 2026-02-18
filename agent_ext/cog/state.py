from __future__ import annotations
import json, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

STATE_PATH = Path(".agent_state/cog_state.json")
REGRESS_PATH = Path(".agent_state/regression_memory.json")

def _read(path: Path, default: Any):
    if not path.exists(): return default
    return json.loads(path.read_text(encoding="utf-8"))

def _write(path: Path, obj: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")

@dataclass
class Budget:
    max_steps: int = 10
    max_model_calls: int = 6
    max_parallel_writers: int = 3
    max_diff_chars: int = 60000
    auto_commit_threshold: float = 80.0

@dataclass
class CogState:
    version: str = "0.2.0"
    last_repo_fingerprint: str = ""
    last_success_ts: float = 0.0
    fail_streak: int = 0
    recent_actions: List[Dict[str, Any]] = field(default_factory=list)

    def load(self):
        data = _read(STATE_PATH, None)
        if not data: return
        self.version = data.get("version", self.version)
        self.last_repo_fingerprint = data.get("last_repo_fingerprint", "")
        self.last_success_ts = float(data.get("last_success_ts", 0.0))
        self.fail_streak = int(data.get("fail_streak", 0))
        self.recent_actions = data.get("recent_actions", [])

    def save(self):
        _write(STATE_PATH, {
            "version": self.version,
            "last_repo_fingerprint": self.last_repo_fingerprint,
            "last_success_ts": self.last_success_ts,
            "fail_streak": self.fail_streak,
            "recent_actions": self.recent_actions[-200:],  # cap
        })

@dataclass
class RegressionMemory:
    """
    Prevents oscillation: detects same files flipping back/forth or repeated revert cycles.
    """
    flips: Dict[str, int] = field(default_factory=dict)  # file -> flip count
    last_commits: List[Dict[str, Any]] = field(default_factory=list)

    def load(self):
        data = _read(REGRESS_PATH, None)
        if not data: return
        self.flips = data.get("flips", {})
        self.last_commits = data.get("last_commits", [])

    def save(self):
        _write(REGRESS_PATH, {
            "flips": self.flips,
            "last_commits": self.last_commits[-200:],
        })

    def note_commit(self, files_touched: List[str], commit_msg: str):
        for f in files_touched:
            self.flips[f] = int(self.flips.get(f, 0)) + 1
        self.last_commits.append({"ts": time.time(), "files": files_touched, "msg": commit_msg})

    def is_thrash_risk(self, files_touched: List[str], max_flips: int = 8) -> bool:
        return any(int(self.flips.get(f, 0)) >= max_flips for f in files_touched)
