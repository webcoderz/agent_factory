# Fully automated self-improving code agent

Goal: run with **no intervention** — test, push to a branch, store state (optionally on GitHub), and **deconflict** when multiple people or runners submit PRs.

---

## What you already have

- **Auto-adopt**: Workbench loop and cog `loop_v2` apply patch → run gates → commit & push when `AUTO_ADOPT=1` and score ≥ threshold.
- **Worktrees**: Isolated branches per run (`auto/<run_id>/<agent>`); patches applied in worktree, then diff applied to main tree.
- **Gates**: Import check, compile check, optional pytest (set `pytest_paths` in GatePlan).
- **Push**: `adopt.commit_and_push(message, branch=AUTO_PUSH_BRANCH)` pushes to `origin/<branch>`.
- **Cog state**: `CogState` + `RegressionMemory` in `.agent_state/` (local); anti-thrash and fail_streak.
- **Locks**: `LeaseLockStore` in `.agent_state/locks/` (local, single-machine).

---

## What’s needed (checklist)

### 1. Headless daemon entry point (no TUI)

- **Run the cog loop** (`loop_v2.run_cognitive_cycle`) in a loop with `run_forever` in `agent_ext.cog.daemon`.
- **Same ctx as workbench**: Use `build_ctx()` so the daemon has model, subagents, search, `cog_state`, `regression_memory`.
- **Load .env** at daemon startup (e.g. in a `__main__` for `agent_ext.cog.daemon` or a single `agent_ext.run` entry).
- **Env vars**: `AGENT_LOOP_SLEEP`, `AGENT_DAEMON_GOAL`, `COG_*`, `AUTO_ADOPT`, `AUTO_PUSH_BRANCH`, `AUTO_COMMIT_THRESHOLD`, `LLM_*`.

### 2. Test before push (already there, tighten)

- In `loop_v2` and workbench implement path, gates already run (import + compile + optional pytest).
- Ensure **pytest** runs when you have `tests/`: set `GatePlan(pytest_paths=["tests"])` when appropriate (e.g. from env `RUN_PYTEST=1` or if `tests/` exists).

### 3. Push to “its” branch

- **Single shared branch**: `AUTO_PUSH_BRANCH=dev` — all runners push to `dev`; need pull-before-push and conflict handling.
- **Per-runner branch** (recommended for multi-actor): e.g. `AUTO_PUSH_BRANCH=auto/$(hostname)` or `auto/$RUNNER_ID`. Each runner pushes to its own branch; humans or a bot open PRs from these branches. No direct overwrites; conflicts only at PR merge.

### 4. Pull before push (deconflict with others)

- Before `commit_and_push`: **fetch** and **merge** (or **rebase**) `origin/<branch>` into current branch so you push on top of latest.
- If merge/rebase has **conflicts**: abort commit, leave working tree clean (e.g. `git merge --abort` / `git rebase --abort`), optionally back off and retry later.
- If **push** fails (e.g. non–fast-forward): pull again (merge/rebase), retry push once or twice; then back off and retry next cycle.

### 5. Store state on GitHub

- **Option A – Same repo, state branch**: Push `.agent_state` (or a subset: `cog_state.json`, `regression_memory.json`, `patches/`) to a branch like `agent-state/main` or `agent-state/<runner_id>`. Other runners pull this branch to sync state (with the same conflict rules as code).
- **Option B – State in working branch**: Commit `.agent_state` on the same branch you push code to (e.g. `dev`). Simpler; state and code evolve together; merge conflicts can include state files.
- **Option C – External store**: GitHub API, separate repo, or key-value store. More work; use if you need stronger consistency or multi-repo.

### 6. Multi-actor deconflict (multiple people + PRs)

- **Pull before push** (above) so each runner integrates others’ commits before pushing.
- **Per-runner branches** so each agent has its own ref; no direct conflict on the same branch.
- **Distributed lock** (optional): To allow only one runner to commit at a time, use a lock that all runners see (e.g. a file in the repo or a branch like `lock/agent` that you create/delete via Git, or an external lock service). Current `LeaseLockStore` is local only.
- **PR workflow**: Humans (or a bot) merge PRs from `auto/<runner>` into `main`/`dev`. Branch protection and CI on the target branch enforce tests and review; the agent only pushes to its own branch.

### 7. No intervention

- Daemon runs **forever** (`run_forever`), loads **.env** once at startup, uses **same build_ctx** (model, search, subagents, gates).
- On errors: log and **back off** (e.g. longer sleep), don’t crash; next cycle will fetch latest and try again.

---

## Env vars (summary)

| Var | Purpose |
|-----|--------|
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Model for llm_patch / analyze / design |
| `AUTO_ADOPT` | 1 = auto commit & push after gates pass |
| `AUTO_PUSH_BRANCH` | Branch to push to (e.g. `dev` or `auto/$(hostname)`) |
| `AUTO_COMMIT_THRESHOLD` | Min score (0–100) to auto-adopt |
| `AGENT_LOOP_SLEEP` | Seconds between daemon cycles |
| `AGENT_DAEMON_GOAL` | Default goal for cog loop |
| `COG_MAX_STEPS`, `COG_MAX_MODEL_CALLS`, `COG_MAX_PARALLEL_WRITERS` | Cog budget |
| `MAX_DIFF_CHARS` | Max diff size to consider |
| `RUNNER_ID` or hostname | Optional: for per-runner branch names |

---

## Suggested order of implementation

1. **Daemon entry point**: `python -m agent_ext.cog.daemon` (or similar) that loads `.env`, builds ctx with model, runs `run_forever(ctx)`.
2. **adopt.py**: Add `fetch_and_merge_origin(branch)` (or rebase) before commit; on merge conflict, abort and return error; in `commit_and_push` catch push failure, pull again, retry.
3. **Per-runner branch**: Set `AUTO_PUSH_BRANCH=auto/$(RUNNER_ID)` or `auto/$(hostname)` when running multiple agents.
4. **State on GitHub**: Option B (commit `.agent_state` on same branch) or Option A (dedicated `agent-state` branch) and pull/push it in the daemon.

After that, add optional distributed lock and/or PR-bot integration if you need stricter single-writer or automated PR creation.

---

## Recommendations: multiple people running at once

To **ensure correct merging of state, code, and branches** when many people (or machines) run the agent concurrently:

### 1. **Per-runner branches (strongly recommended)**

- **Code:** Each runner uses a **unique branch** for its commits, e.g. `auto/$RUNNER_ID` or `auto/$(hostname)`.
- **Why:** No two runners push to the same ref → no direct push conflicts. Conflicts only happen when a human/bot merges a PR from `auto/alice` into `main`/`dev`, and that’s a single place to resolve.
- **How:** Set `RUNNER_ID` (or derive from hostname) and `AUTO_PUSH_BRANCH=auto/$RUNNER_ID` in each runner’s env. Document in `.env.example`.

### 2. **State: keep it per-runner (simplest and safe)**

- **Option A – Per-runner state branch:** e.g. `agent-state/$RUNNER_ID`. Each runner pushes/pulls only its own state. No state merge conflicts between people.
- **Option B – State on same branch as code:** Commit `.agent_state` on `auto/$RUNNER_ID` along with code. Again, no cross-runner state conflict.
- **Recommendation:** Start with **per-runner state** (A or B). No need to merge state files between runners; each agent has its own cog_state and regression_memory.

### 3. **If you want shared state (one learning corpus)**

- Use a **single state branch** (e.g. `agent-state/main`) that all runners push to and pull from.
- **Merge strategy:**
  - **Pull-before-push:** Before writing state, fetch and merge `origin/agent-state/main` into your local state branch (same as code in `adopt.py`). Then commit and push.
  - **Conflict resolution:** State files (JSON) can conflict. Options:
    - **Last-write-wins:** On pull, if remote state is newer (by commit timestamp or a field in the file), overwrite local and push. Simple but can drop one runner’s updates.
    - **Key-wise merge:** Implement a merge for `regression_memory.json` (e.g. merge by file path / commit) and for `cog_state.json` (e.g. take max fail_streak, merge timestamps). More work, preserves more information.
    - **Short-lived lock:** A file or branch that acts as a lock (e.g. `lock/agent` or a blob on GitHub); only one runner writes state at a time. Easiest to reason about; serializes state updates.

### 4. **Code merge (already in place)**

- **Pull before push** in `adopt.py` (fetch + merge/rebase) ensures each runner’s branch is based on latest `origin/auto/$RUNNER_ID`. For per-runner branches, the only new commits on that branch are from that runner, so merge/rebase is usually trivial.
- When **merging a PR** from `auto/alice` into `dev`, the merge is done by a human or bot; conflict resolution is once per PR.

### 5. **Concrete steps to support multiple people**

| Step | Action |
|------|--------|
| 1 | **Enforce RUNNER_ID:** In daemon/adopt, set `AUTO_PUSH_BRANCH=auto/${RUNNER_ID:-$(hostname)}` so every runner has a unique branch. |
| 2 | **Ensure branch exists:** Before first push, create `auto/$RUNNER_ID` from current `main`/`dev` if it doesn’t exist (e.g. `git push -u origin HEAD:auto/$RUNNER_ID`). |
| 3 | **State (per-runner):** Optional env `AGENT_STATE_BRANCH=agent-state/$RUNNER_ID`. At daemon start: pull that branch (or create it), restore `.agent_state` from it if present. After successful adopt: commit `.agent_state` and push to that branch. |
| 4 | **State (shared):** If you later add `agent-state/main`, add a small “state sync” that pull/merges state (last-write-wins or key-merge), then push; optionally use a lock to avoid conflicting state pushes. |

### 6. **Single shared learning state, but don’t merge state with code**

You want one shared learning state, and when a PR from `auto/alice` is merged into `main` or `dev`, you **do not** want Alice’s local `.agent_state` to be merged in — only her code.

**Recommended: state never lives on the code branch**

- **Code branch** (`auto/$RUNNER_ID`): Runners commit and push **only code**. Do **not** commit `.agent_state` on this branch.
- **State branch** (`agent-state/main`): All runners pull/push **only state** (e.g. `cog_state.json`, `regression_memory.json`, and any other shared state files) to this branch.
- When you merge `auto/alice` → `main`/`dev`, the PR has no state files, so nothing to exclude. Main/dev never get runner-specific state.

**How to enforce “no state on code branch”**

- In the agent: when adopting, **commit only code** to the code branch (no `git add .agent_state` there). Separately, sync state to `agent-state/main` (e.g. clone/fetch that branch, copy `.agent_state` into it, commit, push). So code and state are always pushed to different branches.
- Optionally keep **`.agent_state/` in `.gitignore`** on the code branch so a mistaken `git add -A` doesn’t add state. (Your repo already ignores most of `.agent_state`; you can keep or tighten that so no state is tracked on code branches.)

**If state ever gets committed on a runner’s branch: merge rule so main/dev don’t take it**

If a runner has already committed `.agent_state` on `auto/alice` and you merge that PR into `main`/`dev`, Git would normally merge those files. To **discard** incoming state and keep main’s version (or leave main without those files), use a **custom merge driver** on `main`/`dev`:

1. **Define a “keep ours” merge driver** (run once per repo, or document for maintainers):

   ```bash
   git config merge.keep-ours.name "keep our version (ignore incoming)"
   git config merge.keep-ours.driver "true"
   ```

   (`true` exits 0 and keeps the current branch’s version; the incoming changes are not applied.)

2. **In the repo root, `.gitattributes`** (already in repo) contains:

   ```
   .agent_state/** merge=keep-ours
   ```
   Commit this on `main`/`dev` so all merges into those branches use it.

3. When you merge `auto/alice` into `main`, Git will use `keep-ours` for any path under `.agent_state/`: it keeps main’s version and ignores Alice’s. So her local state is not merged in.

**Summary**

| Goal | Approach |
|------|----------|
| Shared learning state | All runners push/pull state to `agent-state/main` only. |
| Code PRs don’t merge state | Don’t commit `.agent_state` on code branches; state lives only on `agent-state/main`. |
| Safety net if state was committed on a branch | On main/dev, set `merge=keep-ours` for `.agent_state/**` in `.gitattributes` and define the `keep-ours` merge driver so merges into main/dev never take state from the PR. |

### 7. **Summary**

- **Multiple people, no shared state:** Per-runner code branch + per-runner state (branch or on same branch). No state merge logic; no code conflict between runners.
- **Multiple people, shared state:** Per-runner code branch + shared state branch with pull-before-push and a clear merge/lock strategy (last-write-wins, key-merge, or lock). **Do not commit state on the code branch** so merging PRs into main/dev never merges in local state.
- **Merge rule:** Use `.gitattributes` with `merge=keep-ours` for `.agent_state/**` on main/dev so that if state was ever committed on a runner branch, it is not merged into main/dev.
