from __future__ import annotations

# Ensure root package is importable when run from repo root (e.g. uv run python main.py)
def _ensure_root_importable() -> None:
    import sys
    from pathlib import Path
    _root = Path(__file__).resolve().parent.parent
    _parent = _root.parent
    if _parent not in (Path(p).resolve() for p in sys.path):
        sys.path.insert(0, str(_parent))


_ensure_root_importable()

# ---------------------------------------------------------------------------
# Lightweight, always-needed imports (fast: ~10ms total)
# ---------------------------------------------------------------------------
from .run_context import RunContext, ToolCall, ToolResult
from .hooks.base import Hook, BlockedToolCall, BlockedPrompt
from .hooks.builtins import AuditHook, PolicyHook, ContentFilterHook, ContentFilterFn, make_blocklist_filter
from .hooks.chain import HookChain
from .evidence.models import Citation, Provenance, Evidence
from .skills.models import SkillSpec, LoadedSkill
from .skills.registry import SkillRegistry
from .backends.local_fs import LocalFilesystemBackend
from .backends.sandbox_exec import LocalSubprocessExecBackend
from .memory.summarize import SummarizingMemory
from .memory.window import SlidingWindowMemory
from .todo.models import Task, TaskCreate, TaskPatch, TaskQuery, TaskStatus
from .todo.store_base import TaskStore
from .todo.store_memory import InMemoryTaskStore
from .todo.events import TaskEvent, TaskEventBus, InProcessEventBus, WebhookEventBus
from .todo.toolset import TodoToolset
from .export.models import ExportResult, ExportRequest
from .export.base import Exporter

# ---------------------------------------------------------------------------
# Heavy imports deferred via __getattr__ (pydantic-ai ~0.5s, exporters, etc.)
# These are only loaded when explicitly accessed by name.
# ---------------------------------------------------------------------------

__all__ = [
    "RunContext", "ToolCall", "ToolResult",
    "Hook", "BlockedToolCall", "BlockedPrompt",
    "AuditHook", "PolicyHook", "ContentFilterHook", "ContentFilterFn", "make_blocklist_filter",
    "HookChain",
    "Citation", "Provenance", "Evidence",
    "SkillSpec", "LoadedSkill",
    "SkillRegistry",
    "LocalFilesystemBackend", "LocalSubprocessExecBackend",
    "SummarizingMemory", "SlidingWindowMemory",
    "Subagent", "SubagentResult",
    "SubagentOrchestrator", "SubagentRegistry",
    "RLMPolicy", "run_restricted_python",
    "DocumentInput", "IngestResult", "PageImage", "OCRPage", "OCRSpan", "PageOCROutput", "PageOCRElement",
    "PDFToImages", "OCREngine", "PageExtractor",
    "OCRValidator", "OCRValidationPolicy", "ValidationEvidenceEmitter",
    "IngestPipeline", "OCRRetryAction", "MultiExtractor",
    "Task", "TaskCreate", "TaskPatch", "TaskQuery", "TaskStatus",
    "TaskStore", "InMemoryTaskStore", "PostgresTaskStore",
    "TaskEvent", "TaskEventBus", "InProcessEventBus", "WebhookEventBus",
    "TodoToolset",
    "ExportResult", "ExportRequest",
    "Exporter", "HtmlExporter", "DocxExporter", "PdfExporter", "PptxExporter",
    "LLMVisionOCREngine",
    "PydanticAIAgentBase",
]

# Lazy-loaded module cache
_lazy_cache: dict[str, object] = {}

# Map of name → (module_path, attr_name) for heavy imports
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Subagents (light, but keeps pattern consistent)
    "Subagent": ("agent_ext.subagents.base", "Subagent"),
    "SubagentResult": ("agent_ext.subagents.base", "SubagentResult"),
    "SubagentOrchestrator": ("agent_ext.subagents.orchestrator", "SubagentOrchestrator"),
    "SubagentRegistry": ("agent_ext.subagents.registry", "SubagentRegistry"),
    # RLM
    "RLMPolicy": ("agent_ext.rlm.policies", "RLMPolicy"),
    "run_restricted_python": ("agent_ext.rlm.python_runner", "run_restricted_python"),
    # Ingest (pulls in pdf libs)
    "DocumentInput": ("agent_ext.ingest.models", "DocumentInput"),
    "IngestResult": ("agent_ext.ingest.models", "IngestResult"),
    "PageImage": ("agent_ext.ingest.models", "PageImage"),
    "OCRPage": ("agent_ext.ingest.models", "OCRPage"),
    "OCRSpan": ("agent_ext.ingest.models", "OCRSpan"),
    "PageOCROutput": ("agent_ext.ingest.models", "PageOCROutput"),
    "PageOCRElement": ("agent_ext.ingest.models", "PageOCRElement"),
    "PDFToImages": ("agent_ext.ingest.pdf_to_images", "PDFToImages"),
    "OCREngine": ("agent_ext.ingest.ocr_engines", "OCREngine"),
    "PageExtractor": ("agent_ext.ingest.extractors", "PageExtractor"),
    "OCRValidator": ("agent_ext.ingest.validation", "OCRValidator"),
    "OCRValidationPolicy": ("agent_ext.ingest.validation", "OCRValidationPolicy"),
    "ValidationEvidenceEmitter": ("agent_ext.ingest.validation_evidence", "ValidationEvidenceEmitter"),
    "IngestPipeline": ("agent_ext.ingest.pipeline", "IngestPipeline"),
    "OCRRetryAction": ("agent_ext.ingest.retry_planner", "OCRRetryAction"),
    "MultiExtractor": ("agent_ext.ingest.multi_extractor", "MultiExtractor"),
    # Exporters (pull in reportlab, docx, pptx)
    "HtmlExporter": ("agent_ext.export.html_writer", "HtmlExporter"),
    "DocxExporter": ("agent_ext.export.docx_writer", "DocxExporter"),
    "PdfExporter": ("agent_ext.export.pdf_writer", "PdfExporter"),
    "PptxExporter": ("agent_ext.export.pptx_writer", "PptxExporter"),
    # Postgres task store (pulls asyncpg)
    "PostgresTaskStore": ("agent_ext.todo.store_postgres", "PostgresTaskStore"),
    # Pydantic-AI agent (pulls pydantic-ai ~0.5s)
    "PydanticAIAgentBase": ("agent_ext.agent.base", "PydanticAIAgentBase"),
    # LLM Vision OCR (pulls pydantic-ai)
    "LLMVisionOCREngine": ("agent_ext.ingest.llm_ocr_engine", "LLMVisionOCREngine"),
}


def __getattr__(name: str) -> object:
    if name in _lazy_cache:
        return _lazy_cache[name]
    if name in _LAZY_IMPORTS:
        mod_path, attr = _LAZY_IMPORTS[name]
        import importlib
        try:
            mod = importlib.import_module(mod_path)
            obj = getattr(mod, attr)
            _lazy_cache[name] = obj
            return obj
        except (ImportError, AttributeError):
            # Optional dependency not installed — return None for back-compat
            _lazy_cache[name] = None  # type: ignore[assignment]
            return None
    raise AttributeError(f"module 'agent_ext' has no attribute {name!r}")


__version__ = "0.1.0"
