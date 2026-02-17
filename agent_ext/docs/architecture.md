# AgentsExt Architecture

This package provides modular, pluggable subsystems around an existing agent harness:
- Hooks (middleware): policy, audit, tracing, budgets, redaction
- Skills: progressive-disclosure instruction packs + optional tool bundles
- Backends: permissioned filesystem + execution abstractions
- Memory: context shaping + future summarization/dossier checkpoints
- Subagents: registry + orchestrator for local/server specialists
- Evidence: normalized results with provenance + citations
- RLM: escalation mode for massive context (code-guided analysis)

Nothing here replaces the system router/judge/caching; it wraps them.
