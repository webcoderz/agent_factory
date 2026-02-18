from __future__ import annotations
from html import escape
from agent_ext.export.base import Exporter
from agent_ext.export.models import ExportRequest

class HtmlExporter:
    def mime_type(self) -> str:
        return "text/html; charset=utf-8"

    def filename(self, *, req: ExportRequest) -> str:
        return "report.html"

    def render_bytes(self, *, req: ExportRequest, outcome: dict) -> bytes:
        title = escape(req.title)
        answer = escape(str(outcome.get("answer", "")))

        claims = outcome.get("claims") or []
        limitations = outcome.get("limitations") or []

        def li(items):
            return "\n".join(f"<li>{escape(str(x.get('text', x)))}</li>" if isinstance(x, dict) else f"<li>{escape(str(x))}</li>" for x in items)

        html = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>{title}</title></head>
<body>
  <h1>{title}</h1>
  <h2>Executive Summary</h2>
  <p>{answer}</p>

  {"<h2>Claims</h2><ul>" + li(claims) + "</ul>" if req.include_claims and claims else ""}
  {"<h2>Limitations</h2><ul>" + li(limitations) + "</ul>" if req.include_limitations and limitations else ""}
</body>
</html>
"""
        return html.encode("utf-8")
