# Integration Guide

## 1) Composition root (create subsystems)
- SkillRegistry.discover()
- SkillLoader
- SkillSelector
- MemoryManager (SlidingWindowMemory to start)
- FilesystemBackend + ExecBackend from policy
- SubagentRegistry + SubagentOrchestrator
- HookChain([AuditHook(), PolicyHook(), ...])

## 2) Run loop insertion points
Given your current loop:
router -> agent -> judge -> cache

Wrap it like:
- hooks.before_run(ctx)
- shape messages via ctx.memory.shape_messages(...)
- build skill context pack and inject instructions into the model prompt
- for each tool call: hooks.before_tool_call(...) / after_tool_result(...)
- on model request/response: hooks.before_model_request / after_model_response
- judge validates final output
- memory checkpoint + hooks.after_run(ctx, outcome)

## 3) Evidence everywhere
Require tools and subagents to return Evidence objects (or lists of them).
The judge should validate:
- correctness
- provenance present
- citations present for factual claims when possible
