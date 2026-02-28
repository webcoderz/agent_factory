from __future__ import annotations

import hashlib
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from agent_ext.evidence.models import Evidence
from agent_ext.research.models import ResearchPlan, ResearchTask
from agent_ext.run_context import RunContext


def _hash_jsonable(obj: Any) -> str:
    s = repr(obj).encode("utf-8", errors="ignore")
    return hashlib.sha256(s).hexdigest()


@dataclass
class ResearchLedger:
    """
    In-memory ledger for a single research run.

    Persist what matters through ctx.artifacts:
    - plan
    - step events
    - evidence batches
    - final report
    """

    plan: ResearchPlan
    tasks: dict[str, ResearchTask] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.tasks = {t.id: t for t in self.plan.tasks}

    def add_event(self, kind: str, payload: dict[str, Any]) -> None:
        self.events.append({"t": time.time(), "kind": kind, "payload": payload})

    def add_evidence(self, ev: Sequence[Evidence]) -> list[str]:
        before = len(self.evidence)
        self.evidence.extend(list(ev))
        after = len(self.evidence)
        # return synthetic ids as stable hashes for now
        ids = [self.evidence_id(e) for e in self.evidence[before:after]]
        return ids

    def evidence_id(self, e: Evidence) -> str:
        # stable id for this run, based on content/provenance/citations
        return _hash_jsonable(
            {
                "kind": e.kind,
                "content": e.content,
                "prov": e.provenance.model_dump(),
                "cits": [c.model_dump() for c in e.citations],
                "tags": e.tags,
            }
        )

    def get_task(self, task_id: str) -> ResearchTask:
        return self.tasks[task_id]

    def list_tasks(self) -> list[ResearchTask]:
        return list(self.tasks.values())

    def pending_tasks(self) -> list[ResearchTask]:
        return [t for t in self.tasks.values() if t.status == "pending"]

    def runnable_tasks(self) -> list[ResearchTask]:
        runnable: list[ResearchTask] = []
        for t in self.tasks.values():
            if t.status != "pending":
                continue
            if all(self.tasks[d].status == "done" for d in t.depends_on):
                runnable.append(t)
        return sorted(runnable, key=lambda x: (x.priority, x.id))

    def store_snapshot(self, ctx: RunContext, *, label: str) -> str:
        payload = {
            "label": label,
            "plan": self.plan.model_dump(),
            "tasks": {k: v.model_dump() for k, v in self.tasks.items()},
            "evidence_count": len(self.evidence),
            "events_tail": self.events[-50:],
        }
        return ctx.artifacts.put_json(payload, metadata={"kind": "research_snapshot", "label": label})

    def store_evidence_batch(self, ctx: RunContext, ev: Sequence[Evidence], *, label: str) -> str:
        payload = [e.model_dump() for e in ev]
        return ctx.artifacts.put_json(payload, metadata={"kind": "research_evidence_batch", "label": label})
