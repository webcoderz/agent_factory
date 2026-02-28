from __future__ import annotations

import subprocess
from datetime import datetime


def run(cmd: list[str]) -> tuple[bool, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    ok = p.returncode == 0
    return ok, (p.stdout + "\n" + p.stderr).strip()


def ensure_branch(prefix: str = "auto") -> str:
    slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    branch = f"{prefix}/{slug}"
    ok, out = run(["git", "checkout", "-b", branch])
    if not ok:
        raise RuntimeError(out)
    return branch


def commit_all(message: str) -> None:
    ok, out = run(["git", "add", "-A"])
    if not ok:
        raise RuntimeError(out)
    ok, out = run(["git", "commit", "-m", message])
    if not ok:
        raise RuntimeError(out)


def push(branch: str) -> None:
    ok, out = run(["git", "push", "-u", "origin", branch])
    if not ok:
        raise RuntimeError(out)
