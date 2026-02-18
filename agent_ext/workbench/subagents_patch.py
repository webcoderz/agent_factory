from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

@dataclass
class SubagentResult:
    ok: bool
    name: str
    output: Any
    meta: Dict[str, Any]

def _read_snippet(root: Path, rel_path: str, max_chars: int = 6000) -> str:
    p = root / rel_path
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    if len(txt) > max_chars:
        return txt[:max_chars] + "\n...\n"
    return txt

class LLMPatchSubagent:
    """
    Produces a unified diff. Does NOT apply it.
    Expects ctx.model to be a pydantic-ai OpenAIChatModel (or compatible).
    """
    name = "llm_patch"

    async def run(self, ctx, *, input: Any, meta: Dict[str, Any]) -> SubagentResult:
        if ctx.model is None:
            return SubagentResult(ok=False, name=self.name, output="", meta={"error": "ctx.model is None"})

        workdir = Path(meta.get("workdir", "."))  # may be worktree path
        goal = str(input)

        # candidates: list of {path, score}
        candidates: List[Dict[str, Any]] = meta.get("candidates", [])[: int(meta.get("max_files", 6))]

        snippets = []
        for c in candidates:
            rp = c["path"]
            s = _read_snippet(workdir, rp)
            if s:
                snippets.append(f"FILE: {rp}\n---\n{s}\n")

        strategy = meta.get("strategy")
        strategy_block = f"\nSTRATEGY (follow this approach):\n{strategy}\n" if strategy else ""

        prompt = f"""
You are editing a git repository. Produce a SINGLE unified diff that implements the goal.
{strategy_block}
GOAL:
{goal}

RULES:
- Output ONLY the raw unified diff. No markdown, no code fences (no ```), no explanation before or after.
- Start with "diff --git a/path b/path" or "--- path" and end with the last hunk line.
- Keep changes minimal. Use standard unified diff format: ---/+++ headers, @@ hunk headers, then context lines (space), +add, -remove.
- For new files use --- /dev/null and +++ b/path.
- Prefer modifying existing code rather than inventing new frameworks. Ensure code compiles.

CONTEXT SNIPPETS:
{chr(10).join(snippets) if snippets else "(no snippets)"}
""".strip()

        # Use pydantic-ai Agent only (OpenAIChatModel.request() has different signature by version)
        async with ctx.model_limiter:
            from pydantic_ai import Agent
            agent = Agent(model=ctx.model)
            result = await agent.run(prompt)
            text_out = getattr(result, "output", None) or str(result)

        diff = (text_out or "").strip()
        ok = diff.startswith("diff --git") or diff.startswith("--- ")
        return SubagentResult(ok=ok, name=self.name, output=diff, meta={"files_considered": [c["path"] for c in candidates]})
