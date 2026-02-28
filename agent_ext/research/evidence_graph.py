from __future__ import annotations

from dataclasses import dataclass, field

from agent_ext.evidence.models import Evidence


@dataclass
class EvidenceGraph:
    """
    Minimal "investigation graph" of the research run:
    - evidence nodes
    - links to sources (artifact ids, URLs, doc ids)
    """

    evidence_nodes: dict[str, Evidence] = field(default_factory=dict)
    sources_by_evidence: dict[str, set[str]] = field(default_factory=dict)

    def add(self, evidence_id: str, ev: Evidence) -> None:
        self.evidence_nodes[evidence_id] = ev
        srcs: set[str] = set()
        for c in ev.citations:
            if c.source_id:
                srcs.add(c.source_id)
        for aid in ev.provenance.artifact_ids:
            if aid:
                srcs.add(aid)
        self.sources_by_evidence[evidence_id] = srcs

    def all_sources(self) -> set[str]:
        out: set[str] = set()
        for s in self.sources_by_evidence.values():
            out |= s
        return out

    def evidence_without_citations(self) -> list[str]:
        return [eid for eid, ev in self.evidence_nodes.items() if not ev.citations]

    def validation_failures(self) -> list[str]:
        bad: list[str] = []
        for eid, ev in self.evidence_nodes.items():
            if ev.kind == "validation" and any(t == "validation:fail" for t in (ev.tags or [])):
                bad.append(eid)
        return bad
