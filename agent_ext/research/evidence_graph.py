from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from agent_ext.evidence.models import Evidence


@dataclass
class EvidenceGraph:
    """
    Minimal "investigation graph" of the research run:
    - evidence nodes
    - links to sources (artifact ids, URLs, doc ids)
    """
    evidence_nodes: Dict[str, Evidence] = field(default_factory=dict)
    sources_by_evidence: Dict[str, Set[str]] = field(default_factory=dict)

    def add(self, evidence_id: str, ev: Evidence) -> None:
        self.evidence_nodes[evidence_id] = ev
        srcs: Set[str] = set()
        for c in ev.citations:
            if c.source_id:
                srcs.add(c.source_id)
        for aid in ev.provenance.artifact_ids:
            if aid:
                srcs.add(aid)
        self.sources_by_evidence[evidence_id] = srcs

    def all_sources(self) -> Set[str]:
        out: Set[str] = set()
        for s in self.sources_by_evidence.values():
            out |= s
        return out

    def evidence_without_citations(self) -> List[str]:
        return [eid for eid, ev in self.evidence_nodes.items() if not ev.citations]

    def validation_failures(self) -> List[str]:
        bad: List[str] = []
        for eid, ev in self.evidence_nodes.items():
            if ev.kind == "validation" and any(t == "validation:fail" for t in (ev.tags or [])):
                bad.append(eid)
        return bad
