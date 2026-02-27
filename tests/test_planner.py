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
