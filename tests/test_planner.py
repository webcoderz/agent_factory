"""Tests for agent_ext.workbench.planner — TaskQueue."""
from __future__ import annotations

import asyncio

import pytest

from agent_ext.workbench.planner import Task, TaskQueue


class TestTaskQueue:
    def test_add_and_list(self):
        q = TaskQueue()
        q.add("search", "Find modules", "query")
        q.add("implement", "Create patch", "goal")
        tasks = q.list()
        assert len(tasks) == 2
        assert tasks[0].kind == "search"
        assert tasks[1].kind == "implement"

    def test_ids_are_sequential(self):
        q = TaskQueue()
        t1 = q.add("search", "A", "q1")
        t2 = q.add("search", "B", "q2")
        assert t1.id == "t0001"
        assert t2.id == "t0002"

    def test_next_pending(self):
        q = TaskQueue()
        q.add("search", "A", "q1")
        t = q.next_pending()
        assert t is not None
        assert t.status == "pending"

    def test_next_pending_empty(self):
        q = TaskQueue()
        assert q.next_pending() is None

    @pytest.mark.asyncio
    async def test_claim_next_pending(self):
        q = TaskQueue()
        q.add("search", "A", "q1")
        t = await q.claim_next_pending()
        assert t is not None
        assert t.status == "in_progress"
        # Second claim returns None (no more pending)
        t2 = await q.claim_next_pending()
        assert t2 is None

    @pytest.mark.asyncio
    async def test_cancel_by_id(self):
        q = TaskQueue()
        t = q.add("search", "A", "q1")
        result = await q.cancel_by_id(t.id)
        assert result is True
        assert t.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_non_pending(self):
        q = TaskQueue()
        t = q.add("search", "A", "q1")
        await q.claim_next_pending()  # now in_progress
        result = await q.cancel_by_id(t.id)
        assert result is False  # can't cancel in_progress

    @pytest.mark.asyncio
    async def test_cancel_unknown_id(self):
        q = TaskQueue()
        result = await q.cancel_by_id("t9999")
        assert result is None

    def test_get_by_id(self):
        q = TaskQueue()
        t = q.add("search", "A", "q1")
        found = q.get_by_id("t0001")
        assert found is t
        assert q.get_by_id("0001") is t  # numeric shorthand
        assert q.get_by_id("t9999") is None

    def test_normalize_id(self):
        q = TaskQueue()
        assert q.normalize_id("0001") == "t0001"
        assert q.normalize_id("t0001") == "t0001"

    @pytest.mark.asyncio
    async def test_retry_failed_task(self):
        q = TaskQueue()
        t = q.add("implement", "Create patch", "goal")
        await q.claim_next_pending()  # in_progress
        t.status = "failed"
        result = await q.retry_by_id(t.id)
        assert result is True
        assert t.status == "pending"
        assert t.started_at is None
        assert t.finished_at is None

    @pytest.mark.asyncio
    async def test_retry_non_failed_task(self):
        q = TaskQueue()
        t = q.add("search", "A", "q1")
        result = await q.retry_by_id(t.id)
        assert result is False  # pending, not retryable

    @pytest.mark.asyncio
    async def test_retry_all_failed(self):
        q = TaskQueue()
        t1 = q.add("search", "A", "q1")
        t2 = q.add("implement", "B", "q2")
        t1.status = "failed"
        t2.status = "failed"
        count = await q.retry_all_failed()
        assert count == 2
        assert t1.status == "pending"
        assert t2.status == "pending"

    def test_elapsed_time(self):
        import time
        q = TaskQueue()
        t = q.add("search", "A", "q1")
        assert t.elapsed_s is None  # not started
        t.started_at = time.time() - 5.0
        assert t.elapsed_s is not None
        assert t.elapsed_s >= 4.9  # at least ~5s
        t.finished_at = t.started_at + 5.0
        assert abs(t.elapsed_s - 5.0) < 0.1
