from __future__ import annotations

import json
from pathlib import Path

from .gates import run_gates
from .models import ImprovementRunRecord, PatchProposal, TriggerEvent
from .patching import apply_unified_diff

RUNS_DIR = Path(".agent_state/runs")


class SelfImproveController:
    """
    Trigger-driven: does nothing unless you call run_once(trigger, proposal).
    In the next iteration, we’ll have the agent generate the proposal/diff.
    For now, it’s the plumbing for: apply diff -> run gates -> record result.
    """

    def __init__(self):
        RUNS_DIR.mkdir(parents=True, exist_ok=True)

    def run_once(self, trigger: TriggerEvent, proposal: PatchProposal, *, adopt: bool = False) -> ImprovementRunRecord:
        # 1) apply patch if present
        if proposal.unified_diff:
            ok, out = apply_unified_diff(proposal.unified_diff)
            if not ok:
                rec = ImprovementRunRecord(
                    trigger=trigger, proposal=proposal, gates=run_gates(proposal.gate_plan), adopted=False
                )
                self._write_record(rec, extra={"patch_apply_error": out})
                return rec

        # 2) run gates
        gates = run_gates(proposal.gate_plan)

        # 3) decide adoption (for now, adoption = “keep the changes”)
        adopted = bool(adopt and gates.ok)

        rec = ImprovementRunRecord(trigger=trigger, proposal=proposal, gates=gates, adopted=adopted)
        self._write_record(rec)
        return rec

    def _write_record(self, rec: ImprovementRunRecord, extra: dict | None = None) -> None:
        payload = {
            "trigger": rec.trigger.__dict__,
            "proposal": {
                "title": rec.proposal.title,
                "rationale": rec.proposal.rationale,
                "files_to_edit": rec.proposal.files_to_edit,
                "gate_plan": rec.proposal.gate_plan.__dict__,
                "has_diff": bool(rec.proposal.unified_diff),
            },
            "gates": {"ok": rec.gates.ok, "details": rec.gates.details},
            "adopted": rec.adopted,
        }
        if extra:
            payload["extra"] = extra
        out = RUNS_DIR / f"run_{rec.trigger.kind}_{abs(hash(rec.trigger.signature))}.json"
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
