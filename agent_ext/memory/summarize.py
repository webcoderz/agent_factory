from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from agent_ext.run_context import RunContext

from .base import MemoryManager


class Dossier(BaseModel):
    """
    Long-lived compressed state for a case/session.
    """

    pinned_facts: list[str] = Field(default_factory=list)
    timeline: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    summary: str = ""


class SummarizeConfig(BaseModel):
    max_messages: int = 80
    keep_last_n: int = 30
    min_messages_before_summarize: int = 90
    max_input_chars: int = 250_000


def _stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _default_message_to_text(m: Any) -> str:
    """
    Conservative formatter: works for dict-like, pydantic, and plain strings.
    You should adapt this to your exact message schema for best results.
    """
    if isinstance(m, str):
        return m
    if hasattr(m, "model_dump"):
        d = m.model_dump()
        role = d.get("role", "msg")
        content = d.get("content", d)
        return f"[{role}] {content}"
    if isinstance(m, dict):
        role = m.get("role", "msg")
        content = m.get("content", m)
        return f"[{role}] {content}"
    return str(m)


class SummarizingMemory(MemoryManager):
    """
    Real summarizing memory:
    - keeps last keep_last_n messages verbatim
    - stores a Dossier artifact for older history
    - emits a synthetic 'system' dossier message at the front when present
    """

    def __init__(
        self,
        *,
        cfg: SummarizeConfig,
        summarize_fn: Callable[[RunContext, str, Dossier], Dossier],
        message_to_text: Callable[[Any], str] = _default_message_to_text,
    ):
        self.cfg = cfg
        self.summarize_fn = summarize_fn
        self.message_to_text = message_to_text

        self._dossier: Dossier | None = None
        self._dossier_artifact_id: str | None = None
        self._last_input_hash: str | None = None

    def shape_messages(self, messages: list[Any]) -> list[Any]:
        # If we already have a dossier, prepend it as a synthetic system message.
        if not self._dossier:
            # Window only
            return messages[-self.cfg.max_messages :]

        dossier_msg = {
            "role": "system",
            "content": self._render_dossier(self._dossier),
            "metadata": {"artifact_id": self._dossier_artifact_id, "kind": "dossier"},
        }
        tail = messages[-self.cfg.keep_last_n :]
        shaped = [dossier_msg, *tail]
        return shaped[-self.cfg.max_messages :]

    def checkpoint(self, messages: list[Any], *, outcome: Any) -> None:
        # Only summarize if we have enough history.
        if len(messages) < self.cfg.min_messages_before_summarize:
            return

        # Build summarization input from the "older" portion (everything except last keep_last_n).
        older = messages[: max(0, len(messages) - self.cfg.keep_last_n)]
        text = "\n".join(self.message_to_text(m) for m in older)
        if len(text) > self.cfg.max_input_chars:
            text = text[-self.cfg.max_input_chars :]

        input_hash = _stable_hash(text)
        if self._last_input_hash == input_hash:
            return  # nothing new to summarize

        base = self._dossier or Dossier()
        # Perform summarization (pluggable).
        # IMPORTANT: your summarize_fn should be policy-aware (redaction, etc.)
        # and should update pinned_facts/decisions/open_questions as needed.
        # It can be LLM-based or deterministic.
        new_dossier = self.summarize_fn(self._ctx_required(), text, base)

        # Persist dossier to artifact store (auditability).
        payload = new_dossier.model_dump()
        artifact_id = self._ctx_required().artifacts.put_json(
            payload,
            metadata={
                "kind": "dossier",
                "case_id": self._ctx_required().case_id,
                "session_id": self._ctx_required().session_id,
                "input_hash": input_hash,
            },
        )

        self._dossier = new_dossier
        self._dossier_artifact_id = artifact_id
        self._last_input_hash = input_hash

    # --- wiring: ctx is set by composition root after instantiation
    _ctx: RunContext | None = None

    def bind_ctx(self, ctx: RunContext) -> None:
        self._ctx = ctx

    def _ctx_required(self) -> RunContext:
        if not self._ctx:
            raise RuntimeError("SummarizingMemory not bound to RunContext. Call bind_ctx(ctx).")
        return self._ctx

    @staticmethod
    def _render_dossier(d: Dossier) -> str:
        # Keep it compact; model should treat as authoritative "case memory".
        lines: list[str] = []
        if d.summary:
            lines.append(f"CASE DOSSIER SUMMARY:\n{d.summary}\n")
        if d.pinned_facts:
            lines.append("PINNED FACTS:\n- " + "\n- ".join(d.pinned_facts))
        if d.decisions:
            lines.append("\nDECISIONS:\n- " + "\n- ".join(d.decisions))
        if d.entities:
            lines.append("\nKEY ENTITIES:\n- " + "\n- ".join(d.entities))
        if d.timeline:
            lines.append("\nTIMELINE:\n- " + "\n- ".join(d.timeline))
        if d.open_questions:
            lines.append("\nOPEN QUESTIONS:\n- " + "\n- ".join(d.open_questions))
        return "\n".join(lines).strip()
