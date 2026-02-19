from __future__ import annotations

import asyncio
import time
from typing import List, Optional

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
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
# Animated-looking rule (static; use Live elsewhere for motion)
BANNER_RULE_STYLE = "cyan dim"

# Spinner names: dots, dots12, line, aesthetic, runner, arc, etc. Run: python -m rich.spinner
RUN_SPINNER = "dots12"
LIVE_REFRESH_PER_SECOND = 10


class _LiveSpinner:
    """Renderable that shows an animated spinner; message_ref is a list so the caller can update the text. Implements __rich_console__ for Rich."""

    def __init__(
        self,
        message_ref: List[str],
        spinner_name: str = "dots12",
        style: str = "bold cyan",
        use_markup: bool = True,
    ):
        self._message_ref = message_ref
        self._spinner = Spinner(spinner_name, style=style)
        self._use_markup = use_markup

    def __rich_console__(self, console: Console, options):
        t = time.time()
        msg = self._message_ref[0] if self._message_ref else "Running..."
        text = Text.from_markup(" " + msg) if self._use_markup else Text(" " + msg)
        yield Group(self._spinner.render(t), text)


class _LiveTraceView:
    """Shows the most recent LLM trace. Implement (llm_patch) streams into the trace; analyze/design append after the full response."""

    def __init__(self, ctx, max_lines: int = 22):
        self._ctx = ctx
        self._max_lines = max_lines

    def __rich_console__(self, console: Console, options):
        traces = getattr(self._ctx, "llm_traces", [])
        if not traces:
            yield Panel("[dim]Waiting for LLM…[/]", title="[bold]LLM trace[/]", border_style="dim", padding=(0, 1))
            return
        entry = traces[-1]
        kind = entry.get("kind", "?")
        prompt = (entry.get("prompt") or "").strip()
        response = (entry.get("response") or "").strip()
        half = self._max_lines // 2
        prompt_lines = prompt.splitlines()[:half]
        response_lines = response.splitlines()[:half]
        prompt_preview = "\n".join(prompt_lines) + ("\n…" if len(prompt.splitlines()) > half else "")
        response_preview = "\n".join(response_lines) + ("\n…" if len(response.splitlines()) > half else "")
        body = f"[bold magenta]{kind}[/]\n[dim]in:[/] {prompt_preview}\n[dim]out:[/] {response_preview}"
        yield Panel(body, title="[bold]LLM trace[/]", border_style="magenta", padding=(0, 1))


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


def _format_llm_trace(entry: dict) -> str:
    kind = entry.get("kind", "?")
    prompt = entry.get("prompt", "")
    response = entry.get("response", "")
    return f"[bold magenta]{kind}[/]\n[dim]prompt:[/]\n{prompt}\n[dim]response:[/]\n{response}"


async def _ainput(prompt: str) -> str:
    # Rich input is blocking; run it in a thread so we can keep an async loop.
    return await asyncio.to_thread(console.input, prompt)


async def run_tui(ctx) -> None:
    # Start MCP server now that the event loop is running (cannot start in build_ctx)
    ctx.mcp_server.start()
    console.print(BANNER)
    console.print(Rule(style=BANNER_RULE_STYLE))
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
                    "[cyan]/traces[/] [dim][N][/]  last LLM prompt/response",
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

            state_dir = Path(".agent_state")
            path_file = state_dir / "last_patch_path.txt"
            if path_file.exists():
                diff_path = Path(path_file.read_text(encoding="utf-8").strip())
            else:
                diff_path = state_dir / "last_patch.diff"
            if not diff_path.exists():
                console.print(Panel(
                    "No saved patch. Run /run and complete an implement step first (patch is saved to .agent_state/patch_<run_id>.diff).",
                    title="adopt",
                    border_style="yellow",
                ))
                continue
            diff = diff_path.read_text(encoding="utf-8")
            ok, out = apply_unified_diff(diff, repo_root=Path("."))
            if not ok:
                console.print(Panel(f"adopt failed: {out}", title="adopt"))
                continue
            console.print(Panel(f"adopted patch from {diff_path}", title="adopt"))
            continue
        if msg == "/tasks":
            console.print(_tasks_table(ctx))
            console.print("[dim]  ───[/dim]")
            continue

        if msg == "/traces" or msg.startswith("/traces "):
            traces = getattr(ctx, "llm_traces", [])
            n = 5
            if msg.startswith("/traces ") and msg.split(maxsplit=1)[1].strip().isdigit():
                n = max(1, int(msg.split(maxsplit=1)[1].strip()))
            show = traces[-n:] if traces else []
            if not show:
                console.print(Panel("[dim]No LLM traces yet. Run /run (analyze, design, or implement) to generate.[/]", title="[bold]traces[/bold]", border_style="dim"))
            else:
                for i, entry in enumerate(reversed(show)):
                    console.print(Panel(_format_llm_trace(entry), title=f"[bold]trace[/] {len(show) - i} ([magenta]{entry.get('kind', '?')}[/])", border_style="dim", padding=(0, 1)))
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
            plan_message: List[str] = [f"[dim]Planning: {goal[:50]}{'…' if len(goal) > 50 else ''}[/]"]
            plan_spinner = Panel(
                _LiveSpinner(plan_message, spinner_name="dots", style="bold green"),
                title="[bold green] plan [/]",
                border_style="green",
                padding=(0, 1),
            )
            with Live(plan_spinner, refresh_per_second=LIVE_REFRESH_PER_SECOND, console=console):
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

            outs: List[str] = []
            run_message: List[str] = ["Starting…"]
            run_spinner_panel = Panel(
                _LiveSpinner(run_message, spinner_name=RUN_SPINNER),
                title="[bold yellow] run [/]",
                border_style="yellow",
                padding=(0, 1),
            )
            live_renderable = Group(run_spinner_panel, _LiveTraceView(ctx))

            with Live(live_renderable, refresh_per_second=LIVE_REFRESH_PER_SECOND, console=console):
                for i in range(max(1, count)):
                    next_t = ctx.task_queue.next_pending()
                    if next_t:
                        subagents_desc = TASK_SUBAGENTS.get(next_t.kind, "—")
                        run_message[0] = f"[bold]{next_t.id}[/] [cyan]({next_t.kind})[/] [dim]→ {subagents_desc}[/]"
                    else:
                        run_message[0] = "[dim]No pending tasks[/]"
                    out = await run_next_task(ctx)
                    outs.append(out)
                    if next_t and out.startswith(f"{next_t.id} done"):
                        run_message[0] = f"[green]✓ {next_t.id} done[/] — next…"
                    elif next_t and out.startswith(f"{next_t.id} failed"):
                        run_message[0] = f"[red]✗ {next_t.id} failed[/] — next…"

            # After Live stops, show completion and result panel
            if outs:
                for o in outs:
                    if "done:" in o:
                        console.print(f"  [green]✓[/] [dim]{o.split(chr(10))[0]}[/]")
                    elif "failed" in o:
                        console.print(f"  [red]✗[/] [dim]{o.split(chr(10))[0]}[/]")
            # Show last LLM trace briefly so user can see what the model saw/returned
            traces = getattr(ctx, "llm_traces", [])
            if traces:
                last = traces[-1]
                console.print(Panel(_format_llm_trace(last), title="[bold]last LLM trace[/] [dim](/traces for more)[/]", border_style="magenta", padding=(0, 1)))
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
        plan_message_plain: List[str] = [msg[:60] + ("…" if len(msg) > 60 else "")]
        plan_spinner_plain = Panel(
            _LiveSpinner(plan_message_plain, spinner_name="arc", style="bold cyan", use_markup=False),
            title="[bold cyan] plan [/]",
            border_style="cyan",
            padding=(0, 1),
        )
        with Live(plan_spinner_plain, refresh_per_second=LIVE_REFRESH_PER_SECOND, console=console):
            lines = await plan_and_queue(ctx, msg)
        console.print(Panel("\n".join(lines), title="plan"))
