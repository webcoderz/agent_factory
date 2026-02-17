from __future__ import annotations

from typing import Sequence

from agent_ext.evidence.models import Evidence, Provenance, Citation
from agent_ext.run_context import RunContext
from agent_ext.research.models import ResearchTask
from agent_ext.research.ledger import ResearchLedger
from agent_ext.research.synth import build_outcome


async def handle_analyze(ctx: RunContext, task: ResearchTask, ledger: ResearchLedger) -> Sequence[Evidence]:
    # Deterministic analysis note (replace with PydanticAI analysis agent later)
    return [
        Evidence(
            kind="note",
            content={"goal": task.goal, "inputs": task.inputs, "note": "Analysis placeholder (wire to PydanticAI)."},
            citations=[],
            provenance=Provenance(produced_by="handle_analyze", artifact_ids=[]),
            confidence=0.6,
            tags=["research", "analyze"],
        )
    ]


async def handle_search(ctx: RunContext, task: ResearchTask, ledger: ResearchLedger) -> Sequence[Evidence]:
    # Placeholder: if you have a web/retrieval tool, call it here.
    # For now return a note with the query.
    return [
        Evidence(
            kind="note",
            content={"goal": task.goal, "query": task.query, "note": "Search handler placeholder (wire to retrieval/web tool)."},
            citations=[],
            provenance=Provenance(produced_by="handle_search", artifact_ids=[]),
            confidence=0.3,
            tags=["research", "search", "placeholder"],
        )
    ]


async def handle_subagent(ctx: RunContext, task: ResearchTask, ledger: ResearchLedger) -> Sequence[Evidence]:
    # Example: call ctx.subagents["orchestrator"] if available
    orch = ctx.subagents["orchestrator"]
    name = task.inputs.get("subagent_name")
    payload = task.inputs.get("payload", {})
    results = await orch.run_many(ctx, [(name, payload, {"task_id": task.id})], timeout_s=task.inputs.get("timeout_s", 60))
    res = results.get(name)
    return [
        Evidence(
            kind="finding",
            content={"subagent": name, "output": getattr(res, "output", None), "ok": getattr(res, "ok", False)},
            citations=[],
            provenance=Provenance(produced_by=f"subagent:{name}", artifact_ids=[]),
            confidence=0.7 if getattr(res, "ok", False) else 0.2,
            tags=["research", "subagent"],
        )
    ]


async def handle_synthesize(ctx: RunContext, task: ResearchTask, ledger: ResearchLedger) -> Sequence[Evidence]:
    out = build_outcome(ledger.plan.question, ledger.evidence)
    # Emit as Evidence too
    return [
        Evidence(
            kind="finding",
            content={"final_answer": out.answer, "limitations": out.limitations, "claims": [c.model_dump() for c in out.claims]},
            citations=[],
            provenance=Provenance(produced_by="handle_synthesize", artifact_ids=[]),
            confidence=0.75,
            tags=["research", "synthesis"],
        )
    ]
