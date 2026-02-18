from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass
class SubagentResult:
    ok: bool
    name: str
    output: Any
    meta: Dict[str, Any]

class BM25SearchSubagent:
    name = "bm25"

    async def run(self, ctx, *, input: Any, meta: Dict[str, Any]) -> SubagentResult:
        query = str(input).strip()
        k = int(meta.get("k", 20))
        hits = ctx.search.search(query, top_k=k)  # [(path, score)]
        # return top paths only (keep it small)
        out = [{"path": p, "score": float(s)} for p, s in hits]
        return SubagentResult(ok=True, name=self.name, output=out, meta={"query": query, "k": k})
