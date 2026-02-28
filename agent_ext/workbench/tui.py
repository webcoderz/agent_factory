from __future__ import annotations

from collections.abc import Callable

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()


def run_tui(
    *,
    on_user_message: Callable[[str], str],
    on_command: Callable[[str], str | None],
) -> None:
    console.print(Panel.fit("agent_patterns workbench (type /help for commands, /quit to exit)"))

    while True:
        try:
            msg = console.input("[bold cyan]you> [/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nbye")
            return

        if not msg:
            continue

        if msg.startswith("/"):
            if msg in ("/quit", "/exit"):
                console.print("bye")
                return
            out = on_command(msg)
            if out:
                console.print(Panel(out, title=msg))
            else:
                console.print(Panel("unknown command", title=msg))
            continue

        out = on_user_message(msg)
        # render markdown if it looks like markdown
        console.print(Markdown(out))
