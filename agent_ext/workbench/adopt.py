from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple

# Pull strategy: "merge" (default) or "rebase". Merge is safer for automation.
ADOPT_PULL_STRATEGY = os.getenv("ADOPT_PULL_STRATEGY", "merge").strip().lower()
# Max push retries after pull on non-fast-forward
ADOPT_PUSH_RETRIES = int(os.getenv("ADOPT_PUSH_RETRIES", "2"))


def _run(cmd: list[str], *, cwd: Optional[Path] = None) -> Tuple[bool, str]:
    env = os.environ.copy()  # inherits HTTP_PROXY/HTTPS_PROXY/etc.
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, capture_output=True, text=True)
    out = (p.stdout or "") + ("\n" if p.stdout and p.stderr else "") + (p.stderr or "")
    return (p.returncode == 0), out.strip()


def ensure_branch(branch: str, *, repo_root: Path = Path(".")) -> None:
    ok, out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    if not ok:
        raise RuntimeError(out)
    cur = out.strip()
    if cur != branch:
        ok, out = _run(["git", "checkout", branch], cwd=repo_root)
        if not ok:
            raise RuntimeError(out)


def fetch_and_merge_origin(branch: str, *, repo_root: Path = Path(".")) -> None:
    """Fetch origin and integrate origin/<branch> into current branch. Use before commit_and_push to deconflict with other runners. No-op if origin/branch does not exist yet."""
    ok, _ = _run(["git", "fetch", "origin"], cwd=repo_root)
    if not ok:
        raise RuntimeError("git fetch origin failed")
    ok, _ = _run(["git", "rev-parse", f"origin/{branch}"], cwd=repo_root)
    if not ok:
        return  # remote branch doesn't exist yet (e.g. first push)
    if ADOPT_PULL_STRATEGY == "rebase":
        ok, out = _run(["git", "rebase", f"origin/{branch}"], cwd=repo_root)
        if not ok:
            _run(["git", "rebase", "--abort"], cwd=repo_root)
            raise RuntimeError(f"git rebase origin/{branch} failed (aborted): {out}")
    else:
        ok, out = _run(["git", "merge", "--no-edit", f"origin/{branch}"], cwd=repo_root)
        if not ok:
            _run(["git", "merge", "--abort"], cwd=repo_root)
            raise RuntimeError(f"git merge origin/{branch} failed (aborted): {out}")


def apply_diff_to_repo(diff_text: str, *, repo_root: Path = Path(".")) -> None:
    env = os.environ.copy()
    p = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        cwd=str(repo_root), env=env, input=diff_text, capture_output=True, text=True,
    )
    out = (p.stdout or "") + ("\n" if p.stdout and p.stderr else "") + (p.stderr or "")
    if p.returncode == 0:
        return
    p2 = subprocess.run(
        ["git", "apply", "--3way", "--whitespace=nowarn", "-"],
        cwd=str(repo_root), env=env, input=diff_text, capture_output=True, text=True,
    )
    out2 = (p2.stdout or "") + ("\n" if p2.stdout and p2.stderr else "") + (p2.stderr or "")
    if p2.returncode != 0:
        raise RuntimeError(f"git apply failed:\n{out}\n\n3way failed:\n{out2}")


def commit_and_push(*, message: str, branch: str = "dev", repo_root: Path = Path(".")) -> None:
    ensure_branch(branch, repo_root=repo_root)
    ok, out = _run(["git", "status", "--porcelain"], cwd=repo_root)
    if not ok:
        raise RuntimeError(out)
    had_changes = bool(out.strip())
    if had_changes:
        ok, out = _run(["git", "stash", "push", "-m", "adopt-pre-pull"], cwd=repo_root)
        if not ok:
            raise RuntimeError(f"git stash failed: {out}")
    try:
        fetch_and_merge_origin(branch, repo_root=repo_root)
    finally:
        if had_changes:
            _run(["git", "stash", "pop"], cwd=repo_root)
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

    last_err = out
    for attempt in range(ADOPT_PUSH_RETRIES + 1):
        ok, out = _run(["git", "push", "origin", branch], cwd=repo_root)
        if ok:
            return
        last_err = out
        if attempt < ADOPT_PUSH_RETRIES:
            fetch_and_merge_origin(branch, repo_root=repo_root)
    raise RuntimeError(f"git push origin {branch} failed after {ADOPT_PUSH_RETRIES + 1} attempt(s): {last_err}")
