from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from ..evidence.models import Evidence


@dataclass(frozen=True)
class OCRRetryAction:
    """
    One recommended action. Your router can pick one or sequence them.
    """
    kind: str  # "rerender_pages" | "rerun_ocr" | "rerun_ocr_pages" | "switch_engine" | "increase_dpi"
    params: Dict[str, Any]
    reason: str
    priority: int = 50  # smaller = earlier


@dataclass
class OCRRetryPlan:
    ok: bool
    actions: List[OCRRetryAction]
    summary: str
    failed_pages: List[int]
    warn_pages: List[int]
    metrics: Dict[str, Any]


def _extract_validation_evidence(evidence_chunks: Sequence[Evidence]) -> Tuple[List[Evidence], List[Evidence]]:
    """
    Returns (doc_level, page_level) validation evidences.
    """
    doc_level: List[Evidence] = []
    page_level: List[Evidence] = []
    for e in evidence_chunks:
        if e.kind != "validation":
            continue
        tags = set(e.tags or [])
        if "ocr" not in tags:
            continue
        content = e.content if isinstance(e.content, dict) else {}
        typ = content.get("type")
        if typ == "ocr_quality":
            doc_level.append(e)
        elif typ == "ocr_quality_page":
            page_level.append(e)
    return doc_level, page_level


def _pages_from_page_evidence(page_level: Sequence[Evidence]) -> Tuple[Set[int], Set[int]]:
    failed: Set[int] = set()
    warned: Set[int] = set()
    for e in page_level:
        c = e.content if isinstance(e.content, dict) else {}
        page = c.get("page_index")
        if page is None:
            continue
        tags = set(e.tags or [])
        if "validation:fail" in tags or "severity:error" in tags:
            failed.add(int(page))
        else:
            warned.add(int(page))
    return failed, warned


def _doc_failure(doc_level: Sequence[Evidence]) -> Tuple[bool, Dict[str, Any], List[Dict[str, Any]]]:
    """
    Returns (ok, metrics, issues)
    """
    if not doc_level:
        return True, {}, []
    # pick the last doc-level validation evidence
    e = doc_level[-1]
    c = e.content if isinstance(e.content, dict) else {}
    ok = bool(c.get("ok", True))
    metrics = c.get("metrics") or {}
    issues = c.get("issues") or []
    # normalize list of dicts
    issues = [i if isinstance(i, dict) else {} for i in issues]
    return ok, metrics, issues


def build_ocr_retry_plan(
    *,
    evidence_chunks: Sequence[Evidence],
    current_dpi: int = 200,
    max_dpi: int = 350,
    dpi_step: int = 100,
    current_engine: str = "primary",
    alternate_engines: Optional[List[str]] = None,
    allow_llm_vision_fallback: bool = True,
    prefer_page_subset_retry: bool = True,
) -> OCRRetryPlan:
    """
    Produces a deterministic plan from OCR validation Evidence.

    - If doc-level validation failed: propose increasing DPI, switching engine.
    - If page-level failures exist: prefer rerunning only those pages.
    - Handles common issue codes emitted by OCRValidator.
    """
    alternate_engines = alternate_engines or ["secondary", "llm_vision"]

    doc_level, page_level = _extract_validation_evidence(evidence_chunks)
    ok, metrics, issues = _doc_failure(doc_level)
    failed_pages, warn_pages = _pages_from_page_evidence(page_level)

    actions: List[OCRRetryAction] = []

    # If no failures, nothing to do
    if ok and not failed_pages:
        return OCRRetryPlan(
            ok=True,
            actions=[],
            summary="OCR validation passed; no retry actions recommended.",
            failed_pages=sorted(failed_pages),
            warn_pages=sorted(warn_pages),
            metrics=metrics,
        )

    # Determine likely failure modes
    issue_codes = {i.get("code") for i in issues if i.get("code")}
    empty_frac = float(metrics.get("empty_page_fraction", 0.0) or 0.0)
    total_chars = int(metrics.get("total_chars", 0) or 0)

    # 1) Prefer page-subset retries when we know which pages are bad
    if prefer_page_subset_retry and failed_pages:
        # Try rerender + OCR those pages only (higher DPI or alternate engine)
        next_dpi = min(max_dpi, current_dpi + dpi_step)
        if next_dpi > current_dpi:
            actions.append(
                OCRRetryAction(
                    kind="rerender_pages",
                    params={"pages": sorted(failed_pages), "dpi": next_dpi},
                    reason=f"Some pages failed OCR validation; rerendering only failed pages at higher DPI ({current_dpi}→{next_dpi}).",
                    priority=10,
                )
            )
            actions.append(
                OCRRetryAction(
                    kind="rerun_ocr_pages",
                    params={"pages": sorted(failed_pages), "engine": current_engine},
                    reason="Rerun OCR only on failed pages after rerender.",
                    priority=20,
                )
            )

        # If DPI cannot increase, switch engine on those pages
        for eng in alternate_engines:
            if eng == current_engine:
                continue
            if eng == "llm_vision" and not allow_llm_vision_fallback:
                continue
            actions.append(
                OCRRetryAction(
                    kind="rerun_ocr_pages",
                    params={"pages": sorted(failed_pages), "engine": eng},
                    reason=f"Failed pages may be layout/quality dependent; retry failed pages with alternate OCR engine '{eng}'.",
                    priority=30 if eng != "llm_vision" else 40,
                )
            )
            break  # propose only the next best engine by default

    # 2) Doc-level failures without page attribution (or lots of empties) → rerun whole doc
    if not failed_pages:
        # Increase DPI if possible
        next_dpi = min(max_dpi, current_dpi + dpi_step)
        if next_dpi > current_dpi:
            actions.append(
                OCRRetryAction(
                    kind="increase_dpi",
                    params={"from": current_dpi, "to": next_dpi},
                    reason=f"OCR failed overall quality thresholds; increasing DPI ({current_dpi}→{next_dpi}) often fixes small text or low-contrast scans.",
                    priority=10,
                )
            )
            actions.append(
                OCRRetryAction(
                    kind="rerender_pages",
                    params={"pages": "all", "dpi": next_dpi},
                    reason="Rerender all pages at higher DPI.",
                    priority=15,
                )
            )
            actions.append(
                OCRRetryAction(
                    kind="rerun_ocr",
                    params={"engine": current_engine},
                    reason="Rerun OCR on all pages after rerender.",
                    priority=20,
                )
            )

        # Switch engine whole-doc
        for eng in alternate_engines:
            if eng == current_engine:
                continue
            if eng == "llm_vision" and not allow_llm_vision_fallback:
                continue
            actions.append(
                OCRRetryAction(
                    kind="switch_engine",
                    params={"from": current_engine, "to": eng},
                    reason=f"OCR failed overall; switching engine to '{eng}' is recommended.",
                    priority=30 if eng != "llm_vision" else 40,
                )
            )
            actions.append(
                OCRRetryAction(
                    kind="rerun_ocr",
                    params={"engine": eng},
                    reason=f"Rerun OCR on all pages using '{eng}'.",
                    priority=35 if eng != "llm_vision" else 45,
                )
            )
            break

    # 3) Special-case suggestions based on issue codes
    if "missing_ocr_pages" in issue_codes:
        actions.append(
            OCRRetryAction(
                kind="rerender_pages",
                params={"pages": "missing_only", "dpi": current_dpi},
                reason="OCR output is missing pages; rerender missing pages and rerun OCR for those pages.",
                priority=5,
            )
        )

    if "too_many_empty_pages" in issue_codes or empty_frac >= 0.5:
        actions.append(
            OCRRetryAction(
                kind="switch_engine",
                params={"from": current_engine, "to": "llm_vision" if allow_llm_vision_fallback else (alternate_engines[0] if alternate_engines else "secondary")},
                reason="Many pages are empty/near-empty; this often indicates OCR engine mismatch with scan/layout. Consider LLM vision fallback.",
                priority=25,
            )
        )

    if "too_little_text" in issue_codes and total_chars < 100:
        actions.append(
            OCRRetryAction(
                kind="increase_dpi",
                params={"from": current_dpi, "to": min(max_dpi, max(current_dpi + dpi_step, 300))},
                reason="Very low total extracted text suggests poor rendering/OCR; jump DPI to 300 if possible.",
                priority=12,
            )
        )

    # Sort actions by priority
    actions = sorted(actions, key=lambda a: a.priority)

    summary_bits = []
    if failed_pages:
        summary_bits.append(f"{len(failed_pages)} pages failed validation")
    if warn_pages:
        summary_bits.append(f"{len(warn_pages)} pages have warnings")
    if not ok:
        summary_bits.append("doc-level OCR validation failed")

    summary = "; ".join(summary_bits) if summary_bits else "OCR validation indicates issues."

    return OCRRetryPlan(
        ok=False,
        actions=actions,
        summary=summary,
        failed_pages=sorted(failed_pages),
        warn_pages=sorted(warn_pages),
        metrics=metrics,
    )
