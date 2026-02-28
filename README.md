# agent_patterns

Modular, pluggable subsystems for building AI agents with [pydantic-ai](https://ai.pydantic.dev): **middleware** (async hooks, cost tracking, parallel validators, permissions), **subagents** (message bus, task delegation), **RLM** (sandboxed code execution), **backends** (filesystem, permissions, hashline editing), **memory** (token-aware, safe cutoff), **skills** (registry composition), **database** (SQL queries), **todo** (task management), **evidence**, **document ingest**, **deep research**, and more.

Use one pattern or combine several — everything plugs into pydantic-ai's `Agent` via `FunctionToolset`.

---

## AgentPatterns — Batteries-Included Agent

`AgentPatterns` inherits from pydantic-ai's `Agent` and auto-wires all subsystems. Pass toolset names as strings and get a fully-equipped agent:

```python
from agent_ext.agent import AgentPatterns

# Coding assistant with filesystem + task management
agent = AgentPatterns(
    "openai:gpt-4o",
    instructions="You are a helpful coding assistant.",
    toolsets=["console", "todo"],
)
result = await agent.run("List all Python files and create a review task for each")
```

### Factory Methods

```python
# Console agent (ls, read, write, edit, grep, execute)
agent = AgentPatterns.with_console("openai:gpt-4o")

# Data analysis agent (sandboxed Python with sub-model delegation)
agent = AgentPatterns.with_rlm("openai:gpt-4o", sub_model="openai:gpt-4o-mini")

# Database agent (SQL queries with read-only protection)
agent = AgentPatterns.with_database("openai:gpt-4o")

# Kitchen sink — everything
agent = AgentPatterns.with_all("openai:gpt-4o")
```

### With Memory

```python
from agent_ext.memory import SlidingWindowMemory

agent = AgentPatterns(
    "openai:gpt-4o",
    toolsets=["console", "rlm"],
    memory=SlidingWindowMemory(max_tokens=100_000),
)
```

### Composing Toolsets

```python
from agent_ext.rlm import create_rlm_toolset
from agent_ext.database import create_database_toolset
from agent_ext.backends.console import create_console_toolset

# Mix and match — pass FunctionToolset instances directly
agent = AgentPatterns(
    "openai:gpt-4o",
    toolsets=[
        create_console_toolset(),
        create_rlm_toolset(code_timeout=120, sub_model="openai:gpt-4o-mini"),
        create_database_toolset(),
    ],
)
```

### Available Toolsets

| Name | Tools | Use Case |
|------|-------|----------|
| `"console"` | ls, read_file, write_file, edit_file, grep, glob_files, execute | File operations + shell |
| `"rlm"` | execute_code | Sandboxed Python for data analysis |
| `"database"` | list_tables, describe_table, sample_table, query | SQL database access |
| `"subagents"` | task, check_task, list_active_tasks, cancel_task | Multi-agent delegation |
| `"todo"` | create_task, list_tasks, update_task, complete_task | Task management |

---

## Subsystem Highlights

### Middleware (hooks/)
Async lifecycle hooks with 7 hook points, scoped context, cost tracking, parallel execution, and ALLOW/DENY/ASK permissions.

```python
from agent_ext.hooks import (
    MiddlewareChain, AuditHook, PolicyHook,
    CostTrackingMiddleware, ParallelMiddleware,
    AsyncGuardrailMiddleware, GuardrailTiming,
    make_blocklist_filter, ContentFilterHook,
)

# Cost tracking with budget enforcement
cost_mw = CostTrackingMiddleware(
    model_name="openai:gpt-4o",
    budget_limit_usd=5.0,
    on_cost_update=lambda info: print(f"Cost: ${info.total_cost_usd:.4f}"),
)

# Parallel validators (run concurrently, all must pass)
parallel = ParallelMiddleware([
    PIIDetector(), ProfanityFilter(), InjectionGuard(),
])

# Async guardrail (runs alongside LLM, cancels on failure)
guardrail = AsyncGuardrailMiddleware(
    PolicyCheck(), timing=GuardrailTiming.CONCURRENT,
)

chain = MiddlewareChain([AuditHook(), cost_mw, parallel, guardrail])
```

### Backends (backends/)
File storage with permission presets, in-memory testing backend, and hashline editing.

```python
from agent_ext.backends import (
    StateBackend, LocalFilesystemBackend,
    PermissionChecker, READONLY_RULESET,
    format_hashline_output, apply_hashline_edit,
)

# In-memory backend for testing
backend = StateBackend()
backend.write_text("src/app.py", "def hello(): pass")

# Permission checking
checker = PermissionChecker(READONLY_RULESET)
assert checker.is_allowed("read", "/src/app.py")  # True
assert not checker.is_allowed("write", "/src/app.py")  # False

# Hashline editing (precise, low-token edits)
tagged = format_hashline_output("line one\nline two\n")
# 1:a3|line one
# 2:f1|line two
```

### RLM (rlm/)
Sandboxed REPL for large-context analysis with sub-model delegation.

```python
from agent_ext.rlm import REPLEnvironment, RLMConfig

repl = REPLEnvironment(
    context=massive_document,
    config=RLMConfig(sub_model="openai:gpt-4o-mini"),
)

result = repl.execute("""
lines = context.split('\\n')
relevant = [l for l in lines if 'revenue' in l.lower()]
analysis = llm_query(f"Summarize: {relevant[:5]}")
print(analysis)
""")
```

### Database (database/)
SQL capabilities with security controls.

```python
from agent_ext.database import SQLiteDatabase, DatabaseConfig

async with SQLiteDatabase("data.db", DatabaseConfig(read_only=True)) as db:
    tables = await db.list_tables()
    result = await db.execute_query("SELECT * FROM users WHERE age > 25")
```

### Subagents (subagents/)
Multi-agent orchestration with message bus and task management.

```python
from agent_ext.subagents import (
    DynamicAgentRegistry, InMemoryMessageBus,
    SubAgentConfig, decide_execution_mode,
)

registry = DynamicAgentRegistry(max_agents=10)
bus = InMemoryMessageBus()
response = await bus.ask("parent", "worker", "Analyze this data", task_id="t1")
```

### Memory (memory/)
Token-aware sliding window that never splits tool call/response pairs.

```python
from agent_ext.memory import SlidingWindowMemory

memory = SlidingWindowMemory(
    max_tokens=100_000,
    trigger_tokens=80_000,
)
```

### Skills (skills/)
Progressive-disclosure instruction packs with registry composition.

```python
from agent_ext.skills import create_skill, CombinedRegistry, FilteredRegistry

skill = create_skill(
    id="code_review", name="Code Review",
    description="Review code for quality",
    body="# Code Review\n\nCheck for...",
    tags=["code"],
)
```

---

## Setup

**Optional dependency (pydantic-ai):** The core package does **not** depend on `pydantic-ai`, so you can use agent_patterns (hooks, todo, ingest, evidence, etc.) without pulling in pydantic-ai or its transitive deps (e.g. Starlette). If your app **already has** pydantic-ai installed, **PydanticAIAgentBase** and **LLMVisionOCREngine** will use your version when you import them. If you need the agent/vision OCR and don’t have pydantic-ai yet, install the extra:

```bash
pip install agent-patterns[agent]
# or
uv add "agent-patterns[agent]"
```

Put the **parent** of this repo on `PYTHONPATH`:

```bash
# From the directory that contains agent_patterns (e.g. monorepo root):
export PYTHONPATH="$(pwd):$PYTHONPATH"
uv run python -c "from agent_ext import PydanticAIAgentBase, RunContext; print('OK')"
```

From inside `agent_patterns`:

```bash
export PYTHONPATH="$(cd .. && pwd):$PYTHONPATH"
uv run python your_script.py
```

---

## 1. RunContext (the core)

Every pattern expects a **RunContext**: one object that carries identity, policy, logging, storage, and optional subsystems for the run.

```python
from agent_patterns.run_context import RunContext, Policy

# You implement these protocols (or use your own adapters):
# - Cache (get/set)
# - Logger (info/warning/error)
# - ArtifactStore (put_bytes, get_bytes, put_json, get_json)

ctx = RunContext(
    case_id="case-1",
    session_id="sess-1",
    user_id="user-1",
    policy=Policy(allow_tools=True, allow_exec=False, allow_fs_write=False),
    cache=my_cache,
    logger=my_logger,
    artifacts=my_artifact_store,
    trace_id="optional-trace-id",
)

# Optional: inject subsystems (set by your composition root)
ctx.skills = skill_registry_or_loader
ctx.backends = {"fs": fs_backend, "exec": exec_backend}
ctx.subagents = subagent_registry
ctx.memory = memory_manager
ctx.rlm = rlm_policy
ctx.todo = todo_toolset  # TodoToolset(store, events=...) for task CRUD
```

- **Policy**: `allow_tools`, `allow_exec`, `allow_fs_write`, `max_tool_calls`, `max_runtime_s`, `redaction_level`. Use with **PolicyHook** to enforce at runtime.
- **ArtifactStore**: store blobs and JSON for auditability; ingest and research write artifacts keyed by `case_id` / `session_id`.

---

## 2. Hooks (audit, policy, custom)

**Hooks** run at defined points around a run: before/after run, before/after model request/response, before/after tool call/result, and on error. Implement the `Hook` protocol and chain them.

```python
from agent_ext import HookChain, AuditHook, PolicyHook, ContentFilterHook, BlockedToolCall, BlockedPrompt, make_blocklist_filter

# Built-in: logging and timing
audit = AuditHook()

# Built-in: enforce ctx.policy (e.g. block tools if allow_tools=False)
policy = PolicyHook()

# Block dangerous prompts before they reach the LLM (raises BlockedPrompt on match)
DANGEROUS = ["ignore previous", "jailbreak", "disregard instructions"]  # your blocklist
content_filter = ContentFilterHook(filter_fn=make_blocklist_filter(DANGEROUS, reason="Prompt blocked by policy"))
# Or custom filter that can raise BlockedPrompt or redact:
# def my_filter(ctx, payload, phase): ...
# content_filter = ContentFilterHook(filter_fn=my_filter)

chain = HookChain([audit, content_filter, policy])

# In your agent loop (catch BlockedPrompt so dangerous prompts never reach the LLM):
chain.before_run(ctx)
try:
    request = chain.before_model_request(ctx, request)
    response = get_model_response(request)
    response = chain.after_model_response(ctx, response)
    # ... tool calls: chain.before_tool_call(ctx, call), chain.after_tool_result(ctx, result)
    outcome = ...
except BlockedPrompt as e:
    outcome = "I can't process that request."  # or your safe fallback; no LLM call
except Exception as e:
    outcome = chain.on_error(ctx, e)
chain.after_run(ctx, outcome)
```

- **BlockedToolCall**: raised by PolicyHook when a tool is disallowed; handle it in your runner.
- **BlockedPrompt**: raise from a content filter to **block the request before it reaches the LLM**. The runner should catch it and not call the model (e.g. return a safe message). Use **make_blocklist_filter(patterns, reason=...)** to block requests whose text matches any pattern (substring or regex).
- **ContentFilterHook**: runs your `filter_fn` on every **before_model_request** (so blocking works always) and on **after_model_response** when `ctx.policy.redaction_level` is not `"none"`. Filter can return modified payload or raise **BlockedPrompt** to block the request before it reaches the LLM. Use for blocklists, PII redaction, or moderation APIs.
- **Custom hooks**: implement `Hook` (e.g. rate limiting, metrics) and prepend/append to the chain.

---

## 3. Evidence and citations

**Evidence** is the common shape for “something produced by a step”: text, entities, findings, doc extracts, etc. It carries **citations** (source_id, locator, quote) and **provenance** (produced_by, artifact_ids).

```python
from agent_ext import Evidence, Citation, Provenance

ev = Evidence(
    kind="finding",
    content="The report states X.",
    citations=[Citation(source_id="doc-1", locator="page:3", quote="...", confidence=0.9)],
    provenance=Provenance(produced_by="ingest_pipeline", artifact_ids=["doc-1"]),
    confidence=0.8,
    tags=["pii:redacted"],
)
```

Used by: **ingest** (extractors produce Evidence), **research** (tasks produce Evidence, synth consumes it), and any agent that needs to pass structured findings with sources.

---

## 4. Skills (discovery and loading)

**Skills** are discovered from directories (`skills/<id>/SKILL.md`) and loaded as markdown. The registry builds a **SkillSpec** per folder; the loader reads the body and returns a **LoadedSkill**.

```python
from agent_ext import SkillRegistry
from agent_ext.skills.loader import SkillLoader

registry = SkillRegistry(roots=["skills", "vendor/skills"])
registry.discover()
for spec in registry.list():
    print(spec.id, spec.name)

loader = SkillLoader(max_bytes=256_000)
loaded = loader.load(registry.get("my_skill"))
# loaded.body_markdown, loaded.spec, loaded.body_hash
```

- Attach `registry` or a skill selector to **ctx.skills** so agents/tools can resolve skills by id.
- Use **SkillSpec** / **LoadedSkill** to inject skill text into prompts or tool descriptions.

---

## 5. Backends (filesystem and exec)

**Backends** give the run sandboxed filesystem and optional subprocess execution. Attach them to **ctx.backends** so tools (or ingest) can use them under policy.

```python
from agent_ext import LocalFilesystemBackend, LocalSubprocessExecBackend

fs = LocalFilesystemBackend(root="/tmp/sandbox", allow_write=ctx.policy.allow_fs_write)
exec_backend = LocalSubprocessExecBackend()  # runs in subprocess, respects timeout

ctx.backends = {"fs": fs, "exec": exec_backend}

# In a tool or pipeline:
backend = ctx.backends["fs"]
content = backend.read_text("path/relative/to/root")
# exec_backend.run(["python", "-c", "..."], timeout_s=30)
```

- **FilesystemBackend**: read_text, write_text, list, glob (all scoped to root).
- **ExecBackend**: run(cmd, cwd=..., env=..., timeout_s=...). Use only when **Policy.allow_exec** is True.

---

## 6. Memory (conversation shape and checkpoint)

**Memory** shapes the list of messages before each model request and checkpoints after each run. Two implementations: **SlidingWindowMemory** (last N) and **SummarizingMemory** (dossier + last N).

```python
from agent_ext import SlidingWindowMemory, SummarizingMemory, SummarizeConfig
from agent_ext.memory.summarize import Dossier

# Option A: sliding window
memory = SlidingWindowMemory(max_messages=20)

# Option B: summarizing (needs a summarize_fn that returns/updates a Dossier)
def my_summarize(ctx, text: str, base: Dossier) -> Dossier:
    base.summary = f"Summary of: {text[:1000]}..."
    return base

memory = SummarizingMemory(
    cfg=SummarizeConfig(max_messages=80, keep_last_n=30),
    summarize_fn=my_summarize,
)
if hasattr(memory, "bind_ctx"):
    memory.bind_ctx(ctx)
```

- **MemoryManager** protocol: `shape_messages(messages) -> messages`, `checkpoint(messages, outcome=...)`.
- Attach to **ctx.memory** and/or pass into **PydanticAIAgentBase(memory=...)** so the pydantic-ai history_processor and post-run checkpoint use it.

---

## 7. Subagents (delegate to specialists)

**Subagents** are async callables that take `input` and `metadata` and return **SubagentResult**. Register them and run via **SubagentOrchestrator**.

```python
from agent_ext import Subagent, SubagentResult, SubagentRegistry, SubagentOrchestrator

class MySpecialist(Subagent):
    name = "kg_proposer"
    async def run(self, *, input: Any, metadata: dict) -> SubagentResult:
        # e.g. call another agent or service
        return SubagentResult(ok=True, output={"schema": "..."}, metadata={})

registry = SubagentRegistry()
registry.register(MySpecialist())
orchestrator = SubagentOrchestrator(registry)

ctx.subagents = registry

# Run several in parallel
results = await orchestrator.run_many(
    ctx,
    [
        ("kg_proposer", evidence_list, {"source": "ingest"}),
        ("other_agent", query, {}),
    ],
    timeout_s=60,
)
```

- Use from a **main agent tool**: resolve `ctx.subagents.get(name)` and `await agent.run(...)`, or call **orchestrator.run_many** with a list of (name, input, metadata).

---

## 8. RLM (restricted execution)

**RLM** provides a restricted Python runner and policy for executing user or model-generated code safely (e.g. for reasoning or tool-like execution).

```python
from agent_ext import RLMPolicy, run_restricted_python

policy = RLMPolicy()  # configure allowed builtins, timeouts, etc.
ctx.rlm = policy

# Run untrusted code in a restricted environment
result = run_restricted_python("1 + 1", policy=policy)
```

- Use when **Policy.allow_exec** (or a dedicated RLM flag) is True; wrap in hooks for audit.

---

## 9. Todo (task management)

**Todo** provides planning primitives: tasks with subtasks, dependencies, and multi-tenant scoping (case_id, session_id, user_id). Use **TaskStore** (in-memory or Postgres), optional **TaskEventBus** for task_created / task_updated / task_completed, and **TodoToolset** to expose CRUD to agents or services.

```python
from agent_ext import (
    Task,
    TaskCreate,
    TaskPatch,
    TaskQuery,
    TaskStatus,
    TaskStore,
    InMemoryTaskStore,
    PostgresTaskStore,
    TaskEvent,
    TaskEventBus,
    InProcessEventBus,
    WebhookEventBus,
    TodoToolset,
)

# In-memory store (no deps)
store: TaskStore = InMemoryTaskStore()

# Or Postgres (requires asyncpg)
# store = await PostgresTaskStore.connect("postgresql://...")

# Optional: events (in-process handlers or webhooks)
bus = InProcessEventBus()
bus.on("task_completed", lambda e: print("Done:", e.task.id))

# Or send events to webhooks
# bus = WebhookEventBus(urls=["https://my.app/webhook"], timeout_s=10.0)

toolset = TodoToolset(store, events=bus)

# Create task (e.g. from agent or planner)
t = await toolset.create_task(
    TaskCreate(
        title="Review document",
        description="Check section 3",
        priority=50,
        tags=["review"],
        case_id=ctx.case_id,
        session_id=ctx.session_id,
        user_id=ctx.user_id,
    )
)

# List and filter
tasks = await toolset.list_tasks(TaskQuery(case_id=ctx.case_id, status="pending", limit=20))

# Update (e.g. mark done)
await toolset.update_task(t.id, TaskPatch(status="done"))

# Dependencies and subtasks
await toolset.add_dependency(task_id="B", depends_on_task_id="A")
child = await toolset.add_subtask(parent_id="parent-id", data=TaskCreate(title="Substep 1"))
```

- **Task**: id, title, description, status, priority, parent_id, depends_on, tags, case_id/session_id/user_id, artifact_ids, evidence_ids, meta, created_at, updated_at.
- **TaskStore** protocol: create_task, get_task, list_tasks, update_task, delete_task, add_dependency, add_subtask.
- **PostgresTaskStore** creates table `agent_tasks` and indexes on case_id, session_id, user_id, parent_id, status (requires **asyncpg**).
- Attach **TodoToolset** to **ctx** (e.g. `ctx.todo = toolset`) so agent tools can create/list/update tasks scoped to the run.

### Using Todo in an agent flow

Use **TodoToolset** with **PydanticAIAgentBase**: set `ctx.todo = toolset` before runs, then in agent tools call `ctx.deps.todo` so the agent can create, list, update, and manage tasks scoped to the current run (case_id, session_id, user_id).

**1. Setup: store, optional events, toolset, attach to context**

```python
from agent_ext import (
    RunContext,
    InMemoryTaskStore,
    InProcessEventBus,
    TodoToolset,
    TaskCreate,
    TaskPatch,
    TaskQuery,
)

store = InMemoryTaskStore()
bus = InProcessEventBus()
toolset = TodoToolset(store, events=bus)

ctx = RunContext(case_id="case-1", session_id="sess-1", user_id="user-1", policy=..., cache=..., logger=..., artifacts=...)
ctx.todo = toolset
```

**2. Define an agent with todo tools (use `ctx.deps` = RunContext, `ctx.deps.todo` = TodoToolset)**

```python
from pydantic import BaseModel, Field
from agent_ext import PydanticAIAgentBase, RunContext
from agent_ext.todo.models import TaskCreate, TaskPatch, TaskQuery
from pydantic_ai import RunContext as PAIRunContext

class PlanOutput(BaseModel):
    summary: str = Field(description="Brief summary of the plan")

class PlannerAgent(PydanticAIAgentBase[PlanOutput]):
    def __init__(self):
        super().__init__(
            "openai:gpt-4o-mini",
            output_type=PlanOutput,
            instructions="You help plan work by creating and updating tasks. Use the task tools to create, list, and update tasks.",
        )

# Tools receive pydantic-ai RunContext; ctx.deps is our RunContext, ctx.deps.todo is the TodoToolset
agent = PlannerAgent()

@agent.tool
async def create_task(
    ctx: PAIRunContext[RunContext],
    title: str,
    description: str = "",
    priority: int = 50,
    tags: str = "",
) -> str:
    """Create a task scoped to the current case/session/user."""
    if not ctx.deps.todo:
        return "Task system not available."
    data = TaskCreate(
        title=title,
        description=description or None,
        priority=priority,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        case_id=ctx.deps.case_id,
        session_id=ctx.deps.session_id,
        user_id=ctx.deps.user_id,
    )
    task = await ctx.deps.todo.create_task(data)
    return f"Created task {task.id}: {task.title}"

@agent.tool
async def list_tasks(
    ctx: PAIRunContext[RunContext],
    status: str = "pending",
    limit: int = 20,
) -> str:
    """List tasks for the current case/session."""
    if not ctx.deps.todo:
        return "Task system not available."
    q = TaskQuery(
        case_id=ctx.deps.case_id,
        session_id=ctx.deps.session_id,
        user_id=ctx.deps.user_id,
        status=status if status in ("pending", "in_progress", "done", "blocked", "canceled", "failed") else None,
        limit=limit,
    )
    tasks = await ctx.deps.todo.list_tasks(q)
    if not tasks:
        return "No tasks found."
    lines = [f"- [{t.id}] {t.title} (status={t.status}, priority={t.priority})" for t in tasks]
    return "\n".join(lines)

@agent.tool
async def update_task_status(
    ctx: PAIRunContext[RunContext],
    task_id: str,
    status: str,
) -> str:
    """Update a task's status (e.g. in_progress, done)."""
    if not ctx.deps.todo:
        return "Task system not available."
    patch = TaskPatch(status=status)
    task = await ctx.deps.todo.update_task(task_id, patch)
    if not task:
        return f"Task {task_id} not found."
    return f"Updated {task.id} to status={task.status}"
```

**3. Run the agent; it can create and manage tasks via the tools**

```python
# User asks for a plan; agent uses create_task / list_tasks / update_task_status
result = agent.run_sync(
    ctx,
    "Create three tasks: (1) Research competitors, (2) Draft outline, (3) Review. Then list pending tasks.",
)
# result.output.summary, and tasks were created/listed via tool calls

# Later: "Mark the first task as in progress"
result2 = agent.run_sync(
    ctx,
    "Set 'Research competitors' to in progress.",
    message_history=result.new_messages(),
)
```

- Always scope **TaskCreate** and **TaskQuery** with `case_id=ctx.deps.case_id`, `session_id=ctx.deps.session_id`, `user_id=ctx.deps.user_id` so tasks belong to the current run.
- Check `ctx.deps.todo` in tools if todo is optional (e.g. return a friendly message when not set).
- For more operations (subtasks, dependencies), add tools that call `ctx.deps.todo.add_subtask(parent_id, TaskCreate(...))` and `ctx.deps.todo.add_dependency(task_id, depends_on_task_id)`.

---

## 10. Document ingest (PDF → OCR → Evidence)

**Ingest** turns documents into **Evidence** with citations: PDF → page images → OCR → validation → extraction.

```python
from agent_ext import (
    RunContext,
    IngestPipeline,
    DocumentInput,
    IngestResult,
    PDFToImages,
    OCREngine,
    PageExtractor,
    OCRValidator,
    OCRValidationPolicy,
    ValidationEvidenceEmitter,
)

# Implement or use provided PDFToImages, OCREngine, PageExtractor
pipeline = IngestPipeline(
    pdf_to_images=pdf_to_images_impl,
    ocr_engine=ocr_engine_impl,
    extractor=extractor_impl,
    validator=OCRValidator(OCRValidationPolicy()),
    validation_evidence_emitter=ValidationEvidenceEmitter(),
    fail_fast_on_validation=True,
)

doc = DocumentInput(artifact_id="doc-123", path="/path/to/file.pdf")
result: IngestResult = pipeline.run(ctx, doc)
# result.ocr_pages, result.evidence_chunks (List[Evidence])
```

- **IngestResult**: doc_artifact_id, page_images, ocr_pages, evidence_chunks. Feed evidence into research or an agent context.
- **MultiExtractor**: combine multiple **PageExtractor**s; **OCRRetryAction** / retry planner for validation failures.

### OCR with the wrapped agent (vision / LLM)

You can run **vision OCR** using our **PydanticAIAgentBase** and ingest pipeline: PDF → page images → one LLM call per page (image + prompt) → structured or plain text per page. This follows the same pattern as the [pydantic-ai OCR examples](https://github.com/vstorm-co/pydantic-ai-examples/tree/main/ocr_parsing) (PDF→images, send image to the model, structured output with validation), but wired to our **RunContext**, **IngestPipeline**, and **LLMVisionOCREngine**.

1. **Structured output model** (optional): use **PageOCROutput** (and **PageOCRElement**) so the agent returns schema-validated OCR per page (`file_type`, `file_content_md`, `file_elements`). Pydantic validates the LLM response; see [pydantic-ai structured OCR](https://github.com/vstorm-co/pydantic-ai-examples/blob/main/ocr_parsing/2_ocr_with_structured_output.py) and [validation](https://github.com/vstorm-co/pydantic-ai-examples/blob/main/ocr_parsing/3_ocr_validation.py) for the idea.

2. **OCR agent**: subclass **PydanticAIAgentBase[PageOCROutput]** (or `str` for plain markdown). Use a vision-capable model (e.g. `openai:gpt-4o`) and instructions that describe the OCR task and output shape.

3. **LLMVisionOCREngine**: wraps your agent; for each page image it sends `[prompt, BinaryContent(image)]` to the agent and maps the result to **OCRPage** (e.g. `full_text` from `file_content_md`). Wire it as the pipeline’s `ocr_engine`.

4. **Pipeline**: **PDFToImages** (e.g. with **Pdf2ImageRenderer** from `agent_ext.ingest.pdf2image_renderer`) → **LLMVisionOCREngine** → validator (optional) → **PageExtractor** (e.g. **MarkdownDumpExtractor**). Run with **RunContext** and **DocumentInput**; get **IngestResult.ocr_pages** and **evidence_chunks**.

```python
from agent_ext import (
    RunContext,
    PydanticAIAgentBase,
    IngestPipeline,
    DocumentInput,
    IngestResult,
    PDFToImages,
    LLMVisionOCREngine,
    PageOCROutput,
)
from agent_ext.ingest.extractors import MarkdownDumpExtractor
from agent_ext.ingest.pdf2image_renderer import Pdf2ImageRenderer

# 1) Structured output model (optional; use str for plain text)
# PageOCROutput has file_type, file_content_md, file_elements (list of PageOCRElement)

# 2) OCR agent: vision model + instructions + output_type
class OCRAgent(PydanticAIAgentBase[PageOCROutput]):
    def __init__(self):
        super().__init__(
            "openai:gpt-4o",
            output_type=PageOCROutput,
            instructions="You are an OCR expert. Extract text and structure from the document image. Return file_type, file_content_md (Markdown), and file_elements (element_type, element_content).",
        )

ocr_agent = OCRAgent()
prompt = "Perform OCR on this document page. Return structured output: file_type, file_content_md, file_elements."

# 3) Vision OCR engine: one agent run per page image
ocr_engine = LLMVisionOCREngine(ocr_agent, prompt, media_type="image/png")

# 4) Pipeline: PDF → images (Pdf2ImageRenderer) → LLM OCR → evidence
pdf_to_images = PDFToImages(Pdf2ImageRenderer(), dpi=200)
pipeline = IngestPipeline(
    pdf_to_images=pdf_to_images,
    ocr_engine=ocr_engine,
    extractor=MarkdownDumpExtractor(),
    validator=None,
)

ctx = RunContext(...)  # case_id, policy, cache, logger, artifacts (required for PDFToImages + engine)
doc = DocumentInput(artifact_id="doc-1", path="/path/to/doc.pdf")
result: IngestResult = pipeline.run(ctx, doc)
# result.ocr_pages[i].full_text, result.ocr_pages[i].metadata.get("structured"), result.evidence_chunks
```

- **Artifacts**: **PDFToImages** and **LLMVisionOCREngine** use **ctx.artifacts** (get_bytes/put_bytes for page images). Ensure the document is stored as an artifact or that you load it and put it before calling **pipeline.run**.
- **Concurrency**: the pipeline runs pages sequentially; for parallel page calls you could extend **LLMVisionOCREngine** or run multiple pipelines in parallel with a shared context.
- A minimal runnable demo is in **examples/ocr_with_agent_demo.py** (requires configured RunContext and artifact store).

---

## 11. Deep research (plan → execute → gaps → synthesize)

**Research** runs a loop: plan tasks → execute (with kind-specific handlers) → collect evidence → gap analysis → add tasks → synthesize outcome.

```python
from agent_ext.research import DeepResearchController
from agent_ext.research.planner import default_plan
from agent_ext.research.executor import ResearchExecutor
from agent_ext.research.handlers_default import handle_analyze, handle_synthesize  # and others
from agent_ext.research.models import ResearchBudget

planner = ResearchPlanner(plan_fn=default_plan)  # or your LLM planner
handlers = {"analyze": handle_analyze, "synthesize": handle_synthesize}  # add search, ingest_document, etc.
executor = ResearchExecutor(handlers=handlers)

controller = DeepResearchController(
    planner=planner,
    executor=executor,
    budget=ResearchBudget(max_steps=40, max_runtime_s=180),
    enable_gap_analysis=True,
    max_gap_iterations=3,
    persist_snapshots=True,
)

outcome = await controller.run(ctx, question="What is the impact of X?")
# outcome.answer, outcome.claims, outcome.plan, outcome.steps_taken
```

- **ResearchLedger** tracks plan, tasks, evidence, events; **EvidenceGraph** for structure; **propose_gaps** to add tasks from gaps; **build_outcome** to synthesize claims and answer.
- Handlers receive **RunContext**, **ResearchTask**, **ResearchLedger** and return **Sequence[Evidence]**. Wire ingest output or subagents into handlers (e.g. `ingest_document` handler runs **IngestPipeline**).

---

## 12. Pydantic-AI agent (base + memory + tools)

**PydanticAIAgentBase** is a pydantic-ai **Agent** that uses **RunContext** as deps, optional **memory** (history_processor + checkpoint), and safe tool-call truncation.

```python
from pydantic import BaseModel, Field
from agent_ext import PydanticAIAgentBase, RunContext, SlidingWindowMemory
from pydantic_ai import RunContext as PAIRunContext

class MyOutput(BaseModel):
    answer: str = Field(description="The agent's answer")

memory = SlidingWindowMemory(max_messages=20)

class MyAgent(PydanticAIAgentBase[MyOutput]):
    def __init__(self):
        super().__init__(
            "openai:gpt-4o",
            output_type=MyOutput,
            instructions="You are a helpful assistant.",
            memory=memory,
        )

@my_agent.tool
async def lookup(ctx: PAIRunContext[RunContext], query: str) -> str:
    ctx.deps.logger.info("tool.lookup", query=query)
    return "..."

agent = MyAgent()
result1 = agent.run_sync(ctx, "What is 2+2?")
result2 = agent.run_sync(ctx, "And in hex?", message_history=result1.new_messages())
```

- **Tool calls and safe truncation**: history is truncated so **tool call pairs** are never split; use **message_kind**, **has_tool_calls**, **has_tool_returns**, **safe_truncate_messages** from **agent_ext.agent** when inspecting or trimming messages.
- **Memory**: with `memory=` set, a history_processor runs **shape_messages** and **checkpoint** runs after each **run_sync** / **run**.
- **Todo in the agent**: set `ctx.todo = TodoToolset(store, events=...)` and in tools use `ctx.deps.todo` to create/list/update tasks; see **§9 (Todo) → Using Todo in an agent flow** for a full example.

---

## 13. Combining patterns

Build one **RunContext** and attach the subsystems you need; then use hooks, ingest, research, and agent together.

### Example: Agent + hooks + policy

```python
ctx = RunContext(case_id=..., session_id=..., user_id=..., policy=Policy(allow_tools=True), ...)
chain = HookChain([AuditHook(), PolicyHook()])
# Wrap your agent run: chain.before_run(ctx); ... run agent ...; chain.after_run(ctx, result)
```

### Example: Ingest → Evidence → Research

```python
ctx.artifacts = my_artifact_store
ingest_result = ingest_pipeline.run(ctx, DocumentInput(artifact_id="doc-1", path="report.pdf"))
evidence_from_doc = ingest_result.evidence_chunks

# Use evidence in research (e.g. in an ingest_document or analyze handler)
# or pass to a subagent / main agent as context
```

### Example: Agent + memory + subagents

```python
ctx.memory = SlidingWindowMemory(max_messages=30)
ctx.subagents = SubagentRegistry()  # register specialists
agent = MyAgent()  # PydanticAIAgentBase with memory=ctx.memory
# In a tool: result = await ctx.subagents.get("kg_proposer").run(input=ev, metadata={})
```

### Example: Agent + todo (task toolset)

```python
store = InMemoryTaskStore()
bus = InProcessEventBus()
toolset = TodoToolset(store, events=bus)
ctx.todo = toolset

# In an agent tool: create/list/update tasks scoped to ctx.case_id / session_id
# t = await ctx.deps.todo.create_task(TaskCreate(title="...", case_id=ctx.deps.case_id, ...))
# tasks = await ctx.deps.todo.list_tasks(TaskQuery(session_id=ctx.deps.session_id))
```

### Example: Research + ingest + orchestrator

```python
async def handle_ingest_document(ctx: RunContext, task: ResearchTask, ledger: ResearchLedger):
    path = task.inputs.get("path")
    doc = DocumentInput(artifact_id=task.id, path=path)
    result = ingest_pipeline.run(ctx, doc)
    return result.evidence_chunks

executor = ResearchExecutor(handlers={..., "ingest_document": handle_ingest_document})
controller = DeepResearchController(planner=planner, executor=executor, ...)
outcome = await controller.run(ctx, question="...")
```

### Example: Full stack (context, hooks, backends, skills, memory, ingest, research, agent)

```python
# 1. Context with all subsystems
ctx = RunContext(..., policy=policy, cache=cache, logger=logger, artifacts=artifacts)
ctx.backends = {"fs": LocalFilesystemBackend(...), "exec": LocalSubprocessExecBackend()}
ctx.skills = SkillRegistry(roots=["skills"])
ctx.skills.discover()
ctx.memory = SummarizingMemory(cfg=..., summarize_fn=...)
ctx.subagents = registry  # SubagentOrchestrator(registry) for run_many
ctx.todo = TodoToolset(InMemoryTaskStore(), events=InProcessEventBus())  # optional

# 2. Hooks around runs
chain = HookChain([AuditHook(), PolicyHook()])

# 3. Ingest for documents
ingest_result = ingest_pipeline.run(ctx, doc)

# 4. Research with ingest + custom handlers
executor = ResearchExecutor(handlers={"ingest_document": handle_ingest, "analyze": handle_analyze, ...})
outcome = await controller.run(ctx, question=question)

# 5. Agent with memory and tools that use ctx.deps (logger, backends, subagents)
agent = MyAgent()
chain.before_run(ctx)
result = agent.run_sync(ctx, user_message, message_history=...)
chain.after_run(ctx, result)
```

---

## Imports reference

| Area | Import from | Key types |
|------|-------------|-----------|
| Context | `agent_ext` or `agent_patterns.run_context` | RunContext, ToolCall, ToolResult, Policy |
| Hooks | `agent_ext` | Hook, BlockedToolCall, BlockedPrompt, AuditHook, PolicyHook, ContentFilterHook, ContentFilterFn, make_blocklist_filter, HookChain |
| Evidence | `agent_ext` | Citation, Provenance, Evidence |
| Skills | `agent_ext` | SkillSpec, LoadedSkill, SkillRegistry |
| Backends | `agent_ext` | LocalFilesystemBackend, LocalSubprocessExecBackend |
| Memory | `agent_ext` | SlidingWindowMemory, SummarizingMemory |
| Memory config | `agent_ext.memory.summarize` | SummarizeConfig, Dossier |
| Subagents | `agent_ext` | Subagent, SubagentResult, SubagentRegistry, SubagentOrchestrator |
| RLM | `agent_ext` | RLMPolicy, run_restricted_python |
| Todo | `agent_ext` | Task, TaskCreate, TaskPatch, TaskQuery, TaskStatus, TaskStore, InMemoryTaskStore, PostgresTaskStore, TaskEvent, TaskEventBus, InProcessEventBus, WebhookEventBus, TodoToolset |
| Ingest | `agent_ext` | DocumentInput, IngestResult, PageImage, OCRPage, OCRSpan, PageOCROutput, PageOCRElement, IngestPipeline, PDFToImages, OCREngine, LLMVisionOCREngine, PageExtractor, OCRValidator, OCRValidationPolicy, ValidationEvidenceEmitter, MultiExtractor, OCRRetryAction |
| Research | `agent_ext.research` | DeepResearchController; planner, executor, ledger, models in agent_ext.research.* |
| Pydantic-AI agent | `agent_ext` | PydanticAIAgentBase |
| Agent memory / tools | `agent_ext.agent` | build_history_processor, checkpoint_after_run, message_kind, has_tool_calls, has_tool_returns, safe_truncate_messages |

Root types live in **agent_patterns.run_context** (re-exported from **agent_ext**) so the stdlib **types** module is not shadowed.
