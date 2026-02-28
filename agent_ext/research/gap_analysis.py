from __future__ import annotations

from agent_ext.research.evidence_graph import EvidenceGraph
from agent_ext.research.ledger import ResearchLedger
from agent_ext.research.models import ResearchTask


def propose_gaps(
    ledger: ResearchLedger,
    graph: EvidenceGraph,
    *,
    max_new_tasks: int = 6,
) -> list[ResearchTask]:
    """
    Deterministic gap finder:
    - uncited evidence -> add 'find source' task
    - OCR validation failures -> add 'retry OCR' task
    - too little evidence overall -> broaden search
    """
    new_tasks: list[ResearchTask] = []

    # 1) Uncited evidence (often model notes) -> request citations
    uncited = graph.evidence_without_citations()
    if uncited:
        new_tasks.append(
            ResearchTask(
                id=f"gap_citations_{len(ledger.tasks) + 1}",
                kind="analyze",
                goal="Review findings that lack citations and either add citations or mark as inference/uncertain.",
                inputs={"evidence_ids": uncited[:20]},
                priority=12,
                tags=["gap", "citations"],
            )
        )

    # 2) OCR validation failures -> schedule retry task
    val_fails = graph.validation_failures()
    if val_fails:
        new_tasks.append(
            ResearchTask(
                id=f"gap_ocr_retry_{len(ledger.tasks) + 1}",
                kind="analyze",
                goal="OCR validation failed. Build and execute an OCR retry plan (higher DPI / alternate engine / rerun bad pages).",
                inputs={"validation_evidence_ids": val_fails},
                priority=10,
                tags=["gap", "ocr"],
            )
        )

    # 3) If too little evidence, add a broader search/browse task (if you support it)
    if len(graph.evidence_nodes) < 3:
        new_tasks.append(
            ResearchTask(
                id=f"gap_broaden_{len(ledger.tasks) + 1}",
                kind="search",
                goal="Gather more sources relevant to the question; broaden query and collect citations.",
                query=ledger.plan.question,
                priority=20,
                tags=["gap", "coverage"],
            )
        )

    return new_tasks[:max_new_tasks]
