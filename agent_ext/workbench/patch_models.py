"""
Structured patch output for the LLM: Pydantic models that the model returns
so we can convert to a valid unified diff ourselves (no raw diff parsing).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LineChange(BaseModel):
    """One line in a file patch: unchanged context, added, or removed."""

    kind: Literal["context", "add", "remove"] = Field(
        description="context = unchanged line, add = new line, remove = deleted line"
    )
    content: str = Field(description="The line content without any + - or space prefix")


class FilePatch(BaseModel):
    """Edits to a single file: path (relative to repo) and list of line changes."""

    path: str = Field(description="Relative path from repo root, e.g. agent_ext/foo.py")
    is_new_file: bool = Field(default=False, description="True if this file is being created")
    lines: list[LineChange] = Field(default_factory=list, description="Ordered list of line changes (context/add/remove)")


class PatchOutput(BaseModel):
    """Structured patch: list of file edits. Convert to unified diff with structured_to_unified_diff()."""

    files: list[FilePatch] = Field(default_factory=list, description="List of file patches to apply")


def structured_to_unified_diff(patch: PatchOutput) -> str:
    """
    Convert structured PatchOutput to a valid unified diff string for git apply.
    We control the format so it is always valid; no LLM diff parsing needed.
    """
    out: list[str] = []
    for fp in patch.files:
        path = fp.path.replace("\\", "/").lstrip("/")
        if fp.is_new_file:
            out.append(f"diff --git a/{path} b/{path}")
            out.append("new file mode 100644")
            out.append("--- /dev/null")
            out.append(f"+++ b/{path}")
        else:
            out.append(f"diff --git a/{path} b/{path}")
            out.append(f"--- a/{path}")
            out.append(f"+++ b/{path}")
        # Single hunk: compute line counts
        old_count = sum(1 for lc in fp.lines if lc.kind in ("context", "remove"))
        new_count = sum(1 for lc in fp.lines if lc.kind in ("context", "add"))
        if fp.is_new_file:
            out.append(f"@@ -0,0 +1,{max(1, new_count)} @@")
        else:
            out.append(f"@@ -1,{max(1, old_count)} +1,{max(1, new_count)} @@")
        for lc in fp.lines:
            if lc.kind == "context":
                prefix = " "
            elif lc.kind == "add":
                prefix = "+"
            else:
                prefix = "-"
            line = (lc.content or "").rstrip("\n")
            out.append(prefix + line)
    if not out:
        return ""
    return "\n".join(out) + "\n"
