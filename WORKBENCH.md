set these:
export LLM_BASE_URL="http://127.0.0.1:8000/v1"
export LLM_API_KEY="local"
export LLM_MODEL="gpt-oss-120b"


uv sync --extra docs --extra agent
python -m agent_ext.workbench --use-openai-chat-model --max-parallel-subagents 6 --max-parallel-model-calls 2

In the TUI

- type: build me self improving code agent

- it queues tasks

- run: /run 3

- view: /tasks

- adjust parallel: /parallel 8

- LLM trace streams during implement; for DAG/streaming hooks use `agent_ext.workbench.streaming` (`run_agent_streaming`, `iter_agent_dag`).

This will already feel like: goal → plan → concurrent repo scans → iterative execution.

---

**Fully automated (no TUI)**  
See `docs/AUTO_AGENT.md` for design. Run the daemon:

  export USE_OPENAI_CHAT_MODEL=1
  python -m agent_ext.cog [--use-openai-chat-model]

Set `AUTO_ADOPT=1` and `AUTO_PUSH_BRANCH` (e.g. `dev` or `auto/$(hostname)`) to auto-commit and push after gates. Adopt pulls before push and retries on conflict (see `.env.example`).