"""Pretty logging for RLM code execution.

Uses Rich for styled terminal output with syntax highlighting.
Falls back to plain text if Rich is not available.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import REPLResult

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class RLMLogger:
    """Pretty logger for RLM code execution."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.console = Console() if RICH_AVAILABLE else None

    def log_code_execution(self, code: str) -> None:
        """Log the code being executed."""
        if not self.enabled:
            return
        if RICH_AVAILABLE and self.console:
            syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
            self.console.print(Panel(syntax, title="[bold cyan]Code Execution[/]", border_style="cyan"))
        else:
            print(f"\n{'=' * 50}\nCODE EXECUTION\n{'=' * 50}\n{code}\n{'=' * 50}")

    def log_result(self, result: REPLResult) -> None:
        """Log the execution result."""
        if not self.enabled:
            return
        if RICH_AVAILABLE and self.console:
            status = "[bold green]SUCCESS[/]" if result.success else "[bold red]ERROR[/]"
            parts = [f"Executed in {result.execution_time:.3f}s"]
            if result.stdout.strip():
                parts.append(f"\n[bold yellow]Output:[/]\n{result.stdout.strip()[:2000]}")
            if result.stderr.strip():
                parts.append(f"\n[bold red]Errors:[/]\n{result.stderr.strip()[:1000]}")
            body = "\n".join(parts)
            border = "green" if result.success else "red"
            self.console.print(Panel(body, title=f"Result: {status}", border_style=border))
        else:
            status = "SUCCESS" if result.success else "ERROR"
            print(f"\n{'=' * 50}\nRESULT: {status} ({result.execution_time:.3f}s)\n{'=' * 50}")
            if result.stdout.strip():
                print(f"Output:\n{result.stdout.strip()[:2000]}")
            if result.stderr.strip():
                print(f"Errors:\n{result.stderr.strip()[:1000]}")

    def log_llm_query(self, prompt: str) -> None:
        """Log an llm_query call."""
        if not self.enabled:
            return
        display = prompt[:500] + "..." if len(prompt) > 500 else prompt
        if RICH_AVAILABLE and self.console:
            self.console.print(Panel(display, title="[bold blue]LLM Query[/]", border_style="blue"))
        else:
            print(f"\n{'=' * 50}\nLLM QUERY\n{'=' * 50}\n{display}")

    def log_llm_response(self, response: str) -> None:
        """Log an llm_query response."""
        if not self.enabled:
            return
        display = response[:500] + "..." if len(response) > 500 else response
        if RICH_AVAILABLE and self.console:
            self.console.print(Panel(display, title="[bold blue]LLM Response[/]", border_style="blue"))
        else:
            print(f"\nLLM RESPONSE:\n{display}")


# Global logger instance
_logger: RLMLogger | None = None


def get_logger() -> RLMLogger:
    """Get the global RLM logger (disabled by default)."""
    global _logger
    if _logger is None:
        _logger = RLMLogger(enabled=False)
    return _logger


def configure_logging(enabled: bool = True) -> RLMLogger:
    """Configure RLM logging."""
    global _logger
    _logger = RLMLogger(enabled=enabled)
    return _logger
