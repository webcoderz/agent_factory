from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .loop import LLM_TRACE_MAX, LLM_TRACE_PROMPT_LEN, LLM_TRACE_RESPONSE_LEN
from .patch_models import PatchOutput, structured_to_unified_diff
from .subagents import SubagentResult

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
    Produces a unified diff via structured output: LLM returns PatchOutput (list of
    file edits with context/add/remove lines), we convert to valid unified diff.
    Avoids raw diff parsing and format failures.
    """
    name = "llm_patch"

    async def run(self, ctx, *, input: Any, meta: Dict[str, Any]) -> SubagentResult:
        if ctx.model is None:
            return SubagentResult(ok=False, name=self.name, output="", meta={"error": "ctx.model is None"})

        workdir = Path(meta.get("workdir", "."))
        goal = str(input)

        candidates: List[Dict[str, Any]] = meta.get("candidates", [])[: int(meta.get("max_files", 6))]

        snippets = []
        for c in candidates:
            rp = c["path"]
            s = _read_snippet(workdir, rp)
            if s:
                snippets.append(f"FILE: {rp}\n---\n{s}\n")

        strategy = meta.get("strategy")
        strategy_block = f"\nSTRATEGY (follow this approach):\n{strategy}\n" if strategy else ""

        prompt = f"""You are editing a git repository. Return a structured patch (JSON) describing the minimal code changes.
{strategy_block}
GOAL:
{goal}

RULES:
- Only change files needed for the goal. Prefer editing existing files over creating new ones.
- For each file: path (relative, e.g. agent_ext/foo.py), is_new_file (true only for new files), and lines: list of {{"kind": "context"|"add"|"remove", "content": "line text"}}.
- context = unchanged line, add = new line, remove = deleted line. Order matters; keep context lines around edits so the patch is readable.
- Keep changes minimal. Ensure code would still compile.

CONTEXT SNIPPETS:
{chr(10).join(snippets) if snippets else "(no snippets)"}

Return only the structured patch: {{"files": [{{"path": "...", "is_new_file": false, "lines": [{{"kind": "context", "content": "..."}}, ...]}}, ...]}}."""

        traces = getattr(ctx, "llm_traces", None)
        trace_entry: Optional[Dict[str, Any]] = None
        if traces is not None:
            if len(traces) >= LLM_TRACE_MAX:
                traces.pop(0)
            trace_entry = {
                "kind": "llm_patch",
                "prompt": (prompt or "")[:LLM_TRACE_PROMPT_LEN],
                "response": "",
            }
            traces.append(trace_entry)

        try:
            async with ctx.model_limiter:
                from pydantic_ai import Agent
                agent = Agent(model=ctx.model, output_type=PatchOutput)
                result = await agent.run(prompt)
                structured: PatchOutput = result.output

            diff = structured_to_unified_diff(structured)
            if trace_entry is not None:
                trace_entry["response"] = (diff or "")[:LLM_TRACE_RESPONSE_LEN]

            ok = bool(diff.strip()) and ("--- " in diff or "diff --git" in diff)
            return SubagentResult(
                ok=ok,
                name=self.name,
                output=diff,
                meta={"files_considered": [c["path"] for c in candidates], "structured": True},
            )
        except Exception as e:
            if trace_entry is not None:
                trace_entry["response"] = f"Structured output failed: {e!s}"
            return SubagentResult(
                ok=False,
                name=self.name,
                output="",
                meta={"error": str(e), "files_considered": [c["path"] for c in candidates]},
            )
