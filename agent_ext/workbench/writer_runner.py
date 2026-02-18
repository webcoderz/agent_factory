from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .locks import LeaseLockStore
from .worktrees import WorktreeHandle, cleanup_worktree, create_worktree, worktree_diff


@dataclass(frozen=True)
class WriterResult:
    ok: bool
    diff: str
    meta: Dict[str, Any]


class WriterCoordinator:
    def __init__(self):
        self.locks = LeaseLockStore()

    async def run_writer(
        self,
        ctx,
        *,
        run_id: str,
        agent_name: str,
        write_key: str,
        subagent,                      # must have async run(ctx, input, meta)
        input: Any,
        meta: Dict[str, Any],
        ttl_s: int = 900,
        prune_branch: bool = False,
    ) -> WriterResult:
        owner = f"{run_id}:{agent_name}"
        lease = self.locks.try_acquire(key=write_key, owner=owner, ttl_s=ttl_s)
        if not lease:
            return WriterResult(ok=False, diff="", meta={"error": f"lock busy: {write_key}"})

        wt: Optional[WorktreeHandle] = None
        try:
            wt = create_worktree(run_id=run_id, agent_name=agent_name)
            # Tell the subagent to operate inside the worktree path
            meta2 = dict(meta)
            meta2["workdir"] = str(wt.path)

            # Important: subagent should ONLY write inside meta["workdir"]
            res = await subagent.run(ctx, input=input, meta=meta2)

            diff = worktree_diff(wt)
            return WriterResult(ok=res.ok, diff=diff, meta={"subagent_meta": res.meta, "worktree": str(wt.path)})

        finally:
            # Release lock and cleanup worktree
            self.locks.release(lease)
            if wt is not None:
                cleanup_worktree(wt, prune_branch=prune_branch)
