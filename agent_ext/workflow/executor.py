from __future__ import annotations

import time
from typing import Any, Dict, List

from .types import ExecutionResult, TaskRequest, WorkflowSpec


class WorkflowExecutor:
    async def execute(self, ctx, wf: WorkflowSpec, req: TaskRequest) -> ExecutionResult:
        state: Dict[str, Any] = {
            "task": {"text": req.text, "task_type": req.task_type, "hints": list(req.hints), "constraints": req.constraints},
            "scratch": {},
        }
        trace: List[Dict[str, Any]] = []
        t0 = time.time()

        ok = True
        for step in wf.steps:
            comp = ctx.workflow_registry.get_component(step.component_name)
            step_t0 = time.time()
            try:
                state = await comp.run(ctx, state)
                trace.append({
                    "step": step.component_name,
                    "ok": True,
                    "dt_ms": int((time.time() - step_t0) * 1000),
                })
            except Exception as e:
                ok = False
                trace.append({
                    "step": step.component_name,
                    "ok": False,
                    "error": repr(e),
                    "dt_ms": int((time.time() - step_t0) * 1000),
                })
                break

        dt_ms = int((time.time() - t0) * 1000)
        metrics = {"dt_ms": dt_ms}
        outputs = state.get("outputs", {})
        return ExecutionResult(ok=ok, workflow_name=wf.name, outputs=outputs, metrics=metrics, trace=trace)
