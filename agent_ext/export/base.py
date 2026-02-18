from __future__ import annotations
from typing import Protocol
from agent_ext.export.models import ExportRequest, ExportResult

class Exporter(Protocol):
    def render_bytes(self, *, req: ExportRequest, outcome: dict) -> bytes: ...
    def filename(self, *, req: ExportRequest) -> str: ...
    def mime_type(self) -> str: ...

    def render_artifact(self, ctx, *, req: ExportRequest, outcome: dict) -> ExportResult:
        b = self.render_bytes(req=req, outcome=outcome)
        aid = ctx.artifacts.put_bytes(
            b,
            filename=self.filename(req=req),
            metadata={"kind": "export", "format": req.format, "title": req.title},
        )
        return ExportResult(
            format=req.format,
            filename=self.filename(req=req),
            mime_type=self.mime_type(),
            bytes_len=len(b),
            artifact_id=aid,
        )
