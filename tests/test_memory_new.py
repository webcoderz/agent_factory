"""Tests for the overhauled memory system."""
from __future__ import annotations

import pytest

from agent_ext.memory import (
    SlidingWindowMemory, approximate_token_count,
    find_safe_cutoff, find_token_based_cutoff, is_safe_cutoff_point,
)


class TestSlidingWindowMemory:
    def test_message_count_mode(self):
        mem = SlidingWindowMemory(max_messages=3)
        result = mem.shape_messages(["a", "b", "c", "d", "e"])
        assert len(result) == 3
        assert result == ["c", "d", "e"]

    def test_under_limit_unchanged(self):
        mem = SlidingWindowMemory(max_messages=10)
        msgs = ["a", "b", "c"]
        result = mem.shape_messages(msgs)
        assert result == msgs

    def test_token_mode(self):
        counter = lambda msgs: sum(len(str(m)) for m in msgs)
        mem = SlidingWindowMemory(max_tokens=5, token_counter=counter)
        result = mem.shape_messages(["aaa", "bb", "c"])  # 3+2+1 = 6 > 5
        assert len(result) < 3

    def test_trigger_messages(self):
        mem = SlidingWindowMemory(max_messages=3, trigger_messages=5)
        # Under trigger: no trim
        result = mem.shape_messages(["a", "b", "c", "d"])
        assert len(result) == 4
        # At trigger: trim
        result2 = mem.shape_messages(["a", "b", "c", "d", "e"])
        assert len(result2) == 3

    def test_checkpoint_is_noop(self):
        mem = SlidingWindowMemory(max_messages=10)
        mem.checkpoint(["a"], outcome="done")  # should not raise


class TestSafeCutoff:
    def test_preserves_messages_when_under(self):
        assert find_safe_cutoff(["a", "b", "c"], messages_to_keep=5) == 0

    def test_trims_when_over(self):
        msgs = list(range(10))
        cutoff = find_safe_cutoff(msgs, messages_to_keep=3)
        assert cutoff >= 7

    def test_keep_zero_returns_full_length(self):
        assert find_safe_cutoff(["a", "b", "c"], messages_to_keep=0) == 3

    def test_safe_cutoff_point_at_start(self):
        assert is_safe_cutoff_point(["a", "b"], 0) is True

    def test_safe_cutoff_point_at_end(self):
        assert is_safe_cutoff_point(["a", "b"], 5) is True


class TestTokenBasedCutoff:
    def test_under_budget_returns_zero(self):
        counter = lambda msgs: len(msgs)
        assert find_token_based_cutoff(["a", "b", "c"], target_tokens=5, token_counter=counter) == 0

    def test_over_budget_trims(self):
        counter = lambda msgs: len(msgs) * 100
        cutoff = find_token_based_cutoff(list(range(10)), target_tokens=300, token_counter=counter)
        assert cutoff >= 7

    def test_empty_messages(self):
        counter = lambda msgs: 0
        assert find_token_based_cutoff([], target_tokens=100, token_counter=counter) == 0


class TestApproximateTokenCount:
    def test_basic(self):
        count = approximate_token_count(["hello world", "test"])
        assert count > 0
        assert isinstance(count, int)
