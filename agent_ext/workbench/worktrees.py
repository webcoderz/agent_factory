from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

WORKTREES_ROOT = Path(".agent_state/worktrees")


@dataclass(frozen=True)
class WorktreeHandle:
    run_id: str
    agent_name: str
    branch: str
    path: Path


def _run(cmd: list[str], *, cwd: Path | None = None) -> tuple[bool, str]:
    env = os.environ.copy()  # includes HTTP_PROXY/HTTPS_PROXY/etc.
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, capture_output=True, text=True)
    ok = p.returncode == 0
    out = (p.stdout or "") + ("\n" if p.stdout and p.stderr else "") + (p.stderr or "")
    return ok, out.strip()


def ensure_git_repo() -> None:
    ok, _ = _run(["git", "rev-parse", "--is-inside-work-tree"])
    if not ok:
        raise RuntimeError("Not inside a git repo. Worktrees require git.")


def create_worktree(
    *,
    run_id: str,
    agent_name: str,
    base_ref: str = "HEAD",
    branch_prefix: str = "auto",
) -> WorktreeHandle:
    """
    Creates a new branch + worktree at:
      .agent_state/worktrees/<run_id>/<agent_name>/
    """
    ensure_git_repo()

    wt_path = WORKTREES_ROOT / run_id / agent_name
    wt_path.parent.mkdir(parents=True, exist_ok=True)

    # Unique branch name
    safe_agent = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in agent_name)
    branch = f"{branch_prefix}/{run_id}/{safe_agent}"

    # Create branch (fails if exists; that’s fine—use a unique run_id)
    ok, out = _run(["git", "branch", branch, base_ref])
    if not ok and "already exists" not in out.lower():
        raise RuntimeError(f"git branch failed: {out}")

    # Add worktree
    # NOTE: --force is dangerous; avoid. If directory exists, wipe it and re-add.
    if wt_path.exists():
        shutil.rmtree(wt_path)

    ok, out = _run(["git", "worktree", "add", str(wt_path), branch])
    if not ok:
        raise RuntimeError(f"git worktree add failed: {out}")

    return WorktreeHandle(run_id=run_id, agent_name=agent_name, branch=branch, path=wt_path)


def worktree_diff(wt: WorktreeHandle) -> str:
    """
    Unified diff of ALL changes in the worktree (edits + new files).
    Stages everything first so new (untracked) files are captured.
    """
    # Stage all changes (including new/untracked files)
    ok, out = _run(["git", "add", "-A"], cwd=wt.path)
    if not ok:
        raise RuntimeError(f"git add -A failed: {out}")
    # Diff staged changes against HEAD to capture everything
    ok, out = _run(["git", "diff", "--cached", "HEAD"], cwd=wt.path)
    if not ok:
        raise RuntimeError(out)
    return out


def worktree_status(wt: WorktreeHandle) -> str:
    ok, out = _run(["git", "status", "--porcelain"], cwd=wt.path)
    if not ok:
        raise RuntimeError(out)
    return out


def cleanup_worktree(wt: WorktreeHandle, *, prune_branch: bool = False) -> None:
    """
    Removes worktree directory and optionally deletes its branch.
    """
    ensure_git_repo()
    # Remove worktree
    ok, out = _run(["git", "worktree", "remove", "--force", str(wt.path)])
    if not ok:
        raise RuntimeError(f"git worktree remove failed: {out}")

    # Optionally delete branch
    if prune_branch:
        ok, out = _run(["git", "branch", "-D", wt.branch])
        if not ok:
            raise RuntimeError(f"git branch -D failed: {out}")
