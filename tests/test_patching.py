"""Tests for agent_ext.self_improve.patching — diff sanitization, hunk repair, and apply."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from agent_ext.self_improve.patching import (
    _HUNK_HEADER_RE,
    _repair_hunk_headers,
    apply_unified_diff,
    sanitize_diff_for_apply,
)
from agent_ext.workbench.patch_models import (
    FilePatch,
    LineChange,
    PatchOutput,
    structured_to_unified_diff,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_git_repo(tmp: Path, files: dict[str, str] | None = None) -> Path:
    """Create a temp git repo with initial files and return its path."""
    subprocess.run(["git", "init", str(tmp)], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(tmp), "config", "user.email", "t@t"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(tmp), "config", "user.name", "t"], capture_output=True, check=True)
    if files:
        for rel_path, content in files.items():
            p = tmp / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp), "add", "-A"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(tmp), "commit", "-m", "init"], capture_output=True, check=True)
    return tmp


# ---------------------------------------------------------------------------
# 1. Hunk header regex
# ---------------------------------------------------------------------------


class TestHunkHeaderRegex:
    def test_matches_standard_headers(self):
        """Regex must match standard @@ -L,N +L,N @@ headers."""
        assert _HUNK_HEADER_RE.match("@@ -1,3 +1,3 @@")
        assert _HUNK_HEADER_RE.match("@@ -0,0 +1,5 @@")
        assert _HUNK_HEADER_RE.match("@@ -10,20 +15,25 @@")

    def test_matches_with_trailing_text(self):
        """Git often appends function context after @@."""
        assert _HUNK_HEADER_RE.match("@@ -1,3 +1,3 @@ def hello")

    def test_rejects_bare_hunk(self):
        """Bare @@ with no line numbers must not match."""
        assert not _HUNK_HEADER_RE.match("@@")
        assert not _HUNK_HEADER_RE.match("@@ malformed @@")


# ---------------------------------------------------------------------------
# 2. _repair_hunk_headers
# ---------------------------------------------------------------------------


class TestRepairHunkHeaders:
    def test_valid_headers_pass_through(self):
        """Already-valid hunk headers should not be altered."""
        diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1,3 +1,3 @@\n line1\n-old\n+new\n"
        repaired = _repair_hunk_headers(diff)
        assert "@@ -1,3 +1,3 @@" in repaired

    def test_bare_hunk_repaired(self):
        """Bare @@ gets rewritten with correct counts."""
        diff = "--- a/foo.py\n+++ b/foo.py\n@@\n context\n-old\n+new\n"
        repaired = _repair_hunk_headers(diff)
        assert "@@ -1,2 +1,2 @@" in repaired

    def test_new_file_bare_hunk_repaired(self):
        """Bare @@ after --- /dev/null gets @@ -0,0 +1,N @@."""
        diff = "--- /dev/null\n+++ b/new.py\n@@\n+line1\n+line2\n"
        repaired = _repair_hunk_headers(diff)
        assert "@@ -0,0 +1,2 @@" in repaired


# ---------------------------------------------------------------------------
# 3. sanitize_diff_for_apply
# ---------------------------------------------------------------------------


class TestSanitizeDiff:
    def test_well_formed_diff_unchanged(self):
        diff = '--- a/foo.py\n+++ b/foo.py\n@@ -1,3 +1,3 @@\n def hello():\n-    return "old"\n+    return "new"\n'
        sanitized = sanitize_diff_for_apply(diff)
        assert "--- a/foo.py" in sanitized
        assert "+++ b/foo.py" in sanitized
        assert "@@ -1,3 +1,3 @@" in sanitized

    def test_markdown_wrapped_diff(self):
        md = (
            "Here is the change:\n"
            "```diff\n"
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def f():\n"
            "-    pass\n"
            "+    return 1\n"
            "```\n"
            "That's it!\n"
        )
        sanitized = sanitize_diff_for_apply(md)
        assert "--- a/foo.py" in sanitized
        assert "+    return 1" in sanitized

    def test_new_file_diff_preserved(self):
        diff = (
            "diff --git a/new.py b/new.py\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/new.py\n"
            "@@ -0,0 +1,3 @@\n"
            "+def new_function():\n"
            "+    return True\n"
            "+\n"
        )
        sanitized = sanitize_diff_for_apply(diff)
        assert "--- /dev/null" in sanitized
        assert "@@ -0,0 +1,3 @@" in sanitized

    def test_empty_input_returns_empty(self):
        assert sanitize_diff_for_apply("") == ""
        assert sanitize_diff_for_apply("  \n  ") == ""

    def test_empty_lines_dont_extend_diff(self):
        """Blank lines after the diff block should not be captured as diff content."""
        text = (
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def f():\n"
            "-    pass\n"
            "+    return 1\n"
            "\n"
            "This is NOT part of the diff.\n"
            "Neither is this.\n"
        )
        sanitized = sanitize_diff_for_apply(text)
        assert "NOT part of the diff" not in sanitized
        assert "Neither is this" not in sanitized


# ---------------------------------------------------------------------------
# 4. structured_to_unified_diff
# ---------------------------------------------------------------------------


class TestStructuredToUnifiedDiff:
    def test_basic_edit(self):
        patch = PatchOutput(
            files=[
                FilePatch(
                    path="src/foo.py",
                    is_new_file=False,
                    lines=[
                        LineChange(kind="context", content="def hello():"),
                        LineChange(kind="remove", content='    return "old"'),
                        LineChange(kind="add", content='    return "new"'),
                    ],
                )
            ]
        )
        diff = structured_to_unified_diff(patch)
        assert "diff --git a/src/foo.py b/src/foo.py" in diff
        assert "--- a/src/foo.py" in diff
        assert "+++ b/src/foo.py" in diff
        assert "@@ -1,2 +1,2 @@" in diff
        assert '-    return "old"' in diff
        assert '+    return "new"' in diff

    def test_new_file(self):
        patch = PatchOutput(
            files=[
                FilePatch(
                    path="src/new.py",
                    is_new_file=True,
                    lines=[
                        LineChange(kind="add", content="# new module"),
                        LineChange(kind="add", content="def fn(): pass"),
                    ],
                )
            ]
        )
        diff = structured_to_unified_diff(patch)
        assert "diff --git a/src/new.py b/src/new.py" in diff
        assert "new file mode 100644" in diff
        assert "--- /dev/null" in diff
        assert "+++ b/src/new.py" in diff
        assert "@@ -0,0 +1,2 @@" in diff

    def test_multi_file(self):
        patch = PatchOutput(
            files=[
                FilePatch(
                    path="a.py",
                    is_new_file=False,
                    lines=[
                        LineChange(kind="context", content="x = 1"),
                        LineChange(kind="remove", content="y = 2"),
                        LineChange(kind="add", content="y = 3"),
                    ],
                ),
                FilePatch(
                    path="b.py",
                    is_new_file=True,
                    lines=[
                        LineChange(kind="add", content="z = 42"),
                    ],
                ),
            ]
        )
        diff = structured_to_unified_diff(patch)
        assert "diff --git a/a.py b/a.py" in diff
        assert "diff --git a/b.py b/b.py" in diff
        assert diff.count("diff --git") == 2

    def test_empty_patch(self):
        patch = PatchOutput(files=[])
        assert structured_to_unified_diff(patch) == ""


# ---------------------------------------------------------------------------
# 5. End-to-end: structured → unified → git apply
# ---------------------------------------------------------------------------


class TestApplyStructuredDiff:
    def test_edit_existing_file(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _make_git_repo(Path(td), {"src/foo.py": 'def hello():\n    return "old"\n'})
            patch = PatchOutput(
                files=[
                    FilePatch(
                        path="src/foo.py",
                        is_new_file=False,
                        lines=[
                            LineChange(kind="context", content="def hello():"),
                            LineChange(kind="remove", content='    return "old"'),
                            LineChange(kind="add", content='    return "new"'),
                        ],
                    ),
                ]
            )
            diff = structured_to_unified_diff(patch)
            ok, err = apply_unified_diff(diff, repo_root=repo)
            assert ok, f"git apply failed: {err}"
            content = (repo / "src" / "foo.py").read_text()
            assert 'return "new"' in content

    def test_create_new_file(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _make_git_repo(Path(td), {"src/existing.py": "x = 1\n"})
            patch = PatchOutput(
                files=[
                    FilePatch(
                        path="src/brand_new.py",
                        is_new_file=True,
                        lines=[
                            LineChange(kind="add", content="def new_fn():"),
                            LineChange(kind="add", content="    return 42"),
                        ],
                    ),
                ]
            )
            diff = structured_to_unified_diff(patch)
            ok, err = apply_unified_diff(diff, repo_root=repo)
            assert ok, f"git apply failed: {err}"
            content = (repo / "src" / "brand_new.py").read_text()
            assert "def new_fn():" in content
            assert "return 42" in content

    def test_multi_file_edit_and_create(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _make_git_repo(
                Path(td),
                {
                    "src/a.py": "x = 1\ny = 2\n",
                },
            )
            patch = PatchOutput(
                files=[
                    FilePatch(
                        path="src/a.py",
                        is_new_file=False,
                        lines=[
                            LineChange(kind="context", content="x = 1"),
                            LineChange(kind="remove", content="y = 2"),
                            LineChange(kind="add", content="y = 3"),
                        ],
                    ),
                    FilePatch(
                        path="src/b.py",
                        is_new_file=True,
                        lines=[
                            LineChange(kind="add", content="z = 42"),
                        ],
                    ),
                ]
            )
            diff = structured_to_unified_diff(patch)
            ok, err = apply_unified_diff(diff, repo_root=repo)
            assert ok, f"git apply failed: {err}"
            assert "y = 3" in (repo / "src" / "a.py").read_text()
            assert "z = 42" in (repo / "src" / "b.py").read_text()
