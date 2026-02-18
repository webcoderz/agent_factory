from __future__ import annotations

import re
import subprocess
from pathlib import Path
import sys


def sanitize_diff_for_apply(diff_text: str) -> str:
    """
    Extract a single valid unified diff from LLM output (may contain markdown, commentary, trailing text).
    - Strips markdown code fences (```diff, ```patch, ```).
    - Keeps only lines that look like a unified diff (---/+++, diff --git, @@ hunks, context).
    - Normalizes line endings to LF so git apply doesn't see corrupt patch at line N.
    """
    if not diff_text or not diff_text.strip():
        return ""
    raw = diff_text.strip()
    # Strip markdown code block if present
    for marker in ("```diff", "```patch", "```"):
        if raw.startswith(marker):
            raw = raw[len(marker) :].lstrip("\r\n")
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")].rstrip("\r\n")
    # Normalize line endings to LF
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")
    # Find first line that starts a unified diff (--- or diff --git)
    start = None
    for i, line in enumerate(lines):
        if line.startswith("--- ") or line.startswith("diff --git "):
            start = i
            break
    if start is None:
        return raw
    # End at last line that is part of a valid unified diff; stop at first non-diff line to avoid "corrupt patch"
    def is_diff_line(ln: str) -> bool:
        if ln.startswith("--- ") or ln.startswith("+++ ") or ln.startswith("diff --git "):
            return True
        if ln.startswith("@@ ") and "@@" in ln[3:]:
            return True
        if ln == "":
            return True
        if len(ln) >= 1 and ln[0] == " ":  # context line
            return True
        if len(ln) >= 1 and ln[0] == "+" and not ln.startswith("+++ "):  # added line
            return True
        if len(ln) >= 1 and ln[0] == "-" and not ln.startswith("--- "):  # removed line
            return True
        return False

    end = start
    for i in range(start, len(lines)):
        if is_diff_line(lines[i]):
            end = i + 1
        else:
            break
    return "\n".join(lines[start:end]) + "\n" if end > start else ""


def apply_unified_diff(diff_text: str, repo_root: Path = Path(".")) -> tuple[bool, str]:
    """
    Applies a unified diff using `git apply` if available.
    Sanitizes LLM output (markdown, trailing text, line endings) before applying.
    """
    cleaned = sanitize_diff_for_apply(diff_text)
    if not cleaned.strip():
        return False, "sanitize_diff: no unified diff found in output (LLM must output raw diff: ---/+++ headers, @@ hunks, no markdown)"
    if "@@" not in cleaned:
        return False, "sanitize_diff: no valid hunks (unified diff must contain @@ hunk headers; LLM may have returned prose instead of a diff)"
    p = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        input=cleaned,
        text=True,
        cwd=str(repo_root),
        capture_output=True,
    )
    ok = p.returncode == 0
    err = (p.stdout + "\n" + p.stderr).strip()
    if not ok and "No valid patches" in err:
        err = "LLM did not produce a valid unified diff (git apply: no valid patches). Output must be raw diff only: diff --git or ---/+++, then @@ hunks with +/− lines. No markdown or commentary."
    return ok, err
