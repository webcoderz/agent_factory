from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

from pdf2image import convert_from_bytes, pdfinfo_from_bytes


@dataclass
class Pdf2ImageRenderer:
    """
    PDFRenderer implementation using pdf2image + poppler.

    Notes:
    - convert_from_bytes can render a single page range (first_page/last_page)
      which we use to avoid loading all pages into memory at once.
    - pdfinfo_from_bytes gives page count quickly.
    """
    fmt: str = "png"
    poppler_path: Optional[str] = None  # set if poppler isn't on PATH

    def page_count(self, *, pdf_bytes: bytes) -> int:
        info = pdfinfo_from_bytes(pdf_bytes, poppler_path=self.poppler_path)
        return int(info["Pages"])

    def render_to_png_bytes(self, *, pdf_bytes: bytes, page_index: int, dpi: int) -> bytes:
        # pdf2image uses 1-indexed pages
        first = page_index + 1
        images = convert_from_bytes(
            pdf_bytes,
            dpi=dpi,
            first_page=first,
            last_page=first,
            fmt=self.fmt,
            poppler_path=self.poppler_path,
            thread_count=1,  # keep deterministic + avoid CPU spikes; tune later
        )
        if not images:
            raise RuntimeError(f"Failed to render page {page_index}")

        img = images[0]
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
