# AGENTS.md — Developer & AI Agent Guide

## Overview

**agent_factory** is a self-improving, self-assembling agentic system. It provides modular, pluggable subsystems for building AI agents: middleware, subagents, memory, backends, skills, RLM, database, and a workbench TUI for interactive development. All subsystems are at feature parity with their upstream reference implementations.

---

## Repository Structure

```
/                              # Root package: agent_patterns
├── AGENTS.md                  # This file
├── README.md                  # Full API documentation
├── WORKBENCH.md               # Workbench usage guide
├── pyproject.toml             # Project config
├── .env.example               # Environment variables reference
│
├── agent_ext/                 # Main extension package
│   ├── hooks/                 # Middleware system (async, context, cost, parallel, permissions)
│   │   ├── README.md
│   │   ├── base.py            # AgentMiddleware ABC + legacy Hook Protocol
│   │   ├── chain.py           # MiddlewareChain (async) + HookChain (legacy sync)
│   │   ├── context.py         # ScopedContext with hook-type access control
│   │   ├── cost_tracking.py   # Token + USD cost monitoring with budgets
│   │   ├── parallel.py        # Run middleware concurrently (ALL_MUST_PASS, FIRST_WINS, MERGE)
│   │   ├── permissions.py     # ALLOW/DENY/ASK tool decisions
│   │   ├── builtins.py        # AuditHook, PolicyHook, ContentFilterHook, ConditionalMiddleware
│   │   └── exceptions.py      # InputBlocked, ToolBlocked, BudgetExceededError, etc.
│   │
│   ├── subagents/             # Multi-agent orchestration
│   │   ├── README.md
│   │   ├── base.py            # Subagent/SubagentResult protocol
│   │   ├── registry.py        # SubagentRegistry (static) + DynamicAgentRegistry
│   │   ├── orchestrator.py    # SubagentOrchestrator (bounded parallel)
│   │   ├── types.py           # Messages, TaskHandle, SubAgentConfig, auto-mode selection
│   │   └── message_bus.py     # InMemoryMessageBus (ask/answer), TaskManager (soft/hard cancel)
│   │
│   ├── rlm/                   # Recursive Language Model — large context analysis
│   │   ├── README.md
│   │   ├── models.py          # RLMConfig, REPLResult, GroundedResponse, RLMDependencies
│   │   ├── repl.py            # REPLEnvironment (persistent state, llm_query, sandboxed)
│   │   ├── policies.py        # RLMPolicy (legacy)
│   │   └── python_runner.py   # run_restricted_python (legacy)
│   │
│   ├── backends/              # File storage, execution, permissions
│   │   ├── README.md
│   │   ├── base.py            # FilesystemBackend + ExecBackend protocols
│   │   ├── local_fs.py        # LocalFilesystemBackend (sandboxed to root)
│   │   ├── sandbox_exec.py    # LocalSubprocessExecBackend
│   │   ├── state.py           # StateBackend (in-memory, for testing)
│   │   ├── permissions.py     # PermissionChecker + presets (READONLY, PERMISSIVE, etc.)
│   │   └── hashline.py        # Content-hash line editing for precise AI edits
│   │
│   ├── memory/                # Context management
│   │   ├── README.md
│   │   ├── base.py            # MemoryManager protocol
│   │   ├── window.py          # SlidingWindowMemory (message-count + token-aware)
│   │   ├── summarize.py       # SummarizingMemory (LLM dossier compression)
│   │   └── cutoff.py          # Safe cutoff preserving tool call/response pairs
│   │
│   ├── skills/                # Progressive-disclosure instruction packs
│   │   ├── README.md
│   │   ├── models.py          # SkillSpec, LoadedSkill, create_skill()
│   │   ├── registry.py        # SkillRegistry (directory discovery)
│   │   ├── loader.py          # SkillLoader
│   │   ├── exceptions.py      # SkillNotFoundError, SkillValidationError
│   │   └── registries/        # CombinedRegistry, FilteredRegistry, PrefixedRegistry
│   │
│   ├── database/              # SQL capabilities for AI agents
│   │   ├── README.md
│   │   ├── types.py           # QueryResult, SchemaInfo, TableInfo, DatabaseConfig
│   │   ├── protocol.py        # DatabaseBackend protocol
│   │   └── sqlite.py          # SQLiteDatabase with security controls
│   │
│   ├── evidence/              # Evidence + citations
│   ├── todo/                  # Task management (CRUD, deps, events, stores)
│   ├── workbench/             # TUI workbench (plan → run → adopt)
│   ├── cog/                   # Cognitive daemon (headless self-improvement)
│   ├── self_improve/          # Patching, gates, triggers
│   ├── search/                # BM25 search index
│   ├── modules/               # Plugin module system
│   ├── mcp/                   # MCP tool registry
│   ├── ingest/                # Document ingestion
│   ├── export/                # Document export
│   ├── research/              # Deep research controller
│   └── workflow/              # Workflow synthesis + execution
│
├── tests/                     # 158 tests
│   ├── test_hooks.py          # Middleware: chain, context, cost, parallel, permissions
│   ├── test_subagents.py      # Registries, message bus, execution modes
│   ├── test_rlm.py            # REPL, persistent state, grounded response
│   ├── test_backends_new.py   # State backend, permissions, hashline
│   ├── test_memory_new.py     # Window, safe cutoff, token-based trim
│   ├── test_database.py       # SQLite queries, security, schemas
│   ├── test_skills_new.py     # Programmatic skills, registry composition
│   ├── test_patching.py       # Diff sanitization, hunk repair, git apply
│   ├── test_planner.py        # TaskQueue operations
│   ├── test_scoring.py        # Score properties, score_patch
│   └── test_worktrees.py      # Git worktree operations
│
└── docs/                      # Additional documentation
```

---

## Setup

```bash
uv sync
cp .env.example .env  # configure LLM endpoint
uv run python -m pytest tests/ -v  # verify 158 tests pass
```

---

## Running

```bash
# TUI workbench
uv run python -m agent_ext.workbench --use-openai-chat-model

# Cog daemon (headless)
AUTO_ADOPT=1 uv run python -m agent_ext.cog --use-openai-chat-model
```

---

## Running Tests

```bash
uv run python -m pytest tests/ -v
```

---

## Subsystem Quick Reference

### Middleware (`hooks/`)
Async lifecycle hooks with scoped context, cost tracking, parallel execution, and permissions.
```python
from agent_ext.hooks import MiddlewareChain, AuditHook, PolicyHook, CostTrackingMiddleware
chain = MiddlewareChain([AuditHook(), PolicyHook(), CostTrackingMiddleware(budget_limit_usd=5.0)])
```

### Subagents (`subagents/`)
Multi-agent orchestration with message bus and task management.
```python
from agent_ext.subagents import DynamicAgentRegistry, InMemoryMessageBus, TaskManager
```

### RLM (`rlm/`)
Sandboxed REPL for large-context analysis with sub-model delegation.
```python
from agent_ext.rlm import REPLEnvironment, RLMConfig, GroundedResponse
```

### Backends (`backends/`)
File storage with permissions, in-memory testing backend, hashline editing.
```python
from agent_ext.backends import StateBackend, PermissionChecker, READONLY_RULESET, format_hashline_output
```

### Memory (`memory/`)
Token-aware sliding window with safe cutoff preserving tool call pairs.
```python
from agent_ext.memory import SlidingWindowMemory
memory = SlidingWindowMemory(max_tokens=100_000, trigger_tokens=80_000)
```

### Skills (`skills/`)
Progressive-disclosure skills with programmatic creation and registry composition.
```python
from agent_ext.skills import create_skill, CombinedRegistry, FilteredRegistry
```

### Database (`database/`)
SQL capabilities with security controls.
```python
from agent_ext.database import SQLiteDatabase, DatabaseConfig
```

---

## Code Patterns

### Adding a New Subagent
```python
from agent_ext.workbench.subagents import SubagentResult
class MyAgent:
    name = "my_agent"
    async def run(self, ctx, *, input, meta):
        return SubagentResult(ok=True, name=self.name, output="result", meta={})
```

### Adding a New Middleware
```python
from agent_ext.hooks import AgentMiddleware, InputBlocked
class MyFilter(AgentMiddleware):
    async def before_run(self, ctx, prompt):
        if "blocked" in str(prompt):
            raise InputBlocked("Blocked content")
        return prompt
```

### Adding a New Module
Create `agent_ext/modules/builtins/<name>/module.py` with `module_spec`.

---

## Key Design Decisions

- **Async-first middleware** with backward-compat sync hooks
- **Scoped context** with hook-type access control (earlier hooks only)
- **Structured patches** — LLM returns structured edits, we convert to valid unified diff
- **Worktree isolation** — each implement task in its own git worktree
- **Safe cutoff** — never split tool call/response pairs when trimming history
- **Lazy imports** — heavy deps (pydantic-ai, exporters) loaded on first use
- **Permission presets** — READONLY, DEFAULT, PERMISSIVE, STRICT
- **Hashline editing** — content-hash-tagged lines for precise AI edits
