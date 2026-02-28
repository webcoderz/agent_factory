from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Sequence

from agent_ext.evidence.models import Evidence, Provenance
from agent_ext.research.ledger import ResearchLedger
from agent_ext.research.models import ResearchTask
from agent_ext.run_context import RunContext

TaskHandler = Callable[[RunContext, ResearchTask, ResearchLedger], Awaitable[Sequence[Evidence]]]


class ResearchExecutor:
    """
    Executes ResearchTask via handlers (kind-based).
    """

    def __init__(self, handlers: dict[str, TaskHandler]):
        self.handlers = handlers

    async def run_task(self, ctx: RunContext, task: ResearchTask, ledger: ResearchLedger) -> list[Evidence]:
        if task.kind not in self.handlers:
            # Return a diagnostic Evidence instead of hard failing
            return [
                Evidence(
                    kind="note",
                    content={"error": f"No handler for task kind '{task.kind}'", "task": task.model_dump()},
                    citations=[],
                    provenance=Provenance(produced_by="research_executor", artifact_ids=[]),
                    confidence=0.3,
                    tags=["research", "missing_handler"],
                )
            ]

        task.status = "running"
        task.attempts += 1
        ledger.add_event("task_start", {"task_id": task.id, "kind": task.kind, "goal": task.goal})

        t0 = time.time()
        try:
            ev = await self.handlers[task.kind](ctx, task, ledger)
            task.status = "done"
            ledger.add_event("task_done", {"task_id": task.id, "seconds": time.time() - t0, "evidence_count": len(ev)})
            return list(ev)
        except Exception as e:
            task.error = str(e)
            task.status = "failed"
            ledger.add_event("task_failed", {"task_id": task.id, "error": str(e)})
            raise

    def should_retry(self, task: ResearchTask) -> bool:
        return task.status == "failed" and task.attempts < task.max_attempts
