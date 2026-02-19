from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import os
from .subagents import SubagentResult

# Optional: pydantic-ai for design/implement LLM steps
try:
    from pydantic_ai import Agent
except ImportError:
    Agent = None  # type: ignore[misc, assignment]

from agent_ext.workbench.worktrees import create_worktree, cleanup_worktree, worktree_diff
from agent_ext.self_improve.gates import run_gates
from agent_ext.self_improve.models import GatePlan
from agent_ext.self_improve.patching import apply_unified_diff
from agent_ext.workbench.adopt import apply_diff_to_repo, commit_and_push
from agent_ext.cog.scoring import score_patch, touched_files_from_diff
from pathlib import Path

LLM_TRACE_MAX = 30
# Store enough for debugging; trace is appended after full response (not streamed)
LLM_TRACE_PROMPT_LEN = 8_000
LLM_TRACE_RESPONSE_LEN = 12_000


def _append_llm_trace(ctx, kind: str, prompt: str, response: str) -> None:
    traces = getattr(ctx, "llm_traces", None)
    if traces is None:
        return
    if len(traces) >= LLM_TRACE_MAX:
        traces.pop(0)
    traces.append({
        "kind": kind,
        "prompt": (prompt or "")[:LLM_TRACE_PROMPT_LEN],
        "response": (response or "")[:LLM_TRACE_RESPONSE_LEN],
    })


async def _implement_in_worktree(
    ctx,
    goal: str,
    candidates: list[dict],
    strategy: str | None = None,
    task_id: Optional[str] = None,
) -> str:
    """
    Lifecycle: (1) Create a temporary worktree (sandbox). (2) Apply LLM diff there, run gates.
    (3) Capture diff from worktree and save to .agent_state/patch_<run_id>.diff. (4) Optionally
    AUTO_ADOPT: apply that file to main repo and commit+push. (5) finally: remove worktree.
    Uses task_id in run_id when provided so concurrent implement tasks don't collide on the same worktree.
    """
    run_id = f"{ctx.session_id}_{task_id}" if task_id else ctx.session_id
    wt = create_worktree(run_id=run_id, agent_name="writer_llm_patch")

    try:
        # 1) generate diff (inside the worktree context)
        patcher = ctx.subagents.get("llm_patch")
        meta = {"workdir": str(wt.path), "candidates": candidates, "max_files": 6}
        if strategy:
            meta["strategy"] = strategy
        res = await patcher.run(ctx, input=goal, meta=meta)
        raw_output = (res.output or "").strip()
        # Even if LLM didn't return something that starts with diff --git/---, try sanitizer (e.g. extract from markdown)
        ok_apply = False
        out_apply = ""
        if raw_output:
            ok_apply, out_apply = apply_unified_diff(raw_output, repo_root=wt.path)
        if not ok_apply:
            snippet = (raw_output[:800] + ("..." if len(raw_output) > 800 else "")) if raw_output else "(empty)"
            reason = "model output not a raw diff (no diff --git or --- at start)" if not res.ok and not raw_output else out_apply or "no unified diff found in output"
            return (
                f"implement: create patch failed.\n"
                f"Reason: {reason}\n"
                f"Model output (first 800 chars):\n{snippet}"
            )

        # 3) gates in worktree (compile/import; pytest optional)
        plan = GatePlan(import_check=True, compile_check=True, pytest_paths=[])
        gates = run_gates(plan, repo_root=wt.path)

        # 4) produce final diff
        diff = worktree_diff(wt)

        # ---- NEW: persist diff into agent state ----
        state_dir = Path(".agent_state")
        state_dir.mkdir(parents=True, exist_ok=True)

        diff_path = state_dir / f"patch_{run_id}.diff"
        diff_path.write_text(diff, encoding="utf-8")

        # pointer to latest patch (optional but nice)
        (state_dir / "last_patch_path.txt").write_text(str(diff_path), encoding="utf-8")

        # ---- append modules history (learning memory) ----
        hist = state_dir / "modules_history.json"

        data = {"patches": []}
        if hist.exists():
            data = json.loads(hist.read_text(encoding="utf-8"))

        data["patches"].append({
            "run_id": run_id,
            "path": str(diff_path),
            "gates_ok": gates.ok,
            "diff_chars": len(diff),
        })

        hist.write_text(json.dumps(data, indent=2), encoding="utf-8")
        # --------------------------------------------
        touched = touched_files_from_diff(diff)
        sc = score_patch(gates_ok=gates.ok, diff_chars=len(diff), files_touched=len(touched), eval_delta=0.0)
        # ---- AUTO-ADOPT (optional) ----
        AUTO_ADOPT = bool(int(os.getenv("AUTO_ADOPT", "0")))  # default off until you're confident
        AUTO_PUSH_BRANCH = os.getenv("AUTO_PUSH_BRANCH", "dev")
        threshold = float(os.getenv("AUTO_COMMIT_THRESHOLD", "80"))

        if gates.ok and AUTO_ADOPT and sc.score >= threshold:
            # 1) apply to main working tree (outside worktree)
            apply_diff_to_repo(diff, repo_root=Path("."))

            # 2) rerun gates on main tree (highly recommended)
            main_plan = GatePlan(import_check=True, compile_check=True, pytest_paths=[])
            main_gates = run_gates(main_plan, repo_root=Path("."))

            if not main_gates.ok:
                return (
                    "implement: worktree gates passed, BUT main-tree gates FAILED after auto-adopt.\n"
                    f"diff_saved={diff_path}\n"
                    f"main_gates={list(main_gates.details.keys())}\n"
                    "Patch is applied in your working tree; revert or fix-forward.\n"
                )

            # 3) commit + push
            msg = f"auto: {goal[:72]}"
            commit_and_push(message=msg, branch=AUTO_PUSH_BRANCH, repo_root=Path("."))

            return (
                f"implement: ok_apply={ok_apply} gates_ok={gates.ok}\n"
                f"AUTO_ADOPT: patch applied to main repo and pushed to {AUTO_PUSH_BRANCH}\n"
                f"diff_saved={diff_path}\n"
            )
        # ------------------------------
        else:
            keep_msg = f"worktree_kept={wt.path}\n" if bool(int(os.getenv("KEEP_WORKTREE", "0"))) else ""
            return (
                f"implement: ok_apply={ok_apply} gates_ok={gates.ok}\n"
                f"diff_saved={diff_path}\n"
                f"Patch is on disk; worktree will be removed (use KEEP_WORKTREE=1 to keep). Use /adopt to apply to main repo.\n"
                f"score={sc.score}\n"
                f"threshold={threshold}\n"
                f"AUTO_ADOPT={AUTO_ADOPT}\n"
                f"AUTO_PUSH_BRANCH={AUTO_PUSH_BRANCH}\n"
                f"{keep_msg}"
            )

    finally:
        # Patch already saved to diff_path above; safe to remove worktree (sandbox only—we never commit in it).
        keep = bool(int(os.getenv("KEEP_WORKTREE", "0")))
        state_dir = Path(".agent_state")
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "last_worktree_path.txt").write_text(str(wt.path), encoding="utf-8")
        if not keep:
            cleanup_worktree(wt, prune_branch=False)
        else:
            # Leave worktree in place; user can inspect or remove manually
            pass

async def plan_and_queue(ctx, user_goal: str) -> List[str]:
    """
    Uses planner subagent to generate tasks, then enqueues them.
    """
    planner = ctx.subagents.get("planner")
    res = await planner.run(ctx, input=user_goal, meta={})
    if not res.ok:
        return [f"planner failed: {res.output}"]

    tasks = res.output
    lines = []
    state = getattr(ctx, "workbench_run_state", None)
    if state is not None:
        state["goal"] = user_goal
    for t in tasks:
        ctx.task_queue.add(t["kind"], t["title"], t["input"])
        lines.append(f"queued: {t['kind']} - {t['title']}")
    return lines


async def run_next_task(ctx) -> str:
    """
    Executes a single pending task. For now, only implements:
    - search: uses repo_grep
    - analyze/design: placeholder
    - implement: placeholder (tomorrow we wire LLM patch gen + self_improve controller)
    - gates: placeholder
    """
    t = await ctx.task_queue.claim_next_pending()
    if not t:
        return "no pending tasks"

    try:
        if t.kind == "search":
            query = str(t.input).strip()
            # Run repo_grep (literal substring) and BM25 (index) in parallel
            calls = [
                ("repo_grep", query, {"root": ".", "limit": 25, "regex": False}),
            ]
            results: List[SubagentResult] = await ctx.orchestrator.run_many(
                ctx,
                calls,
                max_concurrency=ctx.max_parallel_subagents,
            )
            bm = await ctx.subagents.get("bm25").run(ctx, input=str(t.input), meta={"k": 20})
            t.meta["bm25_candidates"] = bm.output
            state = getattr(ctx, "workbench_run_state", None)
            if state is not None:
                state["search_bm25_hits"] = bm.output
            t.status = "done"
            return f"{t.id} done: search\n- bm25: {len(bm.output)} hits\n  top: " + ", ".join([x["path"] for x in bm.output[:5]])


        if t.kind == "analyze":
            goal = str(t.input).strip()
            state = getattr(ctx, "workbench_run_state", None) or {}
            state["goal"] = goal
            if hasattr(ctx, "workbench_run_state"):
                ctx.workbench_run_state.update(state)
            if ctx.model and Agent is not None:
                analyze_prompt = f"Clarify this goal into a short, concrete one-paragraph spec (what to build, what success looks like). Goal: {goal}"
                async with ctx.model_limiter:
                    agent = Agent(model=ctx.model)
                    result = await agent.run(analyze_prompt)
                spec = result.output if hasattr(result, "output") else str(result)
                _append_llm_trace(ctx, "analyze", analyze_prompt, spec)
                state["analyze_spec"] = spec
                if hasattr(ctx, "workbench_run_state"):
                    ctx.workbench_run_state.update(state)
                t.status = "done"
                return f"{t.id} done: analyze\n{spec[:400]}..."
            t.status = "done"
            return f"{t.id} done: analyze (no model; goal stored)"

        if t.kind == "design":
            state = getattr(ctx, "workbench_run_state", None) or {}
            goal = state.get("goal", str(t.input))
            spec = state.get("analyze_spec", "")
            bm25 = state.get("search_bm25_hits", [])[:10]
            repo_hits = state.get("search_repo_hits", [])
            files_ctx = ""
            if bm25:
                paths = [x["path"] if isinstance(x, dict) else x[0] for x in bm25]
                files_ctx = "Relevant paths (from search): " + ", ".join(paths)
            if repo_hits and isinstance(repo_hits, list):
                flat = []
                for r in repo_hits:
                    if isinstance(r, list):
                        flat.extend([x.get("file", x) if isinstance(x, dict) else str(x) for x in r])
                    else:
                        flat.append(str(r))
                if flat:
                    files_ctx += "\nRepo grep files: " + ", ".join(flat[:15])
            if ctx.model and Agent is not None:
                design_prompt = (
                    f"Goal: {goal}\n{spec}\n{files_ctx}\n\n"
                    "Output a short approach (2-3 sentences) then a JSON array of file changes. "
                    "Format: {\"approach\": \"...\", \"changes\": [{\"path\": \"rel/path\", \"action\": \"edit\" or \"create\", \"description\": \"what to do\"}]}. "
                    "Only include the JSON object, no markdown."
                )
                async with ctx.model_limiter:
                    agent = Agent(model=ctx.model)
                    result = await agent.run(design_prompt)
                raw = result.output if hasattr(result, "output") else str(result)
                _append_llm_trace(ctx, "design", design_prompt, raw)
                raw = raw.strip()
                if "```" in raw:
                    raw = raw.split("```")[1].replace("json", "").strip()
                try:
                    design = json.loads(raw)
                    state["design"] = design
                    if hasattr(ctx, "workbench_run_state"):
                        ctx.workbench_run_state.update(state)
                except json.JSONDecodeError:
                    state["design"] = {"approach": raw[:500], "changes": []}
                    if hasattr(ctx, "workbench_run_state"):
                        ctx.workbench_run_state.update(state)
                approach = design.get("approach", "")[:300]
                changes = design.get("changes", [])
                t.status = "done"
                return f"{t.id} done: design\n{approach}\nchanges: {len(changes)} files"
            t.status = "done"
            return f"{t.id} done: design (no model)"

        if t.kind == "implement":
            candidates = []
            for prev in ctx.task_queue.list():
                if prev.kind == "search" and prev.meta.get("bm25_candidates"):
                    candidates = prev.meta["bm25_candidates"]
                    break
            state = getattr(ctx, "workbench_run_state", None) or {}
            if not candidates:
                candidates = state.get("search_bm25_hits") or []
            if not candidates:
                bm = await ctx.subagents.get("bm25").run(ctx, input=str(t.input), meta={"k": 20})
                candidates = bm.output or []
            design = state.get("design") or {}
            strategy = (design.get("approach") or "").strip() if isinstance(design, dict) else None
            out = await _implement_in_worktree(ctx, str(t.input), candidates, strategy=strategy, task_id=t.id)
            t.status = "done"
            return f"{t.id} done: implement\n{out}"

        if t.kind == "gates":
            try:
                from agent_ext.self_improve.gates import run_gates
                from agent_ext.self_improve.models import GatePlan
            except ImportError:
                t.status = "done"
                return f"{t.id} done: gates (self_improve not available)"
            gates = run_gates(GatePlan(import_check=True, compile_check=True, pytest_paths=[]))
            t.status = "done"
            return f"{t.id} done: gates\nok={gates.ok}\n{gates.details}"

        # Unknown task kind
        t.status = "done"
        return f"{t.id} done: {t.kind} (stub)"

    except Exception as e:
        t.status = "failed"
        return f"{t.id} failed: {e!r}"


def _run_worker(
    ctx,
    results: List[str],
    results_lock: asyncio.Lock,
    progress_callback: Optional[Any] = None,
) -> None:
    """Single worker: repeatedly claim and run next task until queue empty (OpenCode-style parallel units of work)."""
    async def _run() -> None:
        while True:
            out = await run_next_task(ctx)
            if out == "no pending tasks":
                break
            async with results_lock:
                results.append(out)
            if progress_callback is not None and callable(progress_callback):
                try:
                    progress_callback(out)
                except Exception:
                    pass

    return _run


async def run_n_tasks(
    ctx,
    n: int,
    *,
    progress_callback: Optional[Any] = None,
) -> List[str]:
    """Run with n concurrent workers until queue is empty. Each worker claims and runs tasks atomically (OpenCode-style).
    If progress_callback is set, it is called with each task output string as tasks complete (live stream, Cursor/Claude Code style)."""
    workers = max(1, n)
    results: List[str] = []
    results_lock = asyncio.Lock()
    worker_factory = _run_worker(ctx, results, results_lock, progress_callback)
    await asyncio.gather(*[worker_factory() for _ in range(workers)])
    return results
