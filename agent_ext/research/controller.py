from __future__ import annotations

import time

from agent_ext.research.evidence_graph import EvidenceGraph
from agent_ext.research.executor import ResearchExecutor
from agent_ext.research.gap_analysis import propose_gaps
from agent_ext.research.ledger import ResearchLedger
from agent_ext.research.models import ResearchBudget, ResearchOutcome
from agent_ext.research.planner import ResearchPlanner
from agent_ext.research.synth import build_outcome
from agent_ext.run_context import RunContext


class DeepResearchController:
    """
    Core loop:
      plan -> (execute tasks -> collect evidence -> gap analysis -> add tasks)* -> synthesize

    This is the missing “deep research” layer.
    """

    def __init__(
        self,
        *,
        planner: ResearchPlanner,
        executor: ResearchExecutor,
        budget: ResearchBudget = ResearchBudget(),
        enable_gap_analysis: bool = True,
        max_gap_iterations: int = 3,
        persist_snapshots: bool = True,
    ):
        self.planner = planner
        self.executor = executor
        self.budget = budget
        self.enable_gap_analysis = enable_gap_analysis
        self.max_gap_iterations = max_gap_iterations
        self.persist_snapshots = persist_snapshots

    async def run(self, ctx: RunContext, *, question: str) -> ResearchOutcome:
        t0 = time.time()
        steps = 0

        plan = self.planner.make_plan(question)
        ledger = ResearchLedger(plan=plan)
        graph = EvidenceGraph()

        ledger.add_event("research_start", {"question": question})
        if self.persist_snapshots:
            ledger.store_snapshot(ctx, label="start")

        gap_iter = 0

        while steps < self.budget.max_steps and (time.time() - t0) < self.budget.max_runtime_s:
            runnable = ledger.runnable_tasks()
            if not runnable:
                # optionally propose gaps
                if self.enable_gap_analysis and gap_iter < self.max_gap_iterations:
                    gap_iter += 1
                    new_tasks = propose_gaps(ledger, graph)
                    if new_tasks:
                        for t in new_tasks:
                            if t.id in ledger.tasks:
                                continue
                            ledger.tasks[t.id] = t
                            ledger.plan.tasks.append(t)
                        ledger.add_event("gaps_added", {"count": len(new_tasks), "gap_iter": gap_iter})
                        continue
                break

            task = runnable[0]  # deterministic: take highest priority runnable
            steps += 1

            try:
                ev = await self.executor.run_task(ctx, task, ledger)
            except Exception:
                # retry if allowed
                if self.executor.should_retry(task):
                    task.status = "pending"
                    continue
                # else continue with remaining tasks
                continue

            # store evidence + build graph
            ids = ledger.add_evidence(ev)
            for eid, e in zip(ids, ev):
                graph.add(eid, e)

            # persist evidence batch for audit
            if self.persist_snapshots and ev:
                ledger.store_evidence_batch(ctx, ev, label=f"step_{steps}_{task.id}")

            # stop early if synth task done and we have enough evidence
            if task.kind == "synthesize" and task.status == "done":
                break

        # final snapshot
        if self.persist_snapshots:
            ledger.store_snapshot(ctx, label="end")

        outcome = build_outcome(question, ledger.evidence)
        outcome.steps_taken = steps
        outcome.plan = ledger.plan
        ledger.add_event("research_end", {"steps": steps})

        # store final report artifact
        ctx.artifacts.put_json(
            outcome.model_dump(),
            metadata={"kind": "research_outcome", "case_id": ctx.case_id, "session_id": ctx.session_id},
        )
        return outcome
