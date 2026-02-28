"""Tests for agent_ext.workbench.worktrees — worktree create, diff, cleanup."""

from __future__ import annotations

import pytest

from agent_ext.workbench.worktrees import (
    _run,
    cleanup_worktree,
    create_worktree,
    worktree_diff,
)


def _ensure_main_repo_clean():
    """Check we're in a git repo (the workspace itself)."""
    ok, _ = _run(["git", "rev-parse", "--is-inside-work-tree"])
    return ok


@pytest.fixture(autouse=True)
def _skip_if_not_git():
    """Skip worktree tests if we're not inside a git repo."""
    if not _ensure_main_repo_clean():
        pytest.skip("Not inside a git repo — worktree tests require git")


class TestWorktreeCreateAndCleanup:
    def test_create_worktree(self):
        """Creating a worktree should produce a valid WorktreeHandle with an existing directory."""
        wt = create_worktree(run_id="test_create_001", agent_name="test_agent")
        try:
            assert wt.path.exists()
            assert wt.path.is_dir()
            assert wt.run_id == "test_create_001"
            assert wt.agent_name == "test_agent"
            # Verify it's actually a git worktree
            ok, out = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=wt.path)
            assert ok
        finally:
            cleanup_worktree(wt, prune_branch=True)

    def test_cleanup_removes_directory(self):
        """Cleanup should remove the worktree directory."""
        wt = create_worktree(run_id="test_cleanup_001", agent_name="test_agent")
        path = wt.path
        assert path.exists()
        cleanup_worktree(wt, prune_branch=True)
        assert not path.exists()


class TestWorktreeDiff:
    def test_diff_captures_edits(self):
        """Editing an existing file in the worktree should appear in the diff."""
        wt = create_worktree(run_id="test_diff_edit_001", agent_name="test_agent")
        try:
            # Find an existing python file to modify
            py_files = list(wt.path.rglob("*.py"))
            if not py_files:
                pytest.skip("No .py files in worktree")
            target = py_files[0]
            original = target.read_text(encoding="utf-8")
            target.write_text(original + "\n# test edit marker\n", encoding="utf-8")

            diff = worktree_diff(wt)
            assert "# test edit marker" in diff
            assert "+" in diff  # Should have added lines
        finally:
            cleanup_worktree(wt, prune_branch=True)

    def test_diff_captures_new_files(self):
        """New files created in the worktree should appear in the diff."""
        wt = create_worktree(run_id="test_diff_new_001", agent_name="test_agent")
        try:
            new_file = wt.path / "test_brand_new_file.py"
            new_file.write_text("# Brand new file\ndef hello():\n    return 42\n", encoding="utf-8")

            diff = worktree_diff(wt)
            assert "test_brand_new_file.py" in diff
            assert "+# Brand new file" in diff
            assert "+def hello():" in diff
            assert "new file" in diff  # git diff should mark it as new
        finally:
            cleanup_worktree(wt, prune_branch=True)

    def test_diff_empty_when_no_changes(self):
        """No changes should produce an empty diff."""
        wt = create_worktree(run_id="test_diff_empty_001", agent_name="test_agent")
        try:
            diff = worktree_diff(wt)
            assert diff.strip() == ""
        finally:
            cleanup_worktree(wt, prune_branch=True)

    def test_diff_captures_both_edits_and_new_files(self):
        """Mixed changes (edits + new files) should all appear in the diff."""
        wt = create_worktree(run_id="test_diff_mixed_001", agent_name="test_agent")
        try:
            # Edit existing
            py_files = list(wt.path.rglob("*.py"))
            if not py_files:
                pytest.skip("No .py files in worktree")
            target = py_files[0]
            original = target.read_text(encoding="utf-8")
            target.write_text(original + "\n# mixed edit marker\n", encoding="utf-8")

            # Create new
            new_file = wt.path / "test_mixed_new.py"
            new_file.write_text("# mixed new file\n", encoding="utf-8")

            diff = worktree_diff(wt)
            assert "# mixed edit marker" in diff
            assert "test_mixed_new.py" in diff
            assert "+# mixed new file" in diff
        finally:
            cleanup_worktree(wt, prune_branch=True)
