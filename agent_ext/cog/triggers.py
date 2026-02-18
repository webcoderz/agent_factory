from __future__ import annotations
import hashlib, os, subprocess
from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass(frozen=True)
class Trigger:
    kind: str
    detail: str

def _run(cmd: list[str]) -> Tuple[bool, str]:
    p = subprocess.run(cmd, env=os.environ.copy(), capture_output=True, text=True)
    out = (p.stdout or "") + ("\n" if p.stdout and p.stderr else "") + (p.stderr or "")
    return p.returncode == 0, out.strip()

def repo_fingerprint() -> str:
    # cheap-ish: hash of git status + HEAD
    ok, head = _run(["git", "rev-parse", "HEAD"])
    if not ok: return ""
    ok, st = _run(["git", "status", "--porcelain"])
    s = head + "\n" + st
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def detect_triggers(prev_fp: str) -> list[Trigger]:
    tr: list[Trigger] = []
    fp = repo_fingerprint()
    if fp and fp != prev_fp:
        tr.append(Trigger("repo_changed", "git status/head changed"))
    # add more later: failing CI marker, new issues, eval drift, etc.
    return tr
