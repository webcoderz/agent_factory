from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .store import BM25_INDEX_FILE, BM25_META_FILE, read_json, write_json
from .tokenize import Tokenizer, TokenizerConfig
from .index import RepoIndexer, RepoIndexerConfig


@dataclass
class BM25Config:
    k1: float = 1.2
    b: float = 0.75
    top_k: int = 20


class BM25Index:
    """
    In-memory BM25 with incremental rebuild for changed files.
    Persisted to .agent_state/bm25_index.json and bm25_meta.json
    """
    def __init__(self, *, bm25_cfg: BM25Config, tok_cfg: TokenizerConfig, indexer_cfg: RepoIndexerConfig):
        self.bm25_cfg = bm25_cfg
        self.tokenizer = Tokenizer(tok_cfg)
        self.indexer = RepoIndexer(indexer_cfg)

        # postings: token -> {doc_id: tf}
        self.postings: Dict[str, Dict[str, int]] = {}
        self.doc_len: Dict[str, int] = {}
        self.doc_sha: Dict[str, str] = {}
        self.N: int = 0
        self.avgdl: float = 0.0
        self._index_ready: bool = False  # rebuild deferred until first search

    def ensure_index(self) -> None:
        """Build or refresh index on first use (keeps startup fast)."""
        if self._index_ready:
            return
        self.rebuild_incremental()
        self._index_ready = True

    def load(self) -> None:
        meta = read_json(BM25_META_FILE, {})
        data = read_json(BM25_INDEX_FILE, {})
        self.postings = data.get("postings", {})
        self.doc_len = data.get("doc_len", {})
        self.doc_sha = data.get("doc_sha", {})
        self.N = int(data.get("N", 0))
        self.avgdl = float(data.get("avgdl", 0.0))

    def save(self) -> None:
        write_json(BM25_META_FILE, {
            "k1": self.bm25_cfg.k1,
            "b": self.bm25_cfg.b,
            "tokenizer": {
                "use_tiktoken": bool(self.tokenizer.cfg.use_tiktoken),
                "tiktoken_encoding": self.tokenizer.cfg.tiktoken_encoding,
            },
        })
        write_json(BM25_INDEX_FILE, {
            "postings": self.postings,
            "doc_len": self.doc_len,
            "doc_sha": self.doc_sha,
            "N": self.N,
            "avgdl": self.avgdl,
        })

    def _remove_doc(self, doc_id: str) -> None:
        # remove doc from postings
        for tok, plist in list(self.postings.items()):
            if doc_id in plist:
                del plist[doc_id]
                if not plist:
                    del self.postings[tok]
        self.doc_len.pop(doc_id, None)
        self.doc_sha.pop(doc_id, None)

    def _add_doc(self, doc_id: str, text: str, sha: str) -> None:
        toks = self.tokenizer.tokenize(text)
        tf: Dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1

        for tok, cnt in tf.items():
            self.postings.setdefault(tok, {})[doc_id] = cnt

        self.doc_len[doc_id] = len(toks)
        self.doc_sha[doc_id] = sha

    def rebuild_incremental(self) -> Tuple[int, int]:
        """
        Updates repo index, then updates BM25 index only for changed/removed files.
        Returns (num_changed, num_removed).
        """
        repo_state, changed, removed = self.indexer.update_incremental()

        # load existing index if not loaded
        if not self.postings:
            self.load()

        # apply removals
        for doc_id in removed:
            self._remove_doc(doc_id)

        # apply changes
        for doc_id in changed:
            meta = repo_state.files.get(doc_id)
            if not meta:
                continue
            sha = meta.get("sha256", "")
            skipped = bool(meta.get("skipped", False))
            if skipped:
                # treat as removed to avoid stale
                self._remove_doc(doc_id)
                continue

            # if sha unchanged, skip
            if self.doc_sha.get(doc_id) == sha:
                continue

            text = self.indexer.read_text(doc_id)
            if text is None:
                continue
            # remove old then add
            self._remove_doc(doc_id)
            self._add_doc(doc_id, text, sha)

        # recompute corpus stats
        self.N = len(self.doc_len)
        self.avgdl = (sum(self.doc_len.values()) / self.N) if self.N else 0.0
        self.save()
        return len(changed), len(removed)

    def search(self, query: str, *, top_k: int | None = None) -> List[Tuple[str, float]]:
        self.ensure_index()
        q_toks = self.tokenizer.tokenize(query)
        if not q_toks or self.N == 0:
            return []

        k1 = self.bm25_cfg.k1
        b = self.bm25_cfg.b
        top_k = top_k or self.bm25_cfg.top_k

        scores: Dict[str, float] = {}
        seen_tokens = set(q_toks)

        for tok in seen_tokens:
            plist = self.postings.get(tok)
            if not plist:
                continue
            df = len(plist)
            # idf with BM25+ style smoothing
            idf = math.log(1.0 + (self.N - df + 0.5) / (df + 0.5))

            for doc_id, tf in plist.items():
                dl = self.doc_len.get(doc_id, 0)
                denom = tf + k1 * (1.0 - b + b * (dl / (self.avgdl + 1e-9)))
                score = idf * (tf * (k1 + 1.0) / (denom + 1e-9))
                scores[doc_id] = scores.get(doc_id, 0.0) + score

        return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
