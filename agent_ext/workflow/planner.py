from __future__ import annotations

from .bandit import UCB1Bandit
from .experience import ExperienceStore
from .types import TaskRequest, WorkflowSpec


class WorkflowPlanner:
    def __init__(self, exp: ExperienceStore):
        self.exp = exp
        self.bandits = {}  # bucket -> bandit

    def _bucket(self, req: TaskRequest) -> str:
        hints = ",".join(sorted(req.hints)) if req.hints else ""
        return f"{req.task_type}|{hints}"

    def candidates(self, ctx, req: TaskRequest) -> list[str]:
        # Very simple matching rules to start; extend as needed
        names = ctx.workflow_registry.list_workflows()
        out = []
        for n in names:
            wf = ctx.workflow_registry.workflows[n]
            tags = ctx.workflow_registry.workflow_capability_signature(wf)

            if req.task_type == "ocr" and "ocr" not in tags:
                continue
            if "needs_memory" in req.hints and "memory" not in tags:
                continue
            if "needs_planning" in req.hints and "plan" not in tags:
                continue

            out.append(n)

        return out or names  # fallback

    def choose(self, ctx, req: TaskRequest) -> WorkflowSpec:
        cands = self.candidates(ctx, req)
        bucket = self._bucket(req)

        bandit = self.bandits.get(bucket)
        if bandit is None:
            bandit = UCB1Bandit()
            # warm-start from experience
            for row in self.exp.get_bucket_stats(req):
                bandit.observe(row["workflow"], float(row["reward"]))
            self.bandits[bucket] = bandit

        chosen = bandit.choose(cands)
        return ctx.workflow_registry.workflows[chosen]

    def observe(self, req: TaskRequest, workflow_name: str, reward: float) -> None:
        bucket = self._bucket(req)
        bandit = self.bandits.get(bucket)
        if bandit is None:
            bandit = UCB1Bandit()
            self.bandits[bucket] = bandit
        bandit.observe(workflow_name, reward)
