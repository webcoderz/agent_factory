from __future__ import annotations

import asyncio
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .loop import plan_and_queue, run_next_task

console = Console()


def _tasks_table(ctx) -> Table:
    t = Table(title="Task Queue")
    t.add_column("id", style="bold")
    t.add_column("kind")
    t.add_column("status")
    t.add_column("title")
    for task in ctx.task_queue.list():
        t.add_row(task.id, task.kind, task.status, task.title)
    return t


async def _ainput(prompt: str) -> str:
    # Rich input is blocking; run it in a thread so we can keep an async loop.
    return await asyncio.to_thread(console.input, prompt)


async def run_tui(ctx) -> None:
    console.print(Panel.fit("agent_patterns workbench (async)\n/help for commands, /quit to exit"))

    while True:
        msg = (await _ainput("[bold cyan]you> [/bold cyan]")).strip()
        if not msg:
            continue

        if msg in ("/quit", "/exit"):
            console.print("bye")
            return

        if msg == "/help":
            console.print(Panel(
                "\n".join([
                    "/help",
                    "/status",
                    "/agents",
                    "/tasks",
                    "/plan <goal>",
                    "/run",
                    "/run N",
                    "/parallel <n>",
                    "/model",
                    "/workflows",
                    "/assemble <task_type> <text>",
                    "/exec <task_type> <text>",
                    "/quit",
                ]),
                title="commands"
            ))
            continue

        if msg == "/status":
            console.print(Panel(f"case={ctx.case_id} session={ctx.session_id} user={ctx.user_id}"))
            continue

        if msg == "/agents":
            console.print(Panel("\n".join(ctx.subagents.list()), title="subagents"))
            continue

        if msg == "/tasks":
            console.print(_tasks_table(ctx))
            continue

        if msg.startswith("/parallel "):
            try:
                n = int(msg.split(" ", 1)[1].strip())
                ctx.max_parallel_subagents = max(1, n)
                console.print(Panel(f"max_parallel_subagents={ctx.max_parallel_subagents}"))
            except Exception:
                console.print(Panel("usage: /parallel 4"))
            continue

        if msg == "/model":
            console.print(Panel(f"model={'set' if ctx.model else 'none'}; model_calls_parallel={ctx.model_limiter._sem._value if hasattr(ctx.model_limiter, '_sem') else 'n/a'}"))
            continue

        if msg.startswith("/plan "):
            goal = msg.split(" ", 1)[1].strip()
            lines = await plan_and_queue(ctx, goal)
            console.print(Panel("\n".join(lines), title="plan"))
            continue

        if msg.startswith("/run"):
            parts = msg.split()
            count = 1
            if len(parts) == 2:
                try:
                    count = int(parts[1])
                except Exception:
                    count = 1

            outs = []
            for _ in range(max(1, count)):
                outs.append(await run_next_task(ctx))

            console.print(Panel("\n\n".join(outs), title="run"))
            continue

        if msg == "/workflows":
            names = ctx.workflow_registry.list_workflows()
            console.print(Panel("\n".join(names) if names else "none", title="workflows"))
            continue

        if msg.startswith("/assemble "):
            # /assemble ocr extract text from this pdf
            rest = msg.split(" ", 2)
            if len(rest) < 3:
                console.print(Panel("usage: /assemble <task_type> <text>"))
                continue
            task_type, text = rest[1], rest[2]
            req = __import__("agent_ext.workflow.types", fromlist=["TaskRequest"]).TaskRequest(
                text=text,
                task_type=task_type,
                hints=("needs_planning", "needs_memory") if task_type == "ocr" else ("needs_planning",),
            )
            wf = ctx.workflow_planner.choose(ctx, req)
            console.print(Panel(f"chosen workflow: {wf.name}\nsteps: {[s.component_name for s in wf.steps]}"))
            continue

        if msg.startswith("/exec "):
            rest = msg.split(" ", 2)
            if len(rest) < 3:
                console.print(Panel("usage: /exec <task_type> <text>"))
                continue
            task_type, text = rest[1], rest[2]
            from agent_ext.workflow.types import TaskRequest

            req = TaskRequest(
                text=text,
                task_type=task_type,
                hints=("needs_planning", "needs_memory") if task_type == "ocr" else ("needs_planning",),
            )
            wf = ctx.workflow_planner.choose(ctx, req)
            result = await ctx.workflow_executor.execute(ctx, wf, req)

            # reward: success and speed (simple starter)
            # reward in [0,1]: ok=1 else 0; subtract small penalty for slow
            reward = (1.0 if result.ok else 0.0) - min(0.5, result.metrics.get("dt_ms", 0) / 60_000.0)
            ctx.workflow_experience.record(req, result, reward)
            ctx.workflow_planner.observe(req, wf.name, reward)

            console.print(Panel(
                f"ok={result.ok}\nworkflow={result.workflow_name}\nreward={reward:.3f}\noutputs={result.outputs}\ntrace={result.trace}",
                title="execution"
            ))
            continue



        # Plain chat message = treat as goal (fast UX)
        lines = await plan_and_queue(ctx, msg)
        console.print(Panel("\n".join(lines), title="plan"))
