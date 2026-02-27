# AGENTS.md — Developer & AI Agent Guide

## Overview

**agent_patterns** is a self-improving, self-assembling agentic system. It introspects its own codebase, finds places to improve, generates patches via LLM, runs them through gates (compile/import/test), and optionally auto-commits. The system supports parallel subagents working in isolated git worktrees.

### Core Concepts

- **RunContext**: Single object carrying identity, policy, logger, artifacts, and optional subsystems for every operation.
- **Workbench TUI**: Interactive terminal UI for goal → plan → run → adopt workflow.
- **Cog Daemon**: Headless self-improving loop (no TUI) — runs forever, patches, gates, pushes.
- **Worktrees**: Each implement task runs in an isolated git worktree (sandbox), so concurrent patches don't interfere.
- **Structured Patching**: LLM returns structured `PatchOutput` (not raw diff) which we convert to valid unified diff ourselves.
- **Modules**: Plugin system for extending with new tools, subagents, hooks, skills, and TUI commands.

---

## Repository Structure

```
/                          # Root package: agent_patterns
├── __init__.py            # Re-exports RunContext, ToolCall, ToolResult
├── run_context.py         # RunContext, Policy, Cache, Logger, ArtifactStore
├── config.py              # Pydantic config models
├── AGENTS.md              # This file
├── WORKBENCH.md           # Workbench usage guide
├── README.md              # Full API documentation
├── pyproject.toml         # Project config (uv/hatch)
├── .env.example           # Environment variable reference
│
├── agent_ext/             # Main extension package
│   ├── __init__.py        # Lazy-loading re-exports (heavy deps deferred)
│   ├── run_context.py     # Re-export from root
│   │
│   ├── workbench/         # TUI workbench
│   │   ├── __main__.py    # Entry: python -m agent_ext.workbench
│   │   ├── tui_async.py   # Async TUI (Rich console, commands)
│   │   ├── tui.py         # Simple sync TUI (legacy)
│   │   ├── runtime.py     # build_ctx() — composition root
│   │   ├── loop.py        # Task execution loop (plan_and_queue, run_next_task)
│   │   ├── planner.py     # TaskQueue, Task dataclass
│   │   ├── models.py      # ModelConfig, build_openai_chat_model
│   │   ├── patch_models.py # PatchOutput → unified diff conversion
│   │   ├── subagents.py   # SubagentResult, RepoGrepSubagent, PlannerSubagent
│   │   ├── subagents_patch.py # LLMPatchSubagent (structured output)
│   │   ├── subagents_bm25.py  # BM25SearchSubagent
│   │   ├── worktrees.py   # Git worktree create/diff/cleanup
│   │   ├── adopt.py       # Apply diff to repo, commit & push
│   │   ├── parallel.py    # Bounded asyncio.gather
│   │   ├── streaming.py   # Pydantic-AI streaming + DAG hooks
│   │   ├── writer_runner.py # WriterCoordinator with locks
│   │   ├── limits.py      # ModelLimiter (semaphore)
│   │   ├── locks.py       # LeaseLockStore (file-based)
│   │   ├── events.py      # EventBus
│   │   └── jupyter.py     # Notebook wrapper
│   │
│   ├── cog/               # Cognitive daemon (headless)
│   │   ├── __main__.py    # Entry: python -m agent_ext.cog
│   │   ├── daemon.py      # run_forever() loop
│   │   ├── loop_v2.py     # run_cognitive_cycle()
│   │   ├── state.py       # CogState, RegressionMemory, Budget
│   │   ├── modes.py       # FAST/DEEP/REPAIR/EXPLORE modes
│   │   ├── scoring.py     # Score, score_patch, touched_files_from_diff
│   │   ├── strategy_bank.py # Strategy prompts for parallel writers
│   │   └── triggers.py    # Trigger detection (repo changes)
│   │
│   ├── self_improve/      # Patching, gates, triggers
│   │   ├── patching.py    # sanitize_diff, apply_unified_diff, _repair_hunk_headers
│   │   ├── gates.py       # run_gates (import/compile/pytest)
│   │   ├── models.py      # GatePlan, GateResults, PatchProposal
│   │   ├── controller.py  # SelfImproveController
│   │   └── triggers.py    # TriggerStore
│   │
│   ├── search/            # BM25 search index
│   │   ├── bm25.py        # BM25Index (incremental, persisted)
│   │   ├── index.py       # RepoIndexer (file scanning)
│   │   ├── tokenize.py    # Tokenizer (regex + optional tiktoken)
│   │   └── store.py       # JSON persistence
│   │
│   ├── modules/           # Plugin module system
│   │   ├── registry.py    # ModuleRegistry (discover, enable, disable)
│   │   ├── spec.py        # ModuleSpec, ModuleProvides
│   │   ├── loader.py      # Dynamic import
│   │   └── builtins/      # Built-in modules
│   │
│   ├── hooks/             # Middleware hooks
│   ├── evidence/          # Evidence + citations
│   ├── skills/            # Skill discovery + loading
│   ├── backends/          # Filesystem + exec backends
│   ├── memory/            # Conversation memory (sliding window, summarizing)
│   ├── subagents/         # Subagent protocol + registry + orchestrator
│   ├── rlm/               # Restricted Python execution
│   ├── todo/              # Task management (CRUD, events, stores)
│   ├── ingest/            # Document ingestion (PDF → OCR → Evidence)
│   ├── export/            # Document export (HTML, DOCX, PDF, PPTX)
│   ├── mcp/               # MCP tool registry + transport
│   ├── research/          # Deep research controller
│   └── workflow/          # Workflow synthesis + execution
│
├── tests/                 # Test suite
│   ├── test_patching.py   # Diff sanitization, hunk repair, git apply
│   ├── test_scoring.py    # Score properties, score_patch
│   └── test_planner.py    # TaskQueue operations
│
├── evals/                 # Evaluation scripts
├── docs/                  # Additional documentation
│   └── AUTO_AGENT.md      # Fully automated agent design doc
├── .agent_state/          # Runtime state (mostly gitignored)
└── docker/                # Docker files
```

---

## Setup

```bash
# Install dependencies
uv sync

# Copy and configure environment
cp .env.example .env
# Edit .env with your LLM endpoint

# Verify
uv run python -c "from agent_ext import RunContext; print('OK')"
```

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `LLM_BASE_URL` | LLM API base URL | `http://127.0.0.1:8000/v1` |
| `LLM_API_KEY` | API key | `local` |
| `LLM_MODEL` | Model name | `gpt-oss-120b` |
| `MAX_PARALLEL_SUBAGENTS` | Concurrent subagent calls | `4` |
| `MAX_PARALLEL_MODEL_CALLS` | Concurrent LLM calls | `2` |
| `AUTO_ADOPT` | Auto-commit after gates pass | `0` |
| `AUTO_PUSH_BRANCH` | Branch to push to | `dev` |
| `AUTO_COMMIT_THRESHOLD` | Min score to auto-adopt | `80` |
| `KEEP_WORKTREE` | Keep worktree after implement | `0` |
| `BM25_TOP_K` | Default BM25 result count | `20` |

See `.env.example` for the full list.

---

## Running

### TUI Workbench (Interactive)

```bash
uv run python -m agent_ext.workbench --use-openai-chat-model
```

Commands:
- Type a goal or `/plan <goal>` — planning runs in background
- `/run` or `/run N` — execute tasks (N parallel workers)
- `/watch` — live view of progress + LLM traces
- `/tasks` — show task queue with timing
- `/diff` — show last generated patch
- `/adopt` — apply last patch to repo
- `/retry` — retry failed tasks
- `/help` — full command reference

### Cog Daemon (Headless)

```bash
export AUTO_ADOPT=1 AUTO_PUSH_BRANCH=dev
uv run python -m agent_ext.cog --use-openai-chat-model
```

Runs forever: plan → patch → gates → (optional) commit & push.

---

## Running Tests

```bash
uv run python -m pytest tests/ -v
```

Tests cover:
- **Patching**: hunk header regex, diff sanitization, structured→unified conversion, git apply round-trips
- **Scoring**: Score properties, score_patch function, touched file extraction
- **TaskQueue**: add, claim, cancel, retry, elapsed time tracking

---

## Code Patterns

### Adding a New Subagent

1. Create a class with `name` attribute and `async run(self, ctx, *, input, meta) -> SubagentResult`
2. Register in `runtime.py`'s `build_ctx()`: `reg.register(YourSubagent())`

```python
from agent_ext.workbench.subagents import SubagentResult

class MySubagent:
    name = "my_agent"

    async def run(self, ctx, *, input, meta):
        # Do work...
        return SubagentResult(ok=True, name=self.name, output=result, meta={})
```

### Adding a New Task Kind

1. Add the kind to `plan_models.py`'s `TaskSpec.kind` Literal
2. Add handling in `loop.py`'s `run_next_task()`
3. Add to `PlannerSubagent` prompt in `subagents.py`

### Adding a New TUI Command

Add a handler in `tui_async.py`'s main loop:

```python
if msg == "/mycommand":
    console.print(Panel("output", title="mycommand", border_style="cyan"))
    continue
```

### Adding a New Module

Create `agent_ext/modules/builtins/<name>/module.py`:

```python
from agent_ext.modules.spec import ModuleProvides, ModuleSpec

def init(ctx) -> None:
    # Register tools, subagents, hooks, etc.
    pass

module_spec = ModuleSpec(
    name="my_module",
    version="0.1.0",
    description="What it does",
    provides=ModuleProvides(commands=["/my_cmd"]),
    init=init,
)
```

---

## Key Design Decisions

- **Structured patches over raw diffs**: LLM returns `PatchOutput` (file edits with context/add/remove lines), we convert to valid unified diff ourselves. Avoids raw diff parsing failures.
- **Worktree isolation**: Each implement task gets its own git worktree. Patches are applied there, gates run there, then the diff is captured and the worktree is cleaned up.
- **Lazy imports**: Heavy dependencies (pydantic-ai, exporters, postgres) are loaded on first use via `__getattr__`. This keeps startup fast (~0.5s).
- **Deferred BM25 indexing**: The search index is built on first search, not at startup.
- **Atomic task claiming**: `TaskQueue.claim_next_pending()` uses an asyncio lock so multiple parallel workers can safely drain the queue.

---

## Common Issues

### "No unified diff found in output"
The LLM returned prose instead of structured JSON. Check `/traces` for the raw model output. The structured output approach (PatchOutput) should prevent this; if it happens, the model may not support structured output.

### Worktree errors
If a worktree fails to create (branch already exists), use a unique `run_id` or clean up stale worktrees:
```bash
git worktree prune
```

### Import errors in gates
Gates run `import agent_ext` and `import agent_patterns` as a sanity check. If these fail in a worktree, the patch likely broke an import. Check the gate details in the task output.
