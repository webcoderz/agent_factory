"""Tests for agent_ext.cog.scoring — Score properties and score_patch."""
from __future__ import annotations

from agent_ext.cog.scoring import Score, score_patch, touched_files_from_diff


class TestScore:
    def test_score_property_alias(self):
        sc = Score(total=42.0, reasons={"gates": 100.0})
        assert sc.score == 42.0
        assert sc.score == sc.total

    def test_ok_when_gates_pass(self):
        sc = Score(total=90.0, reasons={"gates": 100.0})
        assert sc.ok is True

    def test_not_ok_when_gates_fail(self):
        sc = Score(total=-50.0, reasons={"gates": -50.0})
        assert sc.ok is False

    def test_not_ok_when_gates_zero(self):
        sc = Score(total=0.0, reasons={"gates": 0.0})
        assert sc.ok is False


class TestScorePatch:
    def test_gates_pass_positive_score(self):
        sc = score_patch(gates_ok=True, diff_chars=100, files_touched=1, eval_delta=0.0)
        assert sc.score > 0
        assert sc.ok is True

    def test_gates_fail_negative_score(self):
        sc = score_patch(gates_ok=False, diff_chars=100, files_touched=1, eval_delta=0.0)
        assert sc.score < 0
        assert sc.ok is False

    def test_large_diff_penalized(self):
        small = score_patch(gates_ok=True, diff_chars=100, files_touched=1)
        large = score_patch(gates_ok=True, diff_chars=60000, files_touched=1)
        assert small.score > large.score

    def test_many_files_penalized(self):
        few = score_patch(gates_ok=True, diff_chars=100, files_touched=1)
        many = score_patch(gates_ok=True, diff_chars=100, files_touched=10)
        assert few.score > many.score


class TestTouchedFiles:
    def test_extracts_paths_from_diff_git(self):
        diff = (
            "diff --git a/foo.py b/foo.py\n"
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,1 +1,1 @@\n"
            "+x\n"
            "diff --git a/bar.py b/bar.py\n"
            "--- a/bar.py\n"
            "+++ b/bar.py\n"
            "@@ -1,1 +1,1 @@\n"
            "+y\n"
        )
        files = touched_files_from_diff(diff)
        assert files == ["bar.py", "foo.py"]

    def test_empty_diff(self):
        assert touched_files_from_diff("") == []
