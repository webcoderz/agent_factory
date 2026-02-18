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

This will already feel like: goal → plan → concurrent repo scans → iterative execution.