from __future__ import annotations

"""
DOCX → OCRPage parser (fast path).

Allows DOCX ingestion without OCR by converting native
document text into pseudo OCRPage objects so the rest
of your pipeline stays unchanged.
"""

from dataclasses import dataclass

from .models import OCRPage


@dataclass
class DocxParser:
    paragraphs_per_chunk: int = 40

    def parse_bytes(self, doc_bytes: bytes) -> list[OCRPage]:
        try:
            from docx import Document
        except Exception as e:
            raise ImportError("python-docx is required. Install with: pip install python-docx") from e

        import io

        doc = Document(io.BytesIO(doc_bytes))

        pages: list[OCRPage] = []
        buf: list[str] = []
        page_index = 0

        def flush():
            nonlocal page_index, buf
            if not buf:
                return

            pages.append(
                OCRPage(
                    page_index=page_index,
                    spans=[],
                    full_text="\n".join(buf).strip(),
                    engine="docx_parser",
                    metadata={"paragraph_count": len(buf)},
                )
            )

            page_index += 1
            buf = []

        # paragraphs
        for p in doc.paragraphs:
            txt = (p.text or "").strip()
            if not txt:
                continue

            buf.append(txt)

            if len(buf) >= self.paragraphs_per_chunk:
                flush()

        # tables
        for table in getattr(doc, "tables", []):
            rows = []
            for row in table.rows:
                cells = [(c.text or "").strip() for c in row.cells]
                if any(cells):
                    rows.append("\t".join(cells))

            if rows:
                buf.append("\n".join(rows))

            if len(buf) >= self.paragraphs_per_chunk:
                flush()

        flush()
        return pages
