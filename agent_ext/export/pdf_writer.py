from __future__ import annotations
import io
from agent_ext.export.models import ExportRequest

class PdfExporter:
    def mime_type(self) -> str:
        return "application/pdf"

    def filename(self, *, req: ExportRequest) -> str:
        return "report.pdf"

    def render_bytes(self, *, req: ExportRequest, outcome: dict) -> bytes:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=LETTER)

        width, height = LETTER
        y = height - 72

        def line(txt: str, size: int = 11):
            nonlocal y
            c.setFont("Helvetica", size)
            for chunk in (txt or "").split("\n"):
                c.drawString(72, y, chunk[:120])
                y -= 14
                if y < 72:
                    c.showPage()
                    y = height - 72

        line(req.title, 16)
        y -= 8
        line("Executive Summary", 13)
        line(str(outcome.get("answer", "")), 11)

        if req.include_claims:
            claims = outcome.get("claims") or []
            if claims:
                y -= 10
                line("Claims", 13)
                for c0 in claims:
                    txt = c0.get("text") if isinstance(c0, dict) else str(c0)
                    line(f"• {txt}")

        if req.include_limitations:
            lim = outcome.get("limitations") or []
            if lim:
                y -= 10
                line("Limitations", 13)
                for l in lim:
                    line(f"• {l}")

        c.save()
        return buf.getvalue()
