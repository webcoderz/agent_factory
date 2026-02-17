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
from .subagents.base import Subagent, SubagentResult
from .subagents.orchestrator import SubagentOrchestrator
from .subagents.registry import SubagentRegistry
from .rlm.policies import RLMPolicy
from .rlm.python_runner import run_restricted_python
from .ingest.models import DocumentInput, IngestResult, PageImage, OCRPage, OCRSpan
from .ingest.pdf_to_images import PDFToImages
from .ingest.ocr_engines import OCREngine
from .ingest.extractors import PageExtractor
from .ingest.validation import OCRValidator, OCRValidationPolicy
from .ingest.validation_evidence import ValidationEvidenceEmitter
from .ingest.pipeline import IngestPipeline
from .ingest.retry_planner import OCRRetryAction
from .ingest.multi_extractor import MultiExtractor
from .agent.base import PydanticAIAgentBase
from .todo.models import Task, TaskCreate, TaskPatch, TaskQuery, TaskStatus
from .todo.store_base import TaskStore
from .todo.store_memory import InMemoryTaskStore
from .todo.store_postgres import PostgresTaskStore
from .todo.events import TaskEvent, TaskEventBus, InProcessEventBus, WebhookEventBus
from .todo.toolset import TodoToolset

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
    "DocumentInput", "IngestResult", "PageImage", "OCRPage", "OCRSpan",
    "PDFToImages", "OCREngine", "PageExtractor",
    "OCRValidator", "OCRValidationPolicy", "ValidationEvidenceEmitter",
    "IngestPipeline", "OCRRetryAction", "MultiExtractor",
    "PydanticAIAgentBase",
    "Task", "TaskCreate", "TaskPatch", "TaskQuery", "TaskStatus",
    "TaskStore", "InMemoryTaskStore", "PostgresTaskStore",
    "TaskEvent", "TaskEventBus", "InProcessEventBus", "WebhookEventBus",
    "TodoToolset",
]