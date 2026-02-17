from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Protocol, Tuple

from pydantic import BaseModel, Field, ValidationError

from .models import OCRPage, OCRSpan, PageImage


# ----------------------------
# Validation outputs
# ----------------------------

class ValidationIssue(BaseModel):
    code: str
    severity: str = "warn"  # info|warn|error
    message: str
    page_index: Optional[int] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)


class OCRValidationReport(BaseModel):
    ok: bool
    issues: List[ValidationIssue] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)

    def raise_if_failed(self) -> None:
        if not self.ok:
            msgs = "; ".join([f"{i.code}:{i.message}" for i in self.issues if i.severity == "error"])
            raise RuntimeError(f"OCR validation failed: {msgs}")


# ----------------------------
# Policies
# ----------------------------

class OCRValidationPolicy(BaseModel):
    min_pages: int = 1
    min_chars_per_page: int = 40
    min_total_chars: int = 200
    min_alpha_ratio: float = 0.20          # alpha chars / total chars
    max_garbage_ratio: float = 0.35        # weird chars ratio
    max_empty_page_fraction: float = 0.40  # allow some blank pages
    require_monotonic_pages: bool = True   # page indexes unique/increasing
    min_span_confidence: float = 0.40      # if spans exist
    allow_no_spans: bool = True            # engines may not produce spans


# ----------------------------
# Helpers
# ----------------------------

_WEIRD = re.compile(r"[^\w\s\.,;:\-–—\(\)\[\]{}'\"/\\@#%&\+\*=<>!?$]")

def _alpha_ratio(s: str) -> float:
    if not s:
        return 0.0
    alpha = sum(c.isalpha() for c in s)
    return alpha / max(1, len(s))

def _garbage_ratio(s: str) -> float:
    if not s:
        return 0.0
    weird = len(_WEIRD.findall(s))
    return weird / max(1, len(s))

def _count_chars(p: OCRPage) -> int:
    return len(p.full_text or "")


# ----------------------------
# Validator
# ----------------------------

class OCRValidator:
    def __init__(self, policy: OCRValidationPolicy = OCRValidationPolicy()):
        self.policy = policy

    def validate_pages(
        self,
        *,
        page_images: List[PageImage],
        ocr_pages: List[OCRPage],
    ) -> OCRValidationReport:
        issues: List[ValidationIssue] = []
        metrics: Dict[str, Any] = {}

        if len(page_images) < self.policy.min_pages:
            issues.append(ValidationIssue(
                code="too_few_pages",
                severity="error",
                message=f"Expected >= {self.policy.min_pages} pages, got {len(page_images)}",
            ))

        # page index monotonic + coverage checks
        img_idx = [p.page_index for p in page_images]
        ocr_idx = [p.page_index for p in ocr_pages]

        if self.policy.require_monotonic_pages:
            if img_idx != sorted(img_idx) or len(set(img_idx)) != len(img_idx):
                issues.append(ValidationIssue(
                    code="non_monotonic_page_images",
                    severity="error",
                    message="PageImage.page_index must be unique and increasing",
                    evidence={"indexes": img_idx},
                ))
            if ocr_idx != sorted(ocr_idx) or len(set(ocr_idx)) != len(ocr_idx):
                issues.append(ValidationIssue(
                    code="non_monotonic_ocr_pages",
                    severity="error",
                    message="OCRPage.page_index must be unique and increasing",
                    evidence={"indexes": ocr_idx},
                ))

        # coverage
        missing = sorted(set(img_idx) - set(ocr_idx))
        if missing:
            issues.append(ValidationIssue(
                code="missing_ocr_pages",
                severity="error",
                message=f"OCR missing pages: {missing[:20]}{'...' if len(missing) > 20 else ''}",
                evidence={"missing": missing},
            ))

        # text quality metrics
        total_chars = sum(_count_chars(p) for p in ocr_pages)
        metrics["total_chars"] = total_chars
        metrics["pages"] = len(ocr_pages)

        if total_chars < self.policy.min_total_chars:
            issues.append(ValidationIssue(
                code="too_little_text",
                severity="error",
                message=f"Total OCR chars {total_chars} < {self.policy.min_total_chars}",
                evidence={"total_chars": total_chars},
            ))

        empty_pages = [p.page_index for p in ocr_pages if _count_chars(p) < self.policy.min_chars_per_page]
        empty_frac = (len(empty_pages) / max(1, len(ocr_pages)))
        metrics["empty_page_fraction"] = empty_frac

        if empty_frac > self.policy.max_empty_page_fraction:
            issues.append(ValidationIssue(
                code="too_many_empty_pages",
                severity="error",
                message=f"Empty page fraction {empty_frac:.2f} > {self.policy.max_empty_page_fraction:.2f}",
                evidence={"empty_pages": empty_pages[:50]},
            ))

        # per-page ratios
        bad_alpha: List[int] = []
        bad_garbage: List[int] = []
        for p in ocr_pages:
            txt = p.full_text or ""
            if _alpha_ratio(txt) < self.policy.min_alpha_ratio:
                bad_alpha.append(p.page_index)
            if _garbage_ratio(txt) > self.policy.max_garbage_ratio:
                bad_garbage.append(p.page_index)

            # spans confidence check (if spans exist)
            if p.spans:
                low = [s.confidence for s in p.spans if s.confidence < self.policy.min_span_confidence]
                if low and len(low) / max(1, len(p.spans)) > 0.5:
                    issues.append(ValidationIssue(
                        code="low_span_confidence",
                        severity="warn",
                        page_index=p.page_index,
                        message="Many spans have low confidence",
                        evidence={"min_span_confidence": self.policy.min_span_confidence},
                    ))
            else:
                if not self.policy.allow_no_spans:
                    issues.append(ValidationIssue(
                        code="missing_spans",
                        severity="warn",
                        page_index=p.page_index,
                        message="OCR engine produced no spans",
                    ))

        metrics["bad_alpha_pages"] = len(bad_alpha)
        metrics["bad_garbage_pages"] = len(bad_garbage)

        if bad_alpha:
            issues.append(ValidationIssue(
                code="low_alpha_ratio_pages",
                severity="warn",
                message="Some pages have unusually low alphabetic content",
                evidence={"pages": bad_alpha[:50]},
            ))
        if bad_garbage:
            issues.append(ValidationIssue(
                code="high_garbage_ratio_pages",
                severity="warn",
                message="Some pages contain many unusual characters (possible OCR failure)",
                evidence={"pages": bad_garbage[:50]},
            ))

        ok = not any(i.severity == "error" for i in issues)
        return OCRValidationReport(ok=ok, issues=issues, metrics=metrics)


# ----------------------------
# Structured output validation
# ----------------------------

class StructuredOutputValidator:
    """
    Validates the structured output conforms to a specific Pydantic model.
    Useful when you do LLM-based extraction.
    """
    def validate(self, *, model_type: type[BaseModel], obj: Any) -> Tuple[bool, Optional[str]]:
        try:
            model_type.model_validate(obj)
            return True, None
        except ValidationError as e:
            return False, str(e)
