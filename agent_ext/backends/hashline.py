"""Hashline: content-hash-tagged line editing for AI agents.

Each line is tagged with a 2-character content hash.  Models reference
lines by ``number:hash`` pairs instead of reproducing exact text,
eliminating whitespace-matching errors and reducing output tokens.

Format::

    1:a3|function hello() {
    2:f1|  return "world";
    3:0e|}
"""

from __future__ import annotations

import hashlib


def line_hash(content: str) -> str:
    """Generate a 2-char hex content hash for a line."""
    return hashlib.md5(content.encode("utf-8")).hexdigest()[:2]


def _split_lines(content: str) -> tuple[list[str], bool]:
    has_trailing_nl = content.endswith("\n")
    lines = content.split("\n")
    if has_trailing_nl and lines and lines[-1] == "":
        lines = lines[:-1]
    return lines, has_trailing_nl


def format_hashline_output(content: str, offset: int = 0, limit: int = 2000) -> str:
    """Format file content with hashline tags.

    Each line becomes ``{line_num}:{hash}|{content}``.
    """
    lines, _ = _split_lines(content)
    total = len(lines)
    if total == 0:
        return "(empty file)"
    if offset >= total:
        return f"Error: Offset {offset} exceeds file length ({total} lines)"
    end = min(offset + limit, total)
    parts = [f"{i + 1}:{line_hash(lines[i])}|{lines[i]}" for i in range(offset, end)]
    result = "\n".join(parts)
    if end < total:
        result += f"\n\n... ({total - end} more lines)"
    return result


def apply_hashline_edit(
    content: str,
    start_line: int,
    start_hash: str,
    new_content: str,
    end_line: int | None = None,
    end_hash: str | None = None,
    insert_after: bool = False,
) -> tuple[str, str | None]:
    """Apply a hashline edit.  Validates hashes match before applying.

    Returns ``(new_file_content, error)``.  *error* is ``None`` on success.
    """
    lines, has_trailing_nl = _split_lines(content)
    total = len(lines)

    if start_line < 1 or start_line > total:
        return content, f"Line {start_line} out of range (file has {total} lines)"

    actual_sh = line_hash(lines[start_line - 1])
    if actual_sh != start_hash:
        return content, (
            f"Hash mismatch at line {start_line}: expected '{start_hash}', "
            f"got '{actual_sh}'. File may have changed — re-read it first."
        )

    effective_end = start_line
    if end_line is not None:
        if end_line < start_line:
            return content, f"end_line ({end_line}) must be >= start_line ({start_line})"
        if end_line > total:
            return content, f"End line {end_line} out of range (file has {total} lines)"
        if end_hash is not None:
            actual_eh = line_hash(lines[end_line - 1])
            if actual_eh != end_hash:
                return content, (
                    f"Hash mismatch at line {end_line}: expected '{end_hash}', "
                    f"got '{actual_eh}'. File may have changed — re-read it first."
                )
        effective_end = end_line

    new_lines = new_content.split("\n") if new_content else []

    if insert_after:
        result_lines = lines[:start_line] + new_lines + lines[start_line:]
    else:
        result_lines = lines[: start_line - 1] + new_lines + lines[effective_end:]

    result = "\n".join(result_lines)
    if has_trailing_nl:
        result += "\n"
    return result, None
