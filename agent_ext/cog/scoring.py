from __future__ import annotations

from dataclasses import dataclass


def touched_files_from_diff(diff_text: str) -> list[str]:
    files = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                files.append(parts[3].replace("b/", ""))
    return sorted(set(files))


@dataclass(frozen=True)
class Score:
    total: float
    reasons: dict[str, float]

    @property
    def score(self) -> float:
        """Alias for ``total`` — used by workbench loop and cog loop."""
        return self.total

    @property
    def ok(self) -> bool:
        """True when gates passed (positive gates score)."""
        return self.reasons.get("gates", 0.0) > 0


def score_patch(*, gates_ok: bool, diff_chars: int, files_touched: int, eval_delta: float = 0.0) -> Score:
    """
    Starter scoring:
      +100 if gates pass
      +50*eval_delta (later)
      - diff_chars/2000 (cap 30)
      - 2*files_touched (cap 20)
    """
    reasons: dict[str, float] = {}
    total = 0.0

    reasons["gates"] = 100.0 if gates_ok else -50.0
    total += reasons["gates"]

    reasons["eval_delta"] = eval_delta * 50.0
    total += reasons["eval_delta"]

    reasons["diff_penalty"] = -min(30.0, diff_chars / 2000.0)
    total += reasons["diff_penalty"]

    reasons["files_penalty"] = -min(20.0, files_touched * 2.0)
    total += reasons["files_penalty"]

    return Score(total=total, reasons=reasons)
