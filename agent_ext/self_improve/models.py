from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TriggerEvent:
    kind: str  # "exception", "test_fail", "user_feedback"
    signature: str  # stable fingerprint (e.g., exception type + message)
    detail: str  # human readable
    count: int = 1


@dataclass
class GatePlan:
    import_check: bool = True
    compile_check: bool = True
    pytest_paths: list[str] = field(default_factory=list)  # optional


@dataclass
class GateResults:
    ok: bool
    details: dict[str, str] = field(default_factory=dict)


@dataclass
class PatchProposal:
    title: str
    rationale: str
    files_to_edit: list[str]
    gate_plan: GatePlan
    # Minimal diff representation; keep simple for now
    unified_diff: str | None = None


@dataclass
class ImprovementRunRecord:
    trigger: TriggerEvent
    proposal: PatchProposal
    gates: GateResults
    adopted: bool
