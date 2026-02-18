from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple


def _run(cmd: list[str], *, cwd: Optional[Path] = None) -> Tuple[bool, str]:
    env = os.environ.copy()  # inherits HTTP_PROXY/HTTPS_PROXY/etc.
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, capture_output=True, text=True)
    out = (p.stdout or "") + ("\n" if p.stdout and p.stderr else "") + (p.stderr or "")
    return (p.returncode == 0), out.strip()


def ensure_branch(branch: str) -> None:
    ok, out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if not ok:
        raise RuntimeError(out)
    cur = out.strip()
    if cur != branch:
        ok, out = _run(["git", "checkout", branch])
        if not ok:
            raise RuntimeError(out)


def apply_diff_to_repo(diff_text: str, *, repo_root: Path = Path(".")) -> None:
    ok, out = _run(["git", "apply", "--whitespace=nowarn", "-"], cwd=repo_root)
    if not ok:
        # retry with 3-way (helpful sometimes) if git supports it
        ok2, out2 = _run(["git", "apply", "--3way", "--whitespace=nowarn", "-"], cwd=repo_root)
        if not ok2:
            raise RuntimeError(f"git apply failed:\n{out}\n\n3way failed:\n{out2}")


def commit_and_push(*, message: str, branch: str = "dev", repo_root: Path = Path(".")) -> None:
    ensure_branch(branch)

    ok, out = _run(["git", "status", "--porcelain"], cwd=repo_root)
    if not ok:
        raise RuntimeError(out)
    if not out.strip():
        return  # nothing to commit

    ok, out = _run(["git", "add", "-A"], cwd=repo_root)
    if not ok:
        raise RuntimeError(out)

    ok, out = _run(["git", "commit", "-m", message], cwd=repo_root)
    if not ok:
        raise RuntimeError(out)

    ok, out = _run(["git", "push", "origin", branch], cwd=repo_root)
    if not ok:
        raise RuntimeError(out)
