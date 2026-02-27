from __future__ import annotations

import re
import subprocess
from pathlib import Path
import sys


def _extract_diff_from_lines(lines: list[str]) -> str:
    """From a list of lines, find a contiguous unified diff and return it (with trailing newline)."""
    start = None
    for i, line in enumerate(lines):
        if line.startswith("--- ") or line.startswith("diff --git "):
            start = i
            break
    if start is None:
        return ""

    def is_diff_line(ln: str) -> bool:
        if ln.startswith("--- ") or ln.startswith("+++ ") or ln.startswith("diff --git "):
            return True
        # Valid: @@ -1,3 +1,4 @@  ; LLM sometimes outputs bare @@ (we repair later)
        if ln.startswith("@@"):
            return True
        if len(ln) >= 1 and ln[0] == " ":  # context line (must have leading space)
            return True
        if len(ln) >= 1 and ln[0] == "+" and not ln.startswith("+++ "):  # added line
            return True
        if len(ln) >= 1 and ln[0] == "-" and not ln.startswith("--- "):  # removed line
            return True
        # Git diff header lines (between "diff --git" and "---"/"+++")
        if ln.startswith("index ") or ln.startswith("new file mode ") or ln.startswith("old mode ") or ln.startswith("deleted file mode "):
            return True
        # Empty lines are NOT valid diff lines by themselves;
        # context lines in a diff have a leading space character.
        return False

    end = start
    for i in range(start, len(lines)):
        if is_diff_line(lines[i]):
            end = i + 1
        else:
            break
    return "\n".join(lines[start:end]) + "\n" if end > start else ""


# Valid hunk header: @@ -L1,N1 +L2,N2 @@ (optional trailing text)
_HUNK_HEADER_RE = re.compile(r"^@@ -\d+,\d+ \+\d+,\d+ @@")


def _repair_hunk_headers(diff: str) -> str:
    """
    Repair malformed @@ hunk headers (e.g. LLM outputs bare @@ with no line numbers).
    Counts old/new lines in each hunk body and writes valid @@ -N1,C1 +N2,C2 @@.
    """
    if not diff or "@@" not in diff:
        return diff
    lines = diff.split("\n")
    out: list[str] = []
    i = 0
    in_new_file = False
    while i < len(lines):
        line = lines[i]
        if line.startswith("--- ") and "/dev/null" in line:
            in_new_file = True
            out.append(line)
            i += 1
            continue
        if line.startswith("--- ") or line.startswith("diff --git "):
            in_new_file = False
        if not line.startswith("@@"):
            out.append(line)
            i += 1
            continue
        # This line is a hunk header (maybe malformed)
        if _HUNK_HEADER_RE.match(line.strip()):
            out.append(line)
            i += 1
            continue
        # Malformed: collect hunk body and build valid header
        n_old = n_new = 0
        j = i + 1
        while j < len(lines) and not (lines[j].startswith("@@") or lines[j].startswith("diff --git") or lines[j].startswith("--- ")):
            ln = lines[j]
            if ln.startswith("-") and not ln.startswith("--- "):
                n_old += 1
            elif ln.startswith("+") and not ln.startswith("+++ "):
                n_new += 1
            elif ln.startswith(" ") and len(ln) >= 1:
                # Context line (leading space)
                n_old += 1
                n_new += 1
            j += 1
        if in_new_file:
            # New file: @@ -0,0 +1,N @@
            out.append(f"@@ -0,0 +1,{max(1, n_new)} @@")
        else:
            # Modified file: @@ -1,N_old +1,N_new @@ (single-hunk heuristic)
            out.append(f"@@ -1,{max(1, n_old)} +1,{max(1, n_new)} @@")
        i += 1
        # Append the hunk body (lines between this @@ and the next @@ or end)
        while i < j:
            out.append(lines[i])
            i += 1
    return "\n".join(out) + ("\n" if out else "")


def _normalize_path_in_line(line: str) -> str:
    """Strip leading slashes and normalize backslashes in path part so git apply accepts paths."""
    if line.startswith("diff --git "):
        rest = line[len("diff --git ") :].strip()
        parts = rest.split(None, 1)
        if len(parts) >= 2:
            a_path = parts[0].replace("\\", "/").lstrip("/")
            b_path = parts[1].replace("\\", "/").lstrip("/")
            a_path = a_path if a_path.startswith("a/") else "a/" + a_path.lstrip("a/")
            b_path = b_path if b_path.startswith("b/") else "b/" + b_path.lstrip("b/")
            return f"diff --git {a_path} {b_path}"
    if line.startswith("--- ") or line.startswith("+++ "):
        path_part = line[4:].strip().replace("\\", "/")
        if "/dev/null" not in path_part:
            path_part = path_part.lstrip("/")
        return line[:4] + path_part
    return line


def _normalize_diff_paths(diff: str) -> str:
    """Apply path normalization to header lines so Windows/absolute paths work."""
    lines = diff.split("\n")
    out = []
    for ln in lines:
        if ln.startswith("diff --git ") or ln.startswith("--- ") or ln.startswith("+++ "):
            out.append(_normalize_path_in_line(ln))
        else:
            out.append(ln)
    return "\n".join(out) + ("\n" if out else "")


def _extract_diff_anywhere(text: str) -> str:
    """Find a block that looks like a unified diff (has ---/+++ and @@) anywhere in text."""
    lines = text.split("\n")
    best = ""
    for i, line in enumerate(lines):
        if not (line.startswith("--- ") or line.startswith("diff --git ")):
            continue
        out = _extract_diff_from_lines(lines[i:])
        if out and "@@" in out and len(out) > len(best):
            best = out
    return best


def sanitize_diff_for_apply(diff_text: str) -> str:
    """
    Extract a single valid unified diff from LLM output (may contain markdown, commentary, trailing text).
    - Strips markdown code fences (```diff, ```patch, ```); also looks inside response for fenced blocks.
    - Keeps only lines that look like a unified diff (---/+++, diff --git, @@ hunks, context).
    - Normalizes line endings to LF and path separators so git apply accepts the patch.
    """
    if not diff_text or not diff_text.strip():
        return ""
    raw = diff_text.strip()
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    for marker in ("```diff", "```patch", "```"):
        if raw.startswith(marker):
            raw = raw[len(marker) :].lstrip("\n")
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")].rstrip("\n")
    lines = raw.split("\n")
    out = _extract_diff_from_lines(lines)
    if not out and ("--- " in raw or "diff --git " in raw) and "@@" in raw:
        out = _extract_diff_anywhere(raw)
    if out:
        out = _repair_hunk_headers(out)
        out = _normalize_diff_paths(out)
        return out
    parts = re.split(r"```(?:\w*)\s*\n?", raw)
    for block in parts:
        block = block.strip()
        if "@@" not in block or ("--- " not in block and "+++ " not in block and "diff --git " not in block):
            continue
        out = _extract_diff_from_lines(block.split("\n"))
        if not out:
            out = _extract_diff_anywhere(block)
        if out and "@@" in out:
            out = _repair_hunk_headers(out)
            out = _normalize_diff_paths(out)
            return out
    return ""


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
