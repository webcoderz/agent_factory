"""
Minimal demo: OCR using our wrapped agent and ingest pipeline (vision/LLM per page).

Uses RunContext, PydanticAIAgentBase[PageOCROutput], LLMVisionOCREngine, IngestPipeline.
Pattern matches the pydantic-ai OCR examples (PDF → images → LLM per page → structured output)
but wired to our stack. Not a copy of those scripts.

Run:
  Set OCR_DEMO_PDF to a PDF path and OPENAI_API_KEY; then from repo root:
  uv run python -m agent_ext.examples.ocr_with_agent_demo
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Dict

# Add parent so agent_ext is importable when run as script
import sys
from pathlib import Path
_root = Path(__file__).resolve().parent.parent.parent
if _root not in (Path(p).resolve() for p in sys.path):
    sys.path.insert(0, str(_root))

from agent_ext import (
    PydanticAIAgentBase,
    IngestPipeline,
    DocumentInput,
    IngestResult,
    PDFToImages,
    LLMVisionOCREngine,
    PageOCROutput,
)
from agent_ext.run_context import RunContext, Policy
from agent_ext.ingest.extractors import MarkdownDumpExtractor
from agent_ext.ingest.pdf2image_renderer import Pdf2ImageRenderer


# -----------------------------------------------------------------------------
# Minimal in-memory artifact store and logger for the demo
# -----------------------------------------------------------------------------
class InMemoryArtifactStore:
    def __init__(self) -> None:
        self._bytes_store: Dict[str, bytes] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def put_bytes(self, content: bytes, *, metadata: Dict[str, Any]) -> str:
        aid = str(uuid.uuid4())
        self._bytes_store[aid] = content
        self._metadata[aid] = metadata
        return aid

    def get_bytes(self, artifact_id: str) -> bytes:
        return self._bytes_store[artifact_id]

    def put_json(self, obj: Dict[str, Any], *, metadata: Dict[str, Any]) -> str:
        import json
        aid = str(uuid.uuid4())
        self._bytes_store[aid] = json.dumps(obj).encode("utf-8")
        self._metadata[aid] = metadata
        return aid

    def get_json(self, artifact_id: str) -> Dict[str, Any]:
        import json
        return json.loads(self._bytes_store[artifact_id].decode("utf-8"))


class PrintLogger:
    def info(self, msg: str, **kwargs: Any) -> None:
        print(f"[INFO] {msg}", kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        print(f"[WARN] {msg}", kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        print(f"[ERROR] {msg}", kwargs)


class NoopCache:
    def get(self, key: str) -> Any:
        return None

    def set(self, key: str, value: Any, ttl_s: int | None = None) -> None:
        pass


# -----------------------------------------------------------------------------
# OCR agent and pipeline
# -----------------------------------------------------------------------------
class OCRAgent(PydanticAIAgentBase[PageOCROutput]):
    def __init__(self) -> None:
        super().__init__(
            "openai:gpt-4o",
            output_type=PageOCROutput,
            instructions=(
                "You are an OCR expert. Extract text and structure from the document image. "
                "Return file_type (e.g. invoice, letter, form), file_content_md (full content in Markdown), "
                "and file_elements (list of element_type and element_content for tables, paragraphs, etc.)."
            ),
        )


def main() -> None:
    pdf_path = os.environ.get("OCR_DEMO_PDF")
    if not pdf_path or not Path(pdf_path).exists():
        print("Set OCR_DEMO_PDF to a PDF path. Example: OCR_DEMO_PDF=./sample.pdf uv run python -m agent_ext.examples.ocr_with_agent_demo")
        return

    artifacts = InMemoryArtifactStore()
    artifact_id = "doc-1"
    # Demo: seed store with PDF bytes under a known id (real use: put_bytes and use returned id)
    artifacts._bytes_store[artifact_id] = Path(pdf_path).read_bytes()
    artifacts._metadata[artifact_id] = {"source": pdf_path}

    policy = Policy()
    ctx = RunContext(
        case_id="demo",
        session_id="ocr-session",
        user_id="demo-user",
        policy=policy,
        cache=NoopCache(),
        logger=PrintLogger(),
        artifacts=artifacts,
    )

    ocr_agent = OCRAgent()
    prompt = "Perform OCR on this document page. Return structured output: file_type, file_content_md, file_elements."
    ocr_engine = LLMVisionOCREngine(ocr_agent, prompt, media_type="image/png")
    pdf_to_images = PDFToImages(Pdf2ImageRenderer(), dpi=200)
    pipeline = IngestPipeline(
        pdf_to_images=pdf_to_images,
        ocr_engine=ocr_engine,
        extractor=MarkdownDumpExtractor(),
        validator=None,
    )

    doc = DocumentInput(artifact_id=artifact_id)
    result: IngestResult = pipeline.run(ctx, doc)

    print("Pages:", len(result.ocr_pages))
    for i, page in enumerate(result.ocr_pages[:2]):
        text_preview = (page.full_text or "")[:200].replace("\n", " ")
        print(f"  Page {i}: {text_preview}...")
    if len(result.ocr_pages) > 2:
        print("  ...")
    print("Evidence chunks:", len(result.evidence_chunks))


if __name__ == "__main__":
    main()
