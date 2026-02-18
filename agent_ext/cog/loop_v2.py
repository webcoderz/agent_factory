from __future__ import annotations
import os, time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .state import Budget, CogState, RegressionMemory
from .triggers import detect_triggers, repo_fingerprint
from .modes import choose_mode
from .strategy_bank import pick_strategies
from .scorer import score_candidate

# You already have these pieces:
# - create_worktree / cleanup_worktree
# - worktree_diff
# - apply_unified_diff
# - run_gates / GatePlan
# - your llm_patch subagent which accepts strategy hints

from agent_ext.workbench.worktrees import create_worktree, cleanup_worktree, worktree_diff
from agent_ext.self_improve.patching import apply_unified_diff
from agent_ext.self_improve.gates import run_gates
from agent_ext.self_improve.models import GatePlan

def _diff_touched_files(diff_text: str) -> List[str]:
    files = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                b = parts[3].replace("b/", "")
                files.append(b)
    return sorted(set(files))

async def run_cognitive_cycle(ctx, goal: str, budget: Budget) -> Dict[str, Any]:
    state: CogState = ctx.cog_state
    reg: RegressionMemory = ctx.regression_memory

    triggers = detect_triggers(state.last_repo_fingerprint)

    # BM25 confidence: how sharp is the distribution?
    hits = ctx.search.search(goal, top_k=20)
    bm25_conf = 0.0
    if hits:
        top = hits[0][1]
        tenth = hits[min(9, len(hits)-1)][1]
        bm25_conf = float(top / (top + tenth + 1e-9))

    mode = choose_mode(fail_streak=state.fail_streak, triggers=triggers, bm25_confidence=bm25_conf)

    # Pick candidates (paths) and pass snippets to patcher
    candidates = [{"path": p, "score": float(s)} for p, s in hits[: mode.max_files]]

    # Parallel writers (each in its own worktree)
    strategies = pick_strategies(mode.parallel_writers)

    results = []
    for strat in strategies:
        wt = create_worktree(run_id=ctx.session_id, agent_name=f"writer_{strat.name}")
        try:
            patcher = ctx.subagents.get("llm_patch")
            res = await patcher.run(
                ctx,
                input=goal,
                meta={
                    "workdir": str(wt.path),
                    "candidates": candidates,
                    "max_files": mode.max_files,
                    "strategy": strat.prompt_style,   # your patcher should incorporate this into prompt
                },
            )
            if not res.ok:
                results.append({"strategy": strat.name, "ok": False, "err": res.meta})
                continue

            ok_apply, out_apply = apply_unified_diff(res.output, repo_root=wt.path)
            if not ok_apply:
                results.append({"strategy": strat.name, "ok": False, "err": f"apply_failed: {out_apply[:400]}"})
                continue

            plan = GatePlan(import_check=True, compile_check=True, pytest_paths=(["tests"] if mode.pytest else []))
            gates = run_gates(plan)

            diff = worktree_diff(wt)
            touched = _diff_touched_files(diff)

            # hard cap
            if len(diff) > budget.max_diff_chars:
                results.append({"strategy": strat.name, "ok": False, "err": f"diff_too_large: {len(diff)}"})
                continue

            results.append({
                "strategy": strat.name,
                "ok": True,
                "gates_ok": gates.ok,
                "diff": diff,
                "diff_chars": len(diff),
                "files": touched,
            })

        finally:
            cleanup_worktree(wt, prune_branch=False)

    # Select winner
    scored = []
    for r in results:
        if not r.get("ok") or "diff" not in r:
            continue
        sc = score_candidate(
            gates_ok=bool(r.get("gates_ok")),
            diff_chars=int(r.get("diff_chars", 0)),
            files_touched=len(r.get("files", [])),
            eval_delta=0.0,  # wire evals later
        )
        scored.append((sc.score, sc, r))

    if not scored:
        state.fail_streak += 1
        state.save()
        return {"ok": False, "mode": mode.name, "reason": "no_valid_candidates", "raw": results}

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_sc, best_r = scored[0]

    # Anti-thrash: block if files flip too often
    if reg.is_thrash_risk(best_r["files"]):
        state.fail_streak += 1
        state.save()
        return {"ok": False, "mode": mode.name, "reason": "thrash_risk", "files": best_r["files"], "score": best_score}

    # Decide auto-commit
    auto = bool(int(os.getenv("AUTO_ADOPT", "1")))
    threshold = float(os.getenv("AUTO_COMMIT_THRESHOLD", str(budget.auto_commit_threshold)))

    # Persist patch artifact
    patches_dir = Path(".agent_state/patches") / ctx.session_id
    patches_dir.mkdir(parents=True, exist_ok=True)
    patch_path = patches_dir / f"{best_r['strategy']}.diff"
    patch_path.write_text(best_r["diff"], encoding="utf-8")
    (Path(".agent_state/last_patch_path.txt")).write_text(str(patch_path), encoding="utf-8")

    if not best_sc.ok or best_score < threshold or not auto:
        state.fail_streak += (0 if best_sc.ok else 1)
        state.save()
        return {
            "ok": True,
            "adopted": False,
            "mode": mode.name,
            "score": best_score,
            "patch": str(patch_path),
            "files": best_r["files"],
            "reasons": best_sc.reasons,
        }

    # Auto-adopt into current working tree (dev) + commit/push
    from agent_ext.workbench.adopt import apply_diff_to_repo, commit_and_push
    apply_diff_to_repo(best_r["diff"], repo_root=Path("."))

    main_plan = GatePlan(import_check=True, compile_check=True, pytest_paths=(["tests"] if mode.pytest else []))
    main_gates = run_gates(main_plan)
    if not main_gates.ok:
        state.fail_streak += 1
        state.save()
        return {"ok": False, "mode": mode.name, "reason": "main_gates_failed_after_adopt", "patch": str(patch_path)}

    msg = f"auto[{mode.name}/{best_r['strategy']}]: {goal[:72]}"
    commit_and_push(message=msg, branch=os.getenv("AUTO_PUSH_BRANCH", "dev"), repo_root=Path("."))

    reg.note_commit(best_r["files"], msg)
    reg.save()

    state.fail_streak = 0
    state.last_success_ts = time.time()
    state.last_repo_fingerprint = repo_fingerprint()
    state.save()

    return {
        "ok": True,
        "adopted": True,
        "mode": mode.name,
        "score": best_score,
        "patch": str(patch_path),
        "files": best_r["files"],
        "reasons": best_sc.reasons,
        "commit_msg": msg,
    }
