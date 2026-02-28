from __future__ import annotations

from collections.abc import Sequence

from agent_ext.evidence.models import Evidence
from agent_ext.research.models import Claim, ResearchOutcome


def build_claims_from_evidence(evidence: Sequence[Evidence], *, max_claims: int = 12) -> list[Claim]:
    """
    Deterministic baseline claim builder:
    - turns 'finding' / 'structured' / 'web_capture' / 'doc_extract' into claims.
    In real use, you’ll replace this with an LLM-based claim extractor + validator.
    """
    claims: list[Claim] = []
    i = 0
    for ev in evidence:
        if ev.kind not in {"finding", "structured", "web_capture", "doc_extract", "text"}:
            continue
        i += 1
        txt = ""
        if isinstance(ev.content, dict):
            txt = ev.content.get("summary") or ev.content.get("text") or str(ev.content)[:500]
        else:
            txt = str(ev.content)[:500]

        cits = [c.model_dump() for c in (ev.citations or [])]
        claims.append(
            Claim(
                id=f"c{i}",
                text=txt if txt else f"Claim derived from evidence {i}",
                confidence=min(0.9, max(0.4, ev.confidence or 0.7)),
                citations=cits,
                tags=list(ev.tags or []),
                derived_from_evidence_ids=[],
            )
        )
        if len(claims) >= max_claims:
            break
    return claims


def synthesize_answer(question: str, claims: list[Claim]) -> str:
    """
    Deterministic baseline synthesis.
    Replace with a PydanticAI synth agent for better narrative.
    """
    lines = [f"Question: {question}", ""]
    if not claims:
        lines.append("No sufficient evidence was collected to answer confidently.")
        return "\n".join(lines)

    lines.append("Findings:")
    for c in claims[:10]:
        lines.append(f"- {c.text}")
    lines.append("")
    lines.append(
        "Limitations: This answer is based on the collected evidence; some claims may be incomplete or require additional sources."
    )
    return "\n".join(lines)


def build_outcome(question: str, evidence: Sequence[Evidence]) -> ResearchOutcome:
    claims = build_claims_from_evidence(evidence)
    answer = synthesize_answer(question, claims)
    evidence_ids = []  # you can fill with ledger evidence ids if you want
    limitations = []
    # add a limitation if OCR validation failed
    if any(ev.kind == "validation" and "validation:fail" in (ev.tags or []) for ev in evidence):
        limitations.append("Some OCR validation checks failed; extracted text may be incomplete or inaccurate.")
    return ResearchOutcome(
        question=question,
        answer=answer,
        structured={"claims_count": len(claims)},
        claims=claims,
        evidence_ids=evidence_ids,
        limitations=limitations,
    )
