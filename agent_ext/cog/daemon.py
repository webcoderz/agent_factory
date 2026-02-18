from __future__ import annotations

import asyncio
import os
import random
import time
from dataclasses import dataclass

from agent_ext.cog.loop_v2 import run_cognitive_cycle
from agent_ext.cog.state import Budget


def _log(ctx, level: str, msg: str) -> None:
    if getattr(ctx, "logger", None):
        getattr(ctx.logger, level)(msg, **{})
    else:
        print(f"[daemon][{level}] {msg}")


@dataclass
class DaemonConfig:
    sleep_s: int = int(os.getenv("AGENT_LOOP_SLEEP", "30"))
    max_idle_s: int = int(os.getenv("AGENT_MAX_IDLE", "600"))
    goal: str = os.getenv("AGENT_DAEMON_GOAL", "keep improving the repo safely")


async def run_forever(ctx, *, cfg: DaemonConfig | None = None) -> None:
    cfg = cfg or DaemonConfig()

    budget = Budget(
        max_steps=int(os.getenv("COG_MAX_STEPS", "10")),
        max_model_calls=int(os.getenv("COG_MAX_MODEL_CALLS", "6")),
        max_parallel_writers=int(os.getenv("COG_MAX_PARALLEL_WRITERS", "3")),
        max_diff_chars=int(os.getenv("MAX_DIFF_CHARS", "60000")),
        auto_commit_threshold=float(os.getenv("AUTO_COMMIT_THRESHOLD", "80")),
    )

    cycle = 0
    while True:
        cycle += 1
        try:
            _log(ctx, "info", f"cycle {cycle}: goal={cfg.goal[:50]}...")
            out = await run_cognitive_cycle(ctx, cfg.goal, budget)

            adopted = bool(out.get("adopted", False))
            ok = bool(out.get("ok", False))
            mode = out.get("mode", "—")
            score = out.get("score")
            reason = out.get("reason", "")

            # Backoff logic: if nothing adopted, don’t thrash
            if adopted:
                _log(ctx, "info", f"cycle {cycle}: adopted patch (mode={mode})")
            elif not ok:
                _log(ctx, "warning", f"cycle {cycle}: not ok reason={reason}")
            else:
                _log(ctx, "info", f"cycle {cycle}: skipped (score={score}, no adopt)")

            if not ok or not adopted:
                delay = min(cfg.max_idle_s, cfg.sleep_s * 2)
            else:
                delay = cfg.sleep_s
            delay = delay + random.randint(0, 5)
            _log(ctx, "info", f"cycle {cycle}: sleeping {delay}s")
            await asyncio.sleep(delay)

        except Exception as e:
            if getattr(ctx, "logger", None):
                ctx.logger.error("daemon_error", error=repr(e))
            _log(ctx, "error", f"daemon_error: {e!r}")
            await asyncio.sleep(min(cfg.max_idle_s, cfg.sleep_s * 3) + random.randint(0, 10))


if __name__ == "__main__":
    # So "python -m agent_ext.cog.daemon" works the same as "python -m agent_ext.cog"
    from agent_ext.cog.__main__ import main
    main()
