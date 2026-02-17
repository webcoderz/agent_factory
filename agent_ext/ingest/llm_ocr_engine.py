"""
LLM/Vision OCR engine: use a pydantic-ai agent (e.g. PydanticAIAgentBase) to perform
OCR per page by sending page images and receiving structured or plain text.
Pattern aligned with vision OCR (e.g. PDF → images → LLM per page → structured output);
see README §10 and pydantic-ai OCR examples for the idea.
"""
from __future__ import annotations

from typing import Any, List, Optional, Protocol

from agent_ext.run_context import RunContext
from agent_ext.ingest.models import PageImage, OCRPage

try:
    from pydantic_ai import BinaryContent
except ImportError:
    BinaryContent = None  # type: ignore[misc, assignment]


class _AgentLike(Protocol):
    """Agent that accepts run_sync(ctx, message) with message as list (e.g. prompt + BinaryContent)."""
    def run_sync(self, ctx: RunContext, message: Any, **kwargs: Any) -> Any: ...


def _text_from_output(output: Any) -> str:
    """Extract full text from agent output (structured model or string)."""
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    for attr in ("file_content_md", "content_md", "full_text", "result", "text"):
        if hasattr(output, attr):
            val = getattr(output, attr)
            if isinstance(val, str):
                return val
    return str(output)


class LLMVisionOCREngine:
    """
    OCREngine that runs a vision-capable agent (e.g. PydanticAIAgentBase) per page image.
    Sends each page as image (BinaryContent) + prompt; maps agent output to OCRPage.
    Use with our wrapped agent and a structured output type (e.g. PageOCROutput) for
    schema-validated OCR; see README §10 and pydantic-ai OCR examples for the pattern.
    """
    name = "llm_vision"

    def __init__(
        self,
        agent: _AgentLike,
        prompt: str,
        *,
        media_type: str = "image/png",
    ) -> None:
        if BinaryContent is None:
            raise ImportError("LLMVisionOCREngine requires pydantic-ai (BinaryContent).")
        self.agent = agent
        self.prompt = prompt
        self.media_type = media_type

    def ocr_pages(self, ctx: RunContext, pages: List[PageImage]) -> List[OCRPage]:
        out: List[OCRPage] = []
        for page in pages:
            image_bytes = ctx.artifacts.get_bytes(page.image_artifact_id)
            message = [
                self.prompt,
                BinaryContent(data=image_bytes, media_type=self.media_type),
            ]
            result = self.agent.run_sync(ctx, message)
            output = getattr(result, "data", None) or getattr(result, "output", result)
            full_text = _text_from_output(output)
            metadata: dict = {}
            if output is not None and not isinstance(output, str) and hasattr(output, "model_dump"):
                metadata["structured"] = output.model_dump()
            elif output is not None and not isinstance(output, str):
                metadata["raw"] = str(output)
            out.append(
                OCRPage(
                    page_index=page.page_index,
                    full_text=full_text,
                    engine=self.name,
                    metadata=metadata,
                )
            )
        return out
