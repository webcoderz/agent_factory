from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]{1,}|[0-9]+")


@dataclass
class TokenizerConfig:
    use_tiktoken: bool = False
    tiktoken_encoding: str = "o200k_base"  # override if needed
    max_tokens_per_doc: int = 20000  # prevent indexing huge blobs


def _regex_tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text)]


class Tokenizer:
    """
    Tokenizer with optional tiktoken backing. For BM25 you usually want word-ish tokens;
    tiktoken can help for code identifiers + punctuation-y stuff, but word tokens often win.

    Strategy:
      - Default to regex word tokens (fast, good for BM25)
      - Optionally augment with tiktoken token strings (configurable)
    """

    def __init__(self, cfg: TokenizerConfig):
        self.cfg = cfg
        self._enc = None
        if cfg.use_tiktoken:
            try:
                import tiktoken  # type: ignore

                self._enc = tiktoken.get_encoding(cfg.tiktoken_encoding)
            except Exception:
                self._enc = None  # silently fall back

    def tokenize(self, text: str) -> list[str]:
        toks = _regex_tokens(text)

        if self._enc is not None:
            # Augment with token ids mapped to strings to capture code-ish fragments
            # Keep bounded so we don't explode postings.
            ids = self._enc.encode(text)
            if len(ids) > self.cfg.max_tokens_per_doc:
                ids = ids[: self.cfg.max_tokens_per_doc]
            # Represent token ids as "t<id>" (stable, compact, not leaking raw bytes)
            toks.extend([f"t{tid}" for tid in ids])

        return toks
