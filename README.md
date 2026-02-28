# agent_patterns

A self-improving, self-assembling agentic system built on [pydantic-ai](https://ai.pydantic.dev). Modular subsystems that plug together: **middleware**, **subagents**, **RLM code execution**, **backends**, **memory**, **skills**, **database**, **todo**, **evidence**, **document ingest**, **deep research**, and an interactive **workbench TUI** for goal → plan → run → adopt workflows.

Use one subsystem or all of them. Everything composes through pydantic-ai's `FunctionToolset` API and our `AgentPatterns` batteries-included agent.

```bash
uv sync && uv run python -m agent_ext.workbench --use-openai-chat-model
```

---

## Table of Contents

- [Quick Start](#quick-start)
- [AgentPatterns — Batteries-Included Agent](#agentpatterns--batteries-included-agent)
- [Workbench TUI](#workbench-tui)
- [Cog Daemon (Headless)](#cog-daemon-headless)
- [Subsystems](#subsystems)
  - [Middleware](#middleware)
  - [Subagents](#subagents)
  - [RLM (Code Execution)](#rlm-code-execution)
  - [Backends](#backends)
  - [Memory](#memory)
  - [Skills](#skills)
  - [Database](#database)
  - [Todo](#todo)
  - [Evidence](#evidence)
  - [Document Ingest](#document-ingest)
  - [Deep Research](#deep-research)
- [Toolset Factories](#toolset-factories)
- [Setup](#setup)
- [Environment Variables](#environment-variables)
- [Running Tests](#running-tests)

---

## Quick Start

```bash
# Install
uv sync

# Configure
cp .env.example .env
# Edit .env with your LLM_BASE_URL, LLM_API_KEY, LLM_MODEL

# Run the interactive workbench
uv run python -m agent_ext.workbench --use-openai-chat-model

# Or use programmatically
uv run python -c "
from agent_ext.agent import AgentPatterns
agent = AgentPatterns('openai:gpt-4o', toolsets=['console', 'todo'])
print(type(agent))
"
```

---

## AgentPatterns — Batteries-Included Agent

`AgentPatterns` inherits from pydantic-ai's `Agent` and auto-wires all subsystems. Pass toolset names as strings and get a fully-equipped agent:

```python
from agent_ext.agent import AgentPatterns
from agent_ext.memory import SlidingWindowMemory

# Coding assistant with filesystem + task management + memory
agent = AgentPatterns(
    "openai:gpt-4o",
    instructions="You are a helpful coding assistant.",
    toolsets=["console", "todo"],
    memory=SlidingWindowMemory(max_tokens=100_000),
)

result = await agent.run("List all Python files and create a review task for each")
```

### Factory Methods

```python
# Console agent — ls, read, write, edit, grep, execute
agent = AgentPatterns.with_console("openai:gpt-4o")

# Data analysis — sandboxed Python REPL with sub-model delegation
agent = AgentPatterns.with_rlm("openai:gpt-4o", sub_model="openai:gpt-4o-mini")

# Database — SQL queries with read-only protection
agent = AgentPatterns.with_database("openai:gpt-4o")

# Everything at once
agent = AgentPatterns.with_all("openai:gpt-4o")
```

### Composing Toolsets

Pass names (auto-created) or `FunctionToolset` instances:

```python
from agent_ext.rlm import create_rlm_toolset
from agent_ext.backends.console import create_console_toolset

agent = AgentPatterns(
    "openai:gpt-4o",
    toolsets=[
        "todo",                                    # by name
        create_console_toolset(),                   # pre-configured instance
        create_rlm_toolset(code_timeout=120),       # custom settings
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

## Workbench TUI

Interactive terminal UI for the self-improving agent loop. Think OpenCode / Claude Code style — non-blocking, parallel, streaming.

```bash
uv run python -m agent_ext.workbench --use-openai-chat-model
```

### Workflow

1. **Type a goal** (or `/plan <goal>`) — planning runs in background, prompt returns immediately
2. **`/run`** (or `/run N` for N parallel workers) — tasks execute, completions stream live
3. **`/watch`** — live-updating view of progress + LLM trace
4. **`/adopt`** — apply the generated patch to your repo
5. **`/diff`** — view the last generated patch with syntax highlighting

### Commands

| Command | Description |
|---------|-------------|
| `/plan <goal>` | Queue a plan (background) |
| `/run` or `/run N` | Execute tasks (N parallel workers) |
| `/run N fg` | Execute with live spinner (foreground) |
| `/watch` | Live view of run + LLM trace |
| `/tasks` | Task queue with timing + icons |
| `/diff` | Show last generated patch |
| `/adopt` | Apply last patch to repo |
| `/retry [id]` | Retry failed tasks |
| `/cancel <id>` | Cancel pending task |
| `/ask <question>` | One-off LLM question (background) |
| `/traces [N]` | Last N LLM traces |
| `/trace` | Last trace in full |
| `/status` | Run info + queue counts |
| `/stop` or `/stop all` | Cancel background runs |
| `/parallel <n>` | Set max concurrent subagents |
| `/model` | Model info |
| `/clear` | Clear screen |
| `/help` | Full command reference |

### How It Works

The workbench runs a **plan → search → design → implement → gates** pipeline:

- **Plan**: LLM dynamically chooses task sequence (or fixed fallback without model)
- **Search**: BM25 index + repo grep find relevant code
- **Design**: LLM proposes approach + file list
- **Implement**: LLM generates structured patch → applied in isolated git worktree → gates run
- **Gates**: Import check + compile check + optional pytest
- **Adopt**: Diff saved to `.agent_state/`; `/adopt` applies to main repo

Each implement step runs in an **isolated git worktree** — concurrent patches don't interfere. The structured patch system (LLM returns `PatchOutput` JSON, we convert to valid unified diff) avoids raw diff parsing failures.

---

## Cog Daemon (Headless)

Fully automated self-improving loop — no TUI, runs forever.

```bash
export AUTO_ADOPT=1 AUTO_PUSH_BRANCH=dev
uv run python -m agent_ext.cog --use-openai-chat-model
```

The daemon runs cognitive cycles: detect triggers → choose mode (FAST/DEEP/REPAIR/EXPLORE) → parallel writers in worktrees → score patches → auto-adopt if gates pass + score threshold met → commit and push.

Anti-thrash protection via `RegressionMemory` prevents oscillating edits. Per-runner branches support multiple agents working concurrently.

---

## Subsystems

### Middleware

Async lifecycle hooks with 7 hook points, scoped context, cost tracking, parallel execution, and permissions.

```python
from agent_ext.hooks import (
    MiddlewareChain, AuditHook, PolicyHook,
    CostTrackingMiddleware, ParallelMiddleware,
    AsyncGuardrailMiddleware, GuardrailTiming,
    ConditionalMiddleware, middleware_from_functions,
    make_blocklist_filter, ContentFilterHook,
    ToolDecision, ToolPermissionResult,
)

# Cost tracking with budget enforcement
cost_mw = CostTrackingMiddleware(budget_limit_usd=5.0, cost_per_1k_input=0.01)

# Parallel validators — all must pass
parallel = ParallelMiddleware([PIIDetector(), InjectionGuard()])

# Async guardrail — runs alongside LLM, cancels on failure
guardrail = AsyncGuardrailMiddleware(PolicyCheck(), timing=GuardrailTiming.CONCURRENT)

# Conditional — only run when condition met
redactor = ConditionalMiddleware(
    condition=lambda ctx: ctx.policy.redaction_level != "none",
    when_true=RedactionMiddleware(),
)

chain = MiddlewareChain([AuditHook(), cost_mw, parallel, guardrail, redactor])
```

**Features**: scoped context with access control (earlier hooks only), `ToolDecision.ALLOW/DENY/ASK`, per-hook timeouts, tool-name filtering, decorator-based creation via `middleware_from_functions()`.

### Subagents

Multi-agent orchestration with message bus, dynamic registry, and task management.

```python
from agent_ext.subagents import (
    SubagentRegistry, DynamicAgentRegistry,
    InMemoryMessageBus, TaskManager,
    SubAgentConfig, decide_execution_mode,
)

# Dynamic creation at runtime with limits
registry = DynamicAgentRegistry(max_agents=10)
config = SubAgentConfig(name="researcher", description="...", instructions="...")
registry.register(config, agent_instance)

# Message bus with ask/answer protocol
bus = InMemoryMessageBus()
queue = bus.register_agent("worker-1")
response = await bus.ask("parent", "worker-1", "Analyze this", task_id="t1")

# Auto sync/async mode selection
mode = decide_execution_mode(TaskCharacteristics(estimated_complexity="complex"), config)
```

### RLM (Code Execution)

Sandboxed REPL for large-context analysis. The LLM writes Python code to explore data, with optional `llm_query()` for sub-model delegation.

```python
from agent_ext.rlm import REPLEnvironment, RLMConfig, GroundedResponse

repl = REPLEnvironment(
    context=massive_document,  # str, dict, or list
    config=RLMConfig(sub_model="openai:gpt-4o-mini"),
)

# State persists between executions
repl.execute("print(f'Context: {len(context)} chars')")
repl.execute("""
relevant = [l for l in context.split('\\n') if 'revenue' in l.lower()]
analysis = llm_query(f"Summarize: {relevant[:5]}")
print(analysis)
""")

# Grounded response with citations
response = GroundedResponse(
    info="Revenue grew [1] driven by expansion [2]",
    grounding={"1": "increased by 45%", "2": "new markets in Asia"},
)
```

### Backends

File storage with permission presets, in-memory testing, hashline editing, and composite routing.

```python
from agent_ext.backends import (
    StateBackend, LocalFilesystemBackend, CompositeBackend,
    PermissionChecker, READONLY_RULESET, PERMISSIVE_RULESET,
    format_hashline_output, apply_hashline_edit,
)

# In-memory for tests
backend = StateBackend()
backend.write_text("src/app.py", "print('hello')")

# Composite: route by path prefix
composite = CompositeBackend(
    default=StateBackend(),
    routes={"/project/": LocalFilesystemBackend(root="/my/project", allow_write=True)},
)

# Hashline: precise edits by line number + hash (no text matching needed)
tagged = format_hashline_output("def hello():\n    return 42\n")
# 1:96|def hello():
# 2:2a|    return 42
new_content, error = apply_hashline_edit(content, start_line=2, start_hash="2a", new_content="    return 99")
```

**Permission presets**: `READONLY_RULESET`, `DEFAULT_RULESET`, `PERMISSIVE_RULESET`, `STRICT_RULESET`. All deny `.env`, `.pem`, `.key`, credentials.

### Memory

Token-aware sliding window and auto-triggering LLM summarization. Never splits tool call/response pairs.

```python
from agent_ext.memory import (
    SlidingWindowMemory,
    SummarizationProcessor, create_summarization_processor,
)

# Sliding window (message or token mode)
memory = SlidingWindowMemory(max_tokens=100_000, trigger_tokens=80_000)

# Auto-triggering LLM summarizer
processor = create_summarization_processor(
    model="openai:gpt-4o-mini",
    trigger=("tokens", 100_000),
    keep=("messages", 20),
)
# Use as pydantic-ai history_processor:
# agent = Agent("openai:gpt-4o", history_processors=[processor])
```

### Skills

Progressive-disclosure instruction packs with directory discovery, programmatic creation, registry composition, and git-backed remote loading.

```python
from agent_ext.skills import (
    SkillRegistry, create_skill,
    CombinedRegistry, FilteredRegistry, PrefixedRegistry, RenamedRegistry,
)
from agent_ext.skills.registries.git import GitSkillsRegistry

# Local discovery
local = SkillRegistry(roots=["skills"])
local.discover()

# Git-backed (clone from any repo)
remote = GitSkillsRegistry(
    repo_url="https://github.com/anthropics/skills",
    path="skills",
    target_dir="./cached-skills",
)

# Compose registries
combined = CombinedRegistry([local, remote])
python_only = FilteredRegistry(combined, predicate=lambda s: "python" in s.tags)
namespaced = PrefixedRegistry(remote, prefix="remote_")

# Programmatic creation (no filesystem)
skill = create_skill(id="review", name="Code Review", description="...", body="# Review\n...")
```

### Database

SQL capabilities with SQLite and PostgreSQL backends, security controls, and a FunctionToolset.

```python
from agent_ext.database import SQLiteDatabase, PostgresDatabase, DatabaseConfig

# SQLite (read-only by default)
async with SQLiteDatabase("data.db") as db:
    tables = await db.list_tables()
    result = await db.execute_query("SELECT * FROM users WHERE age > 25")

# PostgreSQL
async with PostgresDatabase("postgresql://user:pass@localhost/mydb") as db:
    schema = await db.get_schema()
    result = await db.execute_query("SELECT COUNT(*) FROM orders")

# Security: read-only, row limits, query length limits
config = DatabaseConfig(read_only=True, max_rows=1000, timeout_s=30)
```

### Todo

Task management with subtasks, dependencies, events, and multi-tenant scoping.

```python
from agent_ext.todo import InMemoryTaskStore, TodoToolset, TaskCreate, TaskQuery

store = InMemoryTaskStore()
toolset = TodoToolset(store)

task = await toolset.create_task(TaskCreate(title="Review PR", tags=["review"], case_id="case-1"))
tasks = await toolset.list_tasks(TaskQuery(case_id="case-1", status="pending"))
await toolset.update_task(task.id, TaskPatch(status="done"))
```

### Evidence

Universal output format for structured findings with citations and provenance.

```python
from agent_ext.evidence import Evidence, Citation, Provenance

evidence = Evidence(
    kind="finding",
    content="Revenue grew 45%",
    citations=[Citation(source_id="doc-1", locator="page:3", quote="...", confidence=0.9)],
    provenance=Provenance(produced_by="ingest_pipeline", artifact_ids=["doc-1"]),
)
```

### Document Ingest

PDF → page images → OCR → validation → Evidence with citations.

### Deep Research

Plan → execute → gap analysis → synthesize. Pluggable handlers for search, ingest, analyze, synthesize.

---

## Toolset Factories

Every subsystem provides a `create_*_toolset()` factory that returns a pydantic-ai `FunctionToolset`:

```python
from agent_ext.rlm import create_rlm_toolset
from agent_ext.database import create_database_toolset
from agent_ext.backends.console import create_console_toolset
from agent_ext.subagents import create_subagent_toolset
from agent_ext.todo import create_todo_toolset
from agent_ext.skills.pai_toolset import create_skills_toolset
```

---

## Setup

```bash
# Install all dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL

# Verify
uv run python -c "from agent_ext import AgentPatterns; print('OK')"

# Run tests
uv run python -m pytest tests/ -v
```

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `LLM_BASE_URL` | LLM API endpoint | `http://127.0.0.1:8000/v1` |
| `LLM_API_KEY` | API key | `local` |
| `LLM_MODEL` | Model name | `gpt-oss-120b` |
| `MAX_PARALLEL_SUBAGENTS` | Concurrent subagent calls | `4` |
| `MAX_PARALLEL_MODEL_CALLS` | Concurrent LLM calls | `2` |
| `AUTO_ADOPT` | Auto-commit after gates pass | `0` |
| `AUTO_PUSH_BRANCH` | Branch to push to | `dev` |
| `AUTO_COMMIT_THRESHOLD` | Min score to auto-adopt | `80` |
| `KEEP_WORKTREE` | Keep worktree after implement | `0` |
| `BM25_TOP_K` | Default search results | `20` |
| `GITHUB_TOKEN` | For git skill registry auth | (none) |

See `.env.example` for the full list.

---

## Running Tests

```bash
# All tests (186 passing)
uv run python -m pytest tests/ -v

# Specific subsystem
uv run python -m pytest tests/test_hooks.py -v
uv run python -m pytest tests/test_database.py -v

# With coverage
uv run python -m pytest tests/ --cov=agent_ext
```

---

## License

MIT
