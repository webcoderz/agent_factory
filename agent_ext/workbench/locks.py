from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

LOCKS_DIR = Path(".agent_state/locks")


@dataclass(frozen=True)
class Lease:
    key: str
    owner: str
    expires_at: float


class LeaseLockStore:
    def __init__(self, root: Path = LOCKS_DIR):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in key)
        return self.root / f"{safe}.json"

    def try_acquire(self, *, key: str, owner: str, ttl_s: int = 900) -> Optional[Lease]:
        """
        Best-effort lock. If expired, we steal it.
        """
        p = self._path(key)
        now = time.time()

        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if float(data.get("expires_at", 0)) > now:
                    return None  # still held
            except Exception:
                pass  # treat as expired/corrupt

        lease = Lease(key=key, owner=owner, expires_at=now + ttl_s)
        p.write_text(json.dumps({"key": key, "owner": owner, "expires_at": lease.expires_at}, indent=2), encoding="utf-8")
        return lease

    def release(self, lease: Lease) -> None:
        p = self._path(lease.key)
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("owner") == lease.owner:
                    p.unlink()
            except Exception:
                # if corrupt, just remove
                p.unlink(missing_ok=True)
