from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .loop import LLM_TRACE_MAX, LLM_TRACE_PROMPT_LEN, LLM_TRACE_RESPONSE_LEN

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
You are editing a git repository. Your reply must be exactly one unified diff and nothing else.
{strategy_block}
GOAL:
{goal}

CRITICAL — output format:
- Your entire response must be the raw unified diff only. No introductory sentence, no "Here is the diff", no markdown, no code fences (no ```), no explanation after.
- Start the first line with "diff --git a/path b/path" or "--- path". Include @@ hunk headers and +/− lines. End with the last hunk line.
- Example shape (minimal): --- a/file.py\\n+++ b/file.py\\n@@ -1,3 +1,4 @@\\n context\\n+new line\\n context
- Keep changes minimal. For new files use --- /dev/null and +++ b/path. Prefer modifying existing code; ensure code compiles.

CONTEXT SNIPPETS:
{chr(10).join(snippets) if snippets else "(no snippets)"}
""".strip()

        # Use pydantic-ai Agent with streaming so the TUI can show response as it arrives
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

        async with ctx.model_limiter:
            from pydantic_ai import Agent
            agent = Agent(model=ctx.model)
            text_out = ""
            use_stream = getattr(agent, "run_stream", None) is not None
            if use_stream:
                try:
                    async with agent.run_stream(prompt) as result:
                        async for text in result.stream_text():
                            text_out = text
                            if trace_entry is not None:
                                trace_entry["response"] = (text or "")[:LLM_TRACE_RESPONSE_LEN]
                except Exception as stream_err:
                    use_stream = False
                    text_out = getattr(stream_err, "output", "") or str(stream_err)
                    if trace_entry is not None:
                        trace_entry["response"] = (text_out or "")[:LLM_TRACE_RESPONSE_LEN]
                    raise
            if not use_stream or not text_out:
                result = await agent.run(prompt)
                text_out = getattr(result, "output", None) or str(result)
                if trace_entry is not None:
                    trace_entry["response"] = (text_out or "")[:LLM_TRACE_RESPONSE_LEN]

        diff = (text_out or "").strip()
        ok = diff.startswith("diff --git") or diff.startswith("--- ")
        return SubagentResult(ok=ok, name=self.name, output=diff, meta={"files_considered": [c["path"] for c in candidates]})
