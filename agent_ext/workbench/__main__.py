from __future__ import annotations

import argparse

from agent_ext.workbench.models import build_openai_chat_model, model_from_env
from agent_ext.workbench.runtime import build_ctx
from agent_ext.workbench.tui_async import run_tui

import asyncio
import os

max_sub = int(os.getenv("MAX_PARALLEL_SUBAGENTS", "4"))
max_llm = int(os.getenv("MAX_PARALLEL_MODEL_CALLS", "2"))

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-id", default="case-1")
    ap.add_argument("--session-id", default="sess-1")
    ap.add_argument("--user-id", default="user-1")
    ap.add_argument("--use-openai-chat-model", action="store_true")
    ap.add_argument("--max-parallel-subagents", type=int, default=4)
    ap.add_argument("--max-parallel-model-calls", type=int, default=2)
    args = ap.parse_args()

    model = None
    if args.use_openai_chat_model:
        cfg = model_from_env()
        model = build_openai_chat_model(cfg)
        print(f"[model] base_url={cfg.base_url} model={cfg.model}")

    ctx = build_ctx(
        case_id=args.case_id,
        session_id=args.session_id,
        user_id=args.user_id,
        model=model,
        max_parallel_subagents=args.max_parallel_subagents,
        max_parallel_model_calls=args.max_parallel_model_calls,
    )

    asyncio.run(run_tui(ctx))


if __name__ == "__main__":
    main()
