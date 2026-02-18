"""
Headless daemon entry point for fully automated self-improving agent.

Usage:
  export LLM_BASE_URL=... LLM_API_KEY=... LLM_MODEL=...
  export USE_OPENAI_CHAT_MODEL=1   # or pass --use-openai-chat-model
  python -m agent_ext.cog [--use-openai-chat-model]

Runs the cognitive loop forever: plan → patch → gates → (optional) adopt & push.
See docs/AUTO_AGENT.md and .env.example for env vars.
"""
from __future__ import annotations

import argparse
import asyncio
import os

from dotenv import find_dotenv, load_dotenv

# Load .env so LLM_*, AUTO_*, COG_*, AGENT_* are set
load_dotenv(find_dotenv())

from agent_ext.workbench.models import build_openai_chat_model, model_from_env
from agent_ext.workbench.runtime import build_ctx
from agent_ext.cog.daemon import run_forever


def main() -> None:
    ap = argparse.ArgumentParser(description="Run self-improving agent daemon (no TUI)")
    ap.add_argument("--use-openai-chat-model", action="store_true", help="Use OpenAI-compatible chat model from env")
    ap.add_argument("--max-parallel-subagents", type=int, default=None, help="Max concurrent subagents (default from env or 4)")
    ap.add_argument("--max-parallel-model-calls", type=int, default=None, help="Max concurrent model calls (default from env or 2)")
    ap.add_argument("--case-id", default=os.getenv("AGENT_CASE_ID", "daemon-1"))
    ap.add_argument("--session-id", default=os.getenv("AGENT_SESSION_ID", "sess-1"))
    ap.add_argument("--user-id", default=os.getenv("AGENT_USER_ID", "user-1"))
    args = ap.parse_args()

    use_model = args.use_openai_chat_model or bool(os.getenv("USE_OPENAI_CHAT_MODEL", "").strip().lower() in ("1", "true", "yes"))
    model = None
    if use_model:
        cfg = model_from_env()
        model = build_openai_chat_model(cfg)
        print(f"[daemon] model={cfg.model} base_url={cfg.base_url}")

    max_sub = args.max_parallel_subagents if args.max_parallel_subagents is not None else int(os.getenv("MAX_PARALLEL_SUBAGENTS", "4"))
    max_llm = args.max_parallel_model_calls if args.max_parallel_model_calls is not None else int(os.getenv("MAX_PARALLEL_MODEL_CALLS", "2"))
    ctx = build_ctx(
        case_id=args.case_id,
        session_id=args.session_id,
        user_id=args.user_id,
        model=model,
        max_parallel_subagents=max_sub,
        max_parallel_model_calls=max_llm,
    )

    asyncio.run(run_forever(ctx))


if __name__ == "__main__":
    main()
