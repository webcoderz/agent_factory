from __future__ import annotations

from agent_ext.evidence.models import Citation, Evidence, Provenance
from agent_ext.run_context import RunContext

from .validation import OCRValidationReport, ValidationIssue


class ValidationEvidenceEmitter:
    """
    Converts validation reports into Evidence so:
    - the judge can see it
    - the router can branch on it
    - you can search / audit past runs
    """

    def __init__(
        self,
        *,
        emit_page_level: bool = True,
        store_full_report_artifact: bool = True,
    ):
        self.emit_page_level = emit_page_level
        self.store_full_report_artifact = store_full_report_artifact
        self.name = "validation_emitter"

    def emit_ocr_validation(
        self,
        ctx: RunContext,
        *,
        doc_artifact_id: str,
        report: OCRValidationReport,
    ) -> list[Evidence]:
        evidences: list[Evidence] = []

        report_artifact_id: str | None = None
        if self.store_full_report_artifact:
            report_artifact_id = ctx.artifacts.put_json(
                report.model_dump(),
                metadata={
                    "kind": "ocr_validation_report",
                    "case_id": ctx.case_id,
                    "session_id": ctx.session_id,
                    "doc_artifact_id": doc_artifact_id,
                    "trace_id": ctx.trace_id,
                    "ok": report.ok,
                },
            )

        # Top-level validation evidence
        tags = ["validation", "ocr"]
        if report.ok:
            tags.append("validation:pass")
        else:
            tags.append("validation:fail")

        # No "citation" required for validation, but we can link to the doc artifact for traceability.
        cit = Citation(source_id=doc_artifact_id, locator="document", confidence=1.0)

        top = Evidence(
            kind="validation",
            content={
                "type": "ocr_quality",
                "ok": report.ok,
                "metrics": report.metrics,
                "issues": [i.model_dump() for i in report.issues],
                "report_artifact_id": report_artifact_id,
            },
            citations=[cit],
            provenance=Provenance(
                produced_by=self.name,
                artifact_ids=[x for x in [doc_artifact_id, report_artifact_id] if x],
                metadata={"trace_id": ctx.trace_id},
            ),
            confidence=1.0,
            tags=tags,
        )
        evidences.append(top)

        # Optional: page-level validation evidence for targeted fallback/retry
        if self.emit_page_level:
            evidences.extend(self._emit_page_level(ctx, doc_artifact_id, report, report_artifact_id))

        return evidences

    def _emit_page_level(
        self,
        ctx: RunContext,
        doc_artifact_id: str,
        report: OCRValidationReport,
        report_artifact_id: str | None,
    ) -> list[Evidence]:
        out: list[Evidence] = []
        by_page: dict[int, list[ValidationIssue]] = {}
        for issue in report.issues:
            if issue.page_index is None:
                continue
            by_page.setdefault(issue.page_index, []).append(issue)

        for page_idx, issues in sorted(by_page.items()):
            # Link directly to the page
            cit = Citation(source_id=doc_artifact_id, locator=f"page:{page_idx}", confidence=1.0)

            sev = "warn"
            if any(i.severity == "error" for i in issues):
                sev = "error"
            tags = ["validation", "ocr", f"page:{page_idx}", f"severity:{sev}"]
            if sev == "error":
                tags.append("validation:fail")

            out.append(
                Evidence(
                    kind="validation",
                    content={
                        "type": "ocr_quality_page",
                        "page_index": page_idx,
                        "issues": [i.model_dump() for i in issues],
                        "report_artifact_id": report_artifact_id,
                    },
                    citations=[cit],
                    provenance=Provenance(
                        produced_by=self.name,
                        artifact_ids=[x for x in [doc_artifact_id, report_artifact_id] if x],
                        metadata={"trace_id": ctx.trace_id},
                    ),
                    confidence=1.0,
                    tags=tags,
                )
            )

        return out
