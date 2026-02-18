from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from .models import TriggerEvent

TRIGGERS_FILE = Path(".agent_state/triggers.json")


class TriggerStore:
    def __init__(self, path: Path = TRIGGERS_FILE):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._data = {}
            return
        try:
            raw = self.path.read_text(encoding="utf-8").strip()
            if not raw:
                self._data = {}
                return
            self._data = json.loads(raw)
        except (json.JSONDecodeError, OSError):
            self._data = {}

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def bump(self, signature: str) -> int:
        self._data[signature] = int(self._data.get(signature, 0)) + 1
        self.save()
        return self._data[signature]

    def get_count(self, signature: str) -> int:
        return int(self._data.get(signature, 0))

    def make_exception_trigger(self, exc: BaseException) -> TriggerEvent:
        sig = f"{type(exc).__name__}:{str(exc)[:200]}"
        count = self.bump(sig)
        return TriggerEvent(kind="exception", signature=sig, detail=repr(exc), count=count)
