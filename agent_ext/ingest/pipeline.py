from __future__ import annotations
from typing import List, Optional

from ...types import RunContext
from .models import DocumentInput, IngestResult
from .pdf_to_images import PDFToImages
from .ocr_engines import OCREngine
from .extractors import PageExtractor
from .validation import OCRValidator, OCRValidationPolicy
from .validation_evidence import ValidationEvidenceEmitter

class IngestPipeline:
    def __init__(
        self,
        *,
        pdf_to_images: Optional[PDFToImages],
        ocr_engine: OCREngine,
        extractor: PageExtractor,
        validator: OCRValidator | None = None,
        validation_evidence_emitter: ValidationEvidenceEmitter | None = None,
        fail_fast_on_validation: bool = True,
    ):
        self.pdf_to_images = pdf_to_images
        self.ocr_engine = ocr_engine
        self.extractor = extractor
        self.validator = validator
        self.validation_evidence_emitter = validation_evidence_emitter
        self.fail_fast_on_validation = fail_fast_on_validation

    def run(self, ctx: RunContext, doc: DocumentInput) -> IngestResult:
        if not doc.artifact_id:
            raise ValueError("IngestPipeline expects doc.artifact_id for auditability")
        doc_id = doc.artifact_id

        # 1) produce page images (if pdf renderer provided)
        page_images = self.pdf_to_images.run(ctx, doc) if self.pdf_to_images else []

        # 2) OCR (if we have images; other paths can be added later)
        ocr_pages = self.ocr_engine.ocr_pages(ctx, page_images)

        validation_evidence = []
        if self.validator:
            report = self.validator.validate_pages(page_images=page_images, ocr_pages=ocr_pages)
            ctx.logger.info("ocr.validation", ok=report.ok, metrics=report.metrics, trace_id=ctx.trace_id)
            report.raise_if_failed()

        if self.fail_fast_on_validation:
            report.raise_if_failed()
        # 3) Extract → Evidence
        evidence = self.extractor.extract(
            ctx, 
            doc_artifact_id=doc_id, 
            pages=ocr_pages
            )

        return IngestResult(
            doc_artifact_id=doc_id,
            page_images=page_images,
            ocr_pages=ocr_pages,
            evidence_chunks=[*validation_evidence, *evidence],
        )
