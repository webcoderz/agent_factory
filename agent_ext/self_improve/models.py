from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TriggerEvent:
    kind: str                   # "exception", "test_fail", "user_feedback"
    signature: str              # stable fingerprint (e.g., exception type + message)
    detail: str                 # human readable
    count: int = 1


@dataclass
class GatePlan:
    import_check: bool = True
    compile_check: bool = True
    pytest_paths: List[str] = field(default_factory=list)  # optional


@dataclass
class GateResults:
    ok: bool
    details: Dict[str, str] = field(default_factory=dict)


@dataclass
class PatchProposal:
    title: str
    rationale: str
    files_to_edit: List[str]
    gate_plan: GatePlan
    # Minimal diff representation; keep simple for now
    unified_diff: Optional[str] = None


@dataclass
class ImprovementRunRecord:
    trigger: TriggerEvent
    proposal: PatchProposal
    gates: GateResults
    adopted: bool
