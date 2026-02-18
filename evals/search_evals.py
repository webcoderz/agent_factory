from __future__ import annotations

def run_search_smoke(ctx) -> dict:
    """
    Deterministic smoke test: ensures BM25 index returns something for common terms.
    Expand later using pydantic-evals.
    """
    q = "RunContext"
    hits = ctx.search.search(q, top_k=10)
    return {"query": q, "num_hits": len(hits), "top": hits[:3]}
