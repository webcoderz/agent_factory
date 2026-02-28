"""Tests for the overhauled backends system."""

from __future__ import annotations

import pytest

from agent_ext.backends import (
    DEFAULT_RULESET,
    PERMISSIVE_RULESET,
    READONLY_RULESET,
    PermissionChecker,
    StateBackend,
    apply_hashline_edit,
    create_ruleset,
    format_hashline_output,
    line_hash,
)


class TestStateBackend:
    def test_write_and_read(self):
        sb = StateBackend()
        sb.write_text("src/app.py", "print('hello')")
        assert sb.read_text("src/app.py") == "print('hello')"

    def test_read_missing_raises(self):
        sb = StateBackend()
        with pytest.raises(FileNotFoundError):
            sb.read_text("nonexistent.py")

    def test_list_files(self):
        sb = StateBackend()
        sb.write_text("src/a.py", "a")
        sb.write_text("src/b.py", "b")
        assert sb.list("/src") == ["a.py", "b.py"]

    def test_glob(self):
        sb = StateBackend()
        sb.write_text("src/a.py", "a")
        sb.write_text("src/b.txt", "b")
        result = sb.glob("**/*.py")
        assert any("a.py" in r for r in result)

    def test_edit(self):
        sb = StateBackend()
        sb.write_text("f.py", "x = 1\ny = 2")
        result = sb.edit("/f.py", "x = 1", "x = 99")
        assert result.error is None
        assert "x = 99" in sb.read_text("f.py")

    def test_edit_not_found(self):
        sb = StateBackend()
        sb.write_text("f.py", "hello")
        result = sb.edit("/f.py", "nonexistent", "replacement")
        assert result.error is not None

    def test_grep(self):
        sb = StateBackend()
        sb.write_text("a.py", "def hello():\n    pass")
        sb.write_text("b.py", "x = 1")
        matches = sb.grep_raw("hello")
        assert isinstance(matches, list)
        assert len(matches) == 1
        assert matches[0].path == "/a.py"

    def test_read_numbered(self):
        sb = StateBackend()
        sb.write_text("f.py", "line1\nline2\nline3")
        output = sb.read_numbered("/f.py")
        assert "1\tline1" in output
        assert "3\tline3" in output

    def test_path_traversal_blocked(self):
        sb = StateBackend()
        with pytest.raises(PermissionError):
            sb.write_text("../../etc/passwd", "hacked")


class TestPermissions:
    def test_readonly_allows_read(self):
        checker = PermissionChecker(READONLY_RULESET)
        assert checker.is_allowed("read", "/src/app.py")

    def test_readonly_blocks_write(self):
        checker = PermissionChecker(READONLY_RULESET)
        assert not checker.is_allowed("write", "/src/app.py")

    def test_permissive_allows_write(self):
        checker = PermissionChecker(PERMISSIVE_RULESET)
        assert checker.is_allowed("write", "/src/app.py")

    def test_secrets_always_denied(self):
        for ruleset in [READONLY_RULESET, PERMISSIVE_RULESET, DEFAULT_RULESET]:
            checker = PermissionChecker(ruleset)
            assert not checker.is_allowed("read", "**/.env")

    def test_custom_ruleset(self):
        ruleset = create_ruleset(allow_read=True, allow_write=True, allow_execute=False)
        checker = PermissionChecker(ruleset)
        assert checker.is_allowed("read", "/f.py")
        assert checker.is_allowed("write", "/f.py")
        assert not checker.is_allowed("execute", "ls")

    def test_require_raises_on_deny(self):
        checker = PermissionChecker(READONLY_RULESET)
        with pytest.raises(PermissionError):
            checker.require("write", "/f.py")


class TestHashline:
    def test_line_hash_deterministic(self):
        h1 = line_hash("hello world")
        h2 = line_hash("hello world")
        assert h1 == h2
        assert len(h1) == 2

    def test_different_content_different_hash(self):
        h1 = line_hash("hello")
        h2 = line_hash("world")
        assert h1 != h2

    def test_format_output(self):
        content = "line one\nline two\nline three\n"
        output = format_hashline_output(content)
        assert "1:" in output
        assert "2:" in output
        assert "3:" in output
        assert "|line one" in output

    def test_apply_edit_success(self):
        content = "first\nsecond\nthird\n"
        h = line_hash("second")
        new_content, error = apply_hashline_edit(content, start_line=2, start_hash=h, new_content="replaced")
        assert error is None
        assert "replaced" in new_content
        assert "second" not in new_content

    def test_apply_edit_hash_mismatch(self):
        content = "first\nsecond\nthird\n"
        new_content, error = apply_hashline_edit(content, start_line=2, start_hash="xx", new_content="replaced")
        assert error is not None
        assert "mismatch" in error.lower()
        assert "second" in new_content  # unchanged

    def test_apply_edit_insert_after(self):
        content = "first\nsecond\nthird\n"
        h = line_hash("first")
        new_content, error = apply_hashline_edit(
            content, start_line=1, start_hash=h, new_content="inserted", insert_after=True
        )
        assert error is None
        lines = new_content.strip().split("\n")
        assert lines[0] == "first"
        assert lines[1] == "inserted"
        assert lines[2] == "second"
