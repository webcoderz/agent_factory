from __future__ import annotations

import asyncio
import re
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

from .loop import plan_and_queue, run_n_tasks, run_next_task

# Slightly custom theme: keep default but ensure status colors pop
console = Console(theme=Theme({"info": "cyan", "success": "green", "warn": "yellow", "error": "red", "dim": "dim"}))

BANNER = """
[bold cyan]  ╭─────────────────────────────────────╮
  │  [bold white]agent_patterns[/bold white] [dim]workbench[/dim]        │
  ╰─────────────────────────────────────╯[/bold cyan]
[dim]  Goal → plan (dynamic) → /run → task completions stream live (Cursor/Claude Code style)[/dim]
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


def _watch_renderable(ctx, task_id: Optional[str] = None) -> Group:
    """Build the live-updating view for /watch: recent task outputs + last LLM trace."""
    watch_out = getattr(ctx, "watch_outputs", [])
    lines = []
    for out in watch_out[-25:]:
        first = (out.split("\n")[0] or "").strip()
        if "done" in out and "failed" not in out:
            lines.append(f"  [green]✓[/] {first}")
        elif "failed" in out:
            lines.append(f"  [red]✗[/] {first}")
        else:
            lines.append(f"  [dim]{first}[/]")
    task_block = "\n".join(lines) if lines else "[dim]No task output yet. Run /run to see completions here.[/]"
    task_panel = Panel(task_block, title="[bold]Recent task output[/] [dim](streams as run progresses)[/dim]", border_style="cyan", padding=(0, 1))
    trace_panel = _LiveTraceView(ctx, max_lines=14)
    if task_id:
        # Highlight that we're watching for this task
        watching = f"[yellow]Watching for {task_id}[/] — output will appear above when it completes."
        header = Panel(watching, title="[bold]watch[/]", border_style="yellow", padding=(0, 1))
        return Group(header, task_panel, trace_panel)
    return Group(task_panel, trace_panel)


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


# Max chars per trace when listing (avoid hanging on /traces with huge prompts/responses)
TRACE_PREVIEW_PROMPT = 800
TRACE_PREVIEW_RESPONSE = 1200


def _format_llm_trace(entry: dict, truncate: bool = True) -> str:
    kind = entry.get("kind", "?")
    prompt = entry.get("prompt", "") or ""
    response = entry.get("response", "") or ""
    if truncate:
        if len(prompt) > TRACE_PREVIEW_PROMPT:
            prompt = prompt[:TRACE_PREVIEW_PROMPT] + "\n… [truncated]"
        if len(response) > TRACE_PREVIEW_RESPONSE:
            response = response[:TRACE_PREVIEW_RESPONSE] + "\n… [truncated]"
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
                    "[cyan]/plan <goal>[/]  queue plan (background)",
                    "[cyan]/run[/] [dim]or[/] [cyan]/run N[/]  run in background  [cyan]/run N fg[/]  wait & watch",
                    "[cyan]/parallel <n>[/]  max subagents",
                    "[cyan]/model[/]   model info",
                    "[cyan]/workflows[/]  list",
                    "[cyan]/assemble[/] [cyan]/exec[/]  workflow",
                    "[cyan]/adopt[/]   apply last patch",
                    "[cyan]/traces[/] [dim][N][/]  last LLM prompt/response",
                    "[cyan]/watch[/] [dim][task_id][/]  live view of run + trace (Enter to leave)",
                    "[cyan]/ask <q>[/]  one-off question (background)",
                    "[cyan]/stop[/]   cancel background run",
                    "[cyan]/quit[/]    exit",
                ]),
                title="[bold]commands[/bold]",
                border_style="cyan",
            ))
            continue

        if msg == "/status":
            tasks_list = getattr(ctx, "background_run_tasks", [])
            active = [t for t in tasks_list if not t.done()]
            done_q = sum(1 for t in ctx.task_queue.list() if t.status == "done")
            pending_q = sum(1 for t in ctx.task_queue.list() if t.status == "pending")
            bg_line = ""
            if active:
                bg_line = f"\n[yellow]{len(active)} run(s) in progress[/] [dim](queue: {done_q} done, {pending_q} pending — /stop or /stop all)[/]"
            else:
                bg_line = f"\n[dim]queue: {done_q} done, {pending_q} pending[/]"
            console.print(Panel(
                f"[bold]case[/]={ctx.case_id}  [bold]session[/]={ctx.session_id}  [bold]user[/]={ctx.user_id}{bg_line}",
                title="[bold]status[/bold]",
                border_style="dim",
            ))
            continue

        if msg.startswith("/stop"):
            tasks_list = getattr(ctx, "background_run_tasks", [])
            active = [t for t in tasks_list if not t.done()]
            if not active:
                console.print(Panel("[dim]No background runs in progress.[/]", title="stop", border_style="dim"))
                continue
            stop_all = msg.strip().lower().endswith("all")
            if stop_all:
                for t in active:
                    t.cancel()
                for t in active:
                    try:
                        await t
                    except asyncio.CancelledError:
                        pass
                ctx.background_run_tasks.clear()
                console.print(Panel(f"[yellow]Stopped {len(active)} run(s).[/]", title="stop", border_style="yellow"))
            else:
                t = active[-1]
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
                try:
                    ctx.background_run_tasks.remove(t)
                except ValueError:
                    pass
                console.print(Panel("[yellow]Most recent run stopped.[/]", title="stop", border_style="yellow"))
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

        if msg == "/watch" or msg.startswith("/watch "):
            task_id = msg.split(maxsplit=1)[1].strip() if msg.startswith("/watch ") else None
            if task_id and not task_id.startswith("t"):
                task_id = f"t{task_id}" if task_id.isdigit() else task_id
            initial = _watch_renderable(ctx, task_id)
            with Live(initial, refresh_per_second=4, console=console) as live:

                async def _watch_update_loop() -> None:
                    while True:
                        live.update(_watch_renderable(ctx, task_id))
                        await asyncio.sleep(0.25)

                update_task = asyncio.create_task(_watch_update_loop())
                try:
                    await _ainput("\n[dim]Press Enter to close watch...[/] ")
                finally:
                    update_task.cancel()
                    try:
                        await update_task
                    except asyncio.CancelledError:
                        pass
            continue

        if msg == "/traces" or msg.startswith("/traces "):
            traces = getattr(ctx, "llm_traces", [])
            n = 5
            parts = msg.split(maxsplit=1)
            if len(parts) >= 2 and parts[1].strip().isdigit():
                n = max(1, min(30, int(parts[1].strip())))
            show = traces[-n:] if traces else []
            if not show:
                console.print(Panel("[dim]No LLM traces yet. Run /run (analyze, design, or implement) to generate.[/]", title="[bold]traces[/bold]", border_style="dim"))
            else:
                for i, entry in enumerate(reversed(show)):
                    body = _format_llm_trace(entry, truncate=True)
                    console.print(Panel(body, title=f"[bold]trace[/] {len(show) - i} ([magenta]{entry.get('kind', '?')}[/]) [dim]preview[/dim]", border_style="dim", padding=(0, 1)))
                if n > 1 or any(len((e.get("prompt") or "") + (e.get("response") or "")) > TRACE_PREVIEW_PROMPT + TRACE_PREVIEW_RESPONSE for e in show):
                    console.print("[dim]Previews only; full content in ctx.llm_traces[/]")
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
            if not goal:
                console.print(Panel("usage: /plan <goal>", title="plan", border_style="dim"))
                continue

            def _on_plan_done_slash(t: asyncio.Task) -> None:
                try:
                    if t.cancelled():
                        return
                    exc = t.exception()
                    if exc is not None:
                        console.print(Panel(f"[red]Plan failed: {exc}[/]", title="plan", border_style="red"))
                        return
                    lines = t.result()
                    console.print(Panel("\n".join(lines) if lines else "[dim]No tasks.[/]", title="plan", border_style="green"))
                except Exception as e:
                    console.print(Panel(f"[red]{e}[/]", title="plan", border_style="red"))

            asyncio.create_task(plan_and_queue(ctx, goal)).add_done_callback(_on_plan_done_slash)
            console.print(Panel(f"[dim]Planning in background:[/] {goal[:80]}{'…' if len(goal) > 80 else ''}\n[dim]/tasks when ready, then /run.[/]", title="plan", border_style="green"))
            continue

        if msg.startswith("/ask "):
            question = msg.split(" ", 1)[1].strip()
            if not question:
                console.print(Panel("usage: /ask <question>", title="ask", border_style="dim"))
                continue
            if not ctx.model:
                console.print(Panel("[red]No model set. Use --use-openai-chat-model.[/]", title="ask", border_style="red"))
                continue

            async def _ask_background(q: str) -> None:
                try:
                    from pydantic_ai import Agent
                    async with ctx.model_limiter:
                        agent = Agent(model=ctx.model)
                        result = await agent.run(q)
                    out = getattr(result, "output", None) or str(result)
                    console.print(Panel(f"[dim]Q:[/] {q[:120]}{'…' if len(q) > 120 else ''}\n\n[green]{out}[/]", title="ask", border_style="cyan"))
                except asyncio.CancelledError:
                    console.print(Panel("[yellow]Ask cancelled.[/]", title="ask", border_style="yellow"))
                except Exception as e:
                    console.print(Panel(f"[red]{e}[/]", title="ask", border_style="red"))

            asyncio.create_task(_ask_background(question))
            console.print(Panel(f"[dim]Asking in background.[/] Answer will appear when ready. Keep typing — /tasks, /run, etc.[/]", title="ask", border_style="cyan"))
            continue

        if msg.startswith("/run"):
            parts = msg.split()
            count = 1
            # Default: run in background so TUI stays responsive; use fg/wait to block and watch
            background = True
            if len(parts) >= 2:
                if parts[-1] in ("fg", "wait", "foreground"):
                    background = False
                    parts = parts[:-1]
                elif parts[-1] in ("&", "bg"):
                    parts = parts[:-1]
                if parts and len(parts) >= 2:
                    try:
                        count = max(1, int(parts[1]))
                    except Exception:
                        count = 1

            if background:
                # Non-blocking: run in background; stream task completions live (Cursor/Claude Code style)
                tasks_list = getattr(ctx, "background_run_tasks", [])

                def _on_task_complete(out: str) -> None:
                    first = (out.split("\n")[0] or "").strip()
                    if "done" in out and "failed" not in out:
                        console.print(f"  [green]✓[/] [dim]{first}[/]")
                    elif "failed" in out:
                        console.print(f"  [red]✗[/] [dim]{first}[/]")
                    watch_out = getattr(ctx, "watch_outputs", None)
                    if watch_out is not None:
                        watch_out.append(out)
                        if len(watch_out) > 100:
                            watch_out.pop(0)

                def _on_background_done(t: asyncio.Task) -> None:
                    try:
                        ctx.background_run_tasks.remove(t)
                    except ValueError:
                        pass
                    if t.cancelled():
                        console.print(Panel("[yellow]Background run stopped.[/]", title="run", border_style="yellow"))
                        return
                    exc = t.exception()
                    if exc is not None:
                        console.print(Panel(f"[red]Background run error: {exc}[/]", title="run", border_style="red"))
                        return
                    outs = t.result()
                    if not outs:
                        console.print(Panel("[dim]No tasks run (queue empty).[/]", title="run", border_style="dim"))
                        return
                    n_done = sum(1 for o in outs if "done" in o and "failed" not in o)
                    failed_outs = [o for o in outs if "failed" in o]
                    n_fail = len(failed_outs)
                    body = f"[green]Background run finished.[/] {n_done} done, {n_fail} failed."
                    if failed_outs:
                        body += "\n\n[red]Failed task(s):[/]"
                        for o in failed_outs:
                            lines = o.strip().split("\n")
                            # For implement/patch failures show more context (reason + model snippet)
                            if "create patch failed" in o or "implement:" in o and "failed" in o:
                                excerpt = "\n    ".join(lines[:8]) if len(lines) > 1 else lines[0]
                                if len(excerpt) > 700:
                                    excerpt = excerpt[:697] + "..."
                                body += f"\n  [red]•[/] {excerpt}"
                            else:
                                first_line = (lines[0] or "").strip()
                                if len(first_line) > 120:
                                    first_line = first_line[:117] + "..."
                                body += f"\n  [red]•[/] {first_line}"
                        body += "\n\n[dim]Use /tasks and /traces for full details.[/]"
                    else:
                        body += "\n[dim]Use /tasks and /traces to inspect.[/]"
                    if n_fail == 0 and outs:
                        for o in outs:
                            if "diff_saved=" in o:
                                m = re.search(r"diff_saved=(\S+)", o)
                                if m:
                                    body += f"\n[cyan]Patch:[/] [dim]{m.group(1)}[/] [dim](/adopt to apply)[/]"
                                    break
                    console.print(Panel(body, title="run", border_style="green" if n_fail == 0 else "red"))

                task = asyncio.create_task(run_n_tasks(ctx, count, progress_callback=_on_task_complete))
                task.add_done_callback(_on_background_done)
                ctx.background_run_tasks.append(task)
                n_active = len([x for x in ctx.background_run_tasks if not x.done()])
                console.print(Panel(
                    f"[green]Run started[/] ({count} worker(s)) — task completions will stream below. [cyan]/status[/] [cyan]/traces[/] [cyan]/stop[/]",
                    title="run",
                    border_style="green",
                ))
                continue

            # Foreground (blocking): show Live spinner + trace
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



        # Plain chat message = queue plan in background (never block TUI; OpenCode/Claude Code style)
        goal = msg.strip()[:200]
        if not goal:
            continue

        def _on_plan_done(t: asyncio.Task) -> None:
            try:
                if t.cancelled():
                    return
                exc = t.exception()
                if exc is not None:
                    console.print(Panel(f"[red]Plan failed: {exc}[/]", title="plan", border_style="red"))
                    return
                lines = t.result()
                if lines and "planner failed" not in (lines[0] or ""):
                    console.print(Panel(
                        "[green]Plan done.[/] " + "\n".join(lines)[:500] + ("\n…" if len("\n".join(lines)) > 500 else "") + "\n[dim]Use /run to start, or /plan <goal> for another.[/]",
                        title="plan",
                        border_style="green",
                    ))
                else:
                    console.print(Panel("\n".join(lines) if lines else "[dim]No tasks.[/]", title="plan", border_style="yellow"))
            except Exception as e:
                console.print(Panel(f"[red]{e}[/]", title="plan", border_style="red"))

        plan_task = asyncio.create_task(plan_and_queue(ctx, goal))
        plan_task.add_done_callback(_on_plan_done)
        console.print(Panel(
            f"[dim]Planning in background:[/] {goal}\n[dim]Keep typing — [/][cyan]/tasks[/] [dim]when ready, then [/][cyan]/run[/] [dim]. Run continues in parallel.[/]",
            title="plan",
            border_style="cyan",
        ))
        continue
