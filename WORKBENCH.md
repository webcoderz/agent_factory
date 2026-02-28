set these:
export LLM_BASE_URL="http://127.0.0.1:8000/v1"
export LLM_API_KEY="local"
export LLM_MODEL="gpt-oss-120b"


uv sync --extra docs --extra agent
python -m agent_ext.workbench --use-openai-chat-model --max-parallel-subagents 6 --max-parallel-model-calls 2

In the TUI (agentic, non-blocking — like OpenCode / Claude Code)

- Type a goal or `/plan <goal>`: planning runs in background; prompt returns immediately. **Plans are dynamic** when you use `--use-openai-chat-model`: the LLM chooses the task sequence (e.g. skip analyze for small edits, add multiple search steps). Without a model, a fixed plan (analyze → search → design → implement → gates) is used.
- try: 'build me a self improving code agent'
- **Live like Cursor/Claude Code:** When you `/run`, task completions stream in real time. Use **`/watch`** to pop up a live-updating view (recent task output + LLM trace); it refreshes until you press Enter to leave. **`/watch t0003`** opens the same view and highlights that you’re watching for that task. When a run finishes, the panel shows the patch path and `/adopt` if implement ran.
- **OpenCode-style parallel execution:** `/run N` starts N **concurrent workers** that drain the task queue. You can start many runs; task completions stream below. Use `/status`, `/traces`, `/stop` while runs are in progress.
- `/ask <question>`: one-off LLM question in background; answer prints when ready.
- To watch one run block with live trace: `/run N fg` (runs N tasks sequentially with spinner). `/status` shows how many runs are in progress and queue counts.
- `/stop`: cancel the most recent background run. `/stop all`: cancel all background runs. Interrupt at any time.

- **Concurrency:** `/parallel 8` sets max concurrent subagent calls per task. `/run N` sets N parallel workers per run (queue is drained by N workers; same idea as OpenCode’s “run multiple units of work in parallel”).

- LLM trace streams during implement; for DAG/streaming hooks use `agent_ext.workbench.streaming` (`run_agent_streaming`, `iter_agent_dag`).

This will already feel like: goal → plan → concurrent repo scans → iterative execution.

---

**Fully automated (no TUI)**  
See `docs/AUTO_AGENT.md` for design. Run the daemon:

  export USE_OPENAI_CHAT_MODEL=1
  python -m agent_ext.cog [--use-openai-chat-model]

Set `AUTO_ADOPT=1` and `AUTO_PUSH_BRANCH` (e.g. `dev` or `auto/$(hostname)`) to auto-commit and push after gates. Adopt pulls before push and retries on conflict (see `.env.example`).