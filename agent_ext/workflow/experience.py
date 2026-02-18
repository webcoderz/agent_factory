from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from .types import ExecutionResult, TaskRequest

EXP_FILE = Path(".agent_state/workflow_experience.json")


def _bucket(req: TaskRequest) -> str:
    hints = ",".join(sorted(req.hints)) if req.hints else ""
    return f"{req.task_type}|{hints}"


@dataclass
class ExperienceStore:
    path: Path = EXP_FILE

    def _read_data(self) -> dict:
        if not self.path.exists():
            return {"buckets": {}}
        try:
            raw = self.path.read_text(encoding="utf-8").strip()
            if not raw:
                return {"buckets": {}}
            return json.loads(raw)
        except (json.JSONDecodeError, OSError):
            return {"buckets": {}}

    def __post_init__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({"buckets": {}}, indent=2), encoding="utf-8")

    def record(self, req: TaskRequest, result: ExecutionResult, reward: float) -> None:
        data = self._read_data()
        b = _bucket(req)
        data["buckets"].setdefault(b, [])
        data["buckets"][b].append({
            "workflow": result.workflow_name,
            "ok": result.ok,
            "reward": reward,
            "dt_ms": result.metrics.get("dt_ms"),
        })
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_bucket_stats(self, req: TaskRequest) -> List[Dict]:
        data = self._read_data()
        return data.get("buckets", {}).get(_bucket(req), [])
