from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def apply_unified_diff(diff_text: str, repo_root: Path = Path(".")) -> tuple[bool, str]:
    """
    Applies a unified diff using `git apply` if available.
    Keeps it simple + repo-contained.
    """
    p = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        input=diff_text,
        text=True,
        cwd=str(repo_root),
        capture_output=True,
    )
    ok = p.returncode == 0
    return ok, (p.stdout + "\n" + p.stderr).strip()
