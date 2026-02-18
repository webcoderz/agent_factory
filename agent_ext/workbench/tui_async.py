from __future__ import annotations

import asyncio
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

from .loop import plan_and_queue, run_next_task

# Slightly custom theme: keep default but ensure status colors pop
console = Console(theme=Theme({"info": "cyan", "success": "green", "warn": "yellow", "error": "red", "dim": "dim"}))

BANNER = """
[bold cyan]  ╭─────────────────────────────────────╮
  │  [bold white]agent_patterns[/bold white] [dim]workbench[/dim]        │
  ╰─────────────────────────────────────╯[/bold cyan]
[dim]  plan → search → design → implement → gates[/dim]
"""

# Which subagents run for each task kind (for display)
TASK_SUBAGENTS = {
    "analyze": "LLM (clarify goal)",
    "search": "repo_grep, bm25",
    "design": "LLM (approach + file list)",
    "implement": "llm_patch (worktree)",
    "gates": "import_check, compile_check",
}


def _status_style(status: str) -> str:
    if status == "done":
        return "green"
    if status == "in_progress":
        return "yellow"
    if status == "failed":
        return "red"
    return "dim"


def _tasks_table(ctx) -> Table:
    t = Table(title="[bold]Task Queue[/bold]", title_style="bold white", border_style="dim")
    t.add_column("id", style="bold cyan")
    t.add_column("kind", style="magenta")
    t.add_column("status", style=None)
    t.add_column("title", style="white")
    for task in ctx.task_queue.list():
        t.add_row(
            task.id,
            task.kind,
            f"[{_status_style(task.status)}]{task.status}[/]",
            task.title,
        )
    return t


async def _ainput(prompt: str) -> str:
    # Rich input is blocking; run it in a thread so we can keep an async loop.
    return await asyncio.to_thread(console.input, prompt)


async def run_tui(ctx) -> None:
    # Start MCP server now that the event loop is running (cannot start in build_ctx)
    ctx.mcp_server.start()
    console.print(BANNER)
    console.print(Panel.fit(
        "[bold]/help[/] commands  [bold]/plan <goal>[/]  [bold]/run[/]  [bold]/quit[/]",
        border_style="cyan",
        padding=(0, 1),
    ))

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
                    "[cyan]/help[/]     this",
                    "[cyan]/status[/]   case/session",
                    "[cyan]/agents[/]   list subagents",
                    "[cyan]/tasks[/]    task queue",
                    "[cyan]/plan <goal>[/]  queue plan",
                    "[cyan]/run[/] [dim]or[/] [cyan]/run N[/]  run next task(s)",
                    "[cyan]/parallel <n>[/]  max subagents",
                    "[cyan]/model[/]   model info",
                    "[cyan]/workflows[/]  list",
                    "[cyan]/assemble[/] [cyan]/exec[/]  workflow",
                    "[cyan]/adopt[/]   apply last patch",
                    "[cyan]/quit[/]    exit",
                ]),
                title="[bold]commands[/bold]",
                border_style="cyan",
            ))
            continue

        if msg == "/status":
            console.print(Panel(
                f"[bold]case[/]={ctx.case_id}  [bold]session[/]={ctx.session_id}  [bold]user[/]={ctx.user_id}",
                title="[bold]status[/bold]",
                border_style="dim",
            ))
            continue

        if msg == "/agents":
            agents = ctx.subagents.list()
            console.print(Panel(
                "\n".join(f"  [cyan]•[/] {a}" for a in agents),
                title="[bold]subagents[/bold]",
                border_style="cyan",
            ))
            continue

        if msg == "/adopt":
            from pathlib import Path
            from agent_ext.self_improve.patching import apply_unified_diff

            diff = Path(".agent_state/last_patch.diff").read_text(encoding="utf-8")
            ok, out = apply_unified_diff(diff, repo_root=Path("."))
            if not ok:
                console.print(Panel(f"adopt failed: {out}", title="adopt"))
                continue
            console.print(Panel(f"adopted patch", title="adopt"))
            continue
        if msg == "/tasks":
            console.print(_tasks_table(ctx))
            console.print("[dim]  ───[/dim]")
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
            model_status = "[green]set[/]" if ctx.model else "[red]none[/]"
            limiter = ctx.model_limiter._sem._value if hasattr(ctx.model_limiter, "_sem") else "n/a"
            console.print(Panel(f"model={model_status}  [dim]parallel slots=[/]{limiter}", title="[bold]model[/bold]", border_style="dim"))
            continue

        if msg.startswith("/plan "):
            goal = msg.split(" ", 1)[1].strip()
            lines = await plan_and_queue(ctx, goal)
            console.print(Panel("\n".join(lines), title="[bold]plan[/bold]", border_style="green"))
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
            for i in range(max(1, count)):
                # Show which task and subagents are about to run
                next_t = ctx.task_queue.next_pending()
                if next_t:
                    subagents_desc = TASK_SUBAGENTS.get(next_t.kind, "—")
                    console.print(
                        f"  [dim]⟳[/] [yellow]Running[/] [bold]{next_t.id}[/] [cyan]({next_t.kind})[/] "
                        f"[dim]→ {subagents_desc}[/]"
                    )
                out = await run_next_task(ctx)
                outs.append(out)
                if next_t and out.startswith(f"{next_t.id} done"):
                    console.print(f"  [green]✓[/] [dim]{next_t.id} done[/]")
                elif next_t and out.startswith(f"{next_t.id} failed"):
                    console.print(f"  [red]✗[/] [dim]{next_t.id} failed[/]")

            console.print()
            console.print(Panel("\n\n".join(outs), title="[bold]run[/bold]", border_style="yellow"))
            continue

        if msg == "/workflows":
            names = ctx.workflow_registry.list_workflows()
            body = "\n".join(f"  [cyan]•[/] {n}" for n in names) if names else "[dim]none[/]"
            console.print(Panel(body, title="[bold]workflows[/bold]", border_style="dim"))
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
