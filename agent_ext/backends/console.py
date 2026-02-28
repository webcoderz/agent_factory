"""Console toolset — gives any pydantic-ai agent file and shell capabilities.

Tools: ls, read_file, write_file, edit_file, grep, glob_files, execute.

Example::

    from pydantic_ai import Agent
    from agent_ext.backends import create_console_toolset, ConsoleDeps, LocalFilesystemBackend

    backend = LocalFilesystemBackend(root="/workspace", allow_write=True)
    toolset = create_console_toolset()
    agent = Agent("openai:gpt-4o", toolsets=[toolset])

    deps = ConsoleDeps(backend=backend)
    result = await agent.run("List files in the src directory", deps=deps)
"""

from __future__ import annotations

import subprocess
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, SkipValidation
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from .permissions import PERMISSIVE_RULESET, PermissionChecker, PermissionRuleset

CONSOLE_SYSTEM_PROMPT = """\
## Console Tools

You have access to filesystem tools (ls, read_file, write_file, edit_file, \
glob, grep) and shell execution (execute). Read each tool's description for \
detailed usage guidance.
"""


class ConsoleDeps(BaseModel):
    """Dependencies for the console toolset."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    backend: Annotated[Any, SkipValidation]  # FilesystemBackend
    permissions: PermissionRuleset = PERMISSIVE_RULESET
    exec_enabled: bool = False
    exec_timeout: int = 30


def create_console_toolset(*, toolset_id: str | None = None) -> FunctionToolset[ConsoleDeps]:
    """Create a console toolset with file operations and optional shell execution.

    Returns:
        FunctionToolset with ls, read_file, write_file, edit_file, grep, glob_files, execute.
    """
    toolset: FunctionToolset[ConsoleDeps] = FunctionToolset(id=toolset_id)

    def _check(ctx: RunContext[ConsoleDeps], op: str, path: str) -> str | None:
        """Check permission; return error string or None."""
        checker = PermissionChecker(ctx.deps.permissions)
        action = checker.check(op, path)  # type: ignore[arg-type]
        if action == "deny":
            return f"Permission denied: {op} on {path}"
        if action == "ask":
            return f"Permission required: {op} on {path} (ask mode not implemented)"
        return None

    @toolset.tool(description="List files and directories at the given path.")
    async def ls(ctx: RunContext[ConsoleDeps], path: str = ".") -> str:
        err = _check(ctx, "ls", path)
        if err:
            return err
        try:
            entries = ctx.deps.backend.list(path)
            return "\n".join(entries) if entries else "(empty directory)"
        except Exception as e:
            return f"Error: {e}"

    @toolset.tool(description="Read file content. ALWAYS read a file before editing it.")
    async def read_file(ctx: RunContext[ConsoleDeps], path: str, offset: int = 0, limit: int = 2000) -> str:
        err = _check(ctx, "read", path)
        if err:
            return err
        try:
            content = ctx.deps.backend.read_text(path)
            lines = content.split("\n")
            end = min(offset + limit, len(lines))
            numbered = [f"{i + 1:>6}\t{lines[i]}" for i in range(offset, end)]
            result = "\n".join(numbered)
            if end < len(lines):
                result += f"\n\n... ({len(lines) - end} more lines)"
            return result
        except Exception as e:
            return f"Error: {e}"

    @toolset.tool(
        description="Write content to a file. Creates the file if it doesn't exist. Prefer edit_file for existing files."
    )
    async def write_file(ctx: RunContext[ConsoleDeps], path: str, content: str) -> str:
        err = _check(ctx, "write", path)
        if err:
            return err
        try:
            ctx.deps.backend.write_text(path, content)
            return f"Wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"Error: {e}"

    @toolset.tool(
        description="Edit a file by replacing an exact string. ALWAYS read_file first. Use replace_all=True for renaming."
    )
    async def edit_file(
        ctx: RunContext[ConsoleDeps],
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        err = _check(ctx, "edit", path)
        if err:
            return err
        try:
            content = ctx.deps.backend.read_text(path)
            count = content.count(old_string)
            if count == 0:
                return f"Error: String not found in {path}"
            if count > 1 and not replace_all:
                return f"Error: String found {count} times. Use replace_all=True or provide more context."
            if replace_all:
                new_content = content.replace(old_string, new_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
            ctx.deps.backend.write_text(path, new_content)
            return f"Replaced {'all ' + str(count) if replace_all else '1'} occurrence(s) in {path}"
        except Exception as e:
            return f"Error: {e}"

    @toolset.tool(description="Search for a regex pattern in files.")
    async def grep(ctx: RunContext[ConsoleDeps], pattern: str, path: str = ".") -> str:
        err = _check(ctx, "grep", path)
        if err:
            return err
        try:
            import re

            results: list[str] = []
            for fp in ctx.deps.backend.glob("**/*.py"):
                try:
                    content = ctx.deps.backend.read_text(fp)
                    for i, line in enumerate(content.split("\n")):
                        if re.search(pattern, line):
                            results.append(f"{fp}:{i + 1}: {line.rstrip()}")
                except Exception:
                    continue
                if len(results) >= 50:
                    break
            return "\n".join(results) if results else "No matches found."
        except Exception as e:
            return f"Error: {e}"

    @toolset.tool(description="Find files matching a glob pattern.")
    async def glob_files(ctx: RunContext[ConsoleDeps], pattern: str) -> str:
        err = _check(ctx, "glob", pattern)
        if err:
            return err
        try:
            matches = ctx.deps.backend.glob(pattern)
            return "\n".join(matches) if matches else "No files found."
        except Exception as e:
            return f"Error: {e}"

    @toolset.tool(description="Execute a shell command. Only available when exec is enabled.")
    async def execute(ctx: RunContext[ConsoleDeps], command: str) -> str:
        if not ctx.deps.exec_enabled:
            return "Error: Shell execution is disabled."
        err = _check(ctx, "execute", command)
        if err:
            return err
        try:
            p = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=ctx.deps.exec_timeout,
            )
            output = (p.stdout or "") + (p.stderr or "")
            if len(output) > 10_000:
                output = output[:10_000] + "\n... (truncated)"
            return f"Exit code: {p.returncode}\n{output}".strip()
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {ctx.deps.exec_timeout}s"
        except Exception as e:
            return f"Error: {e}"

    return toolset
