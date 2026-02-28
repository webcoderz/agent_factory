from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Strategy:
    name: str
    prompt_style: str


STRATEGIES = [
    Strategy("minimal_fix", "Make the smallest change that satisfies the goal."),
    Strategy("test_first", "Add/adjust tests first, then implement."),
    Strategy("refactor_safe", "Prefer safer refactor patterns and clearer structure."),
]


def pick_strategies(n: int) -> list[Strategy]:
    return STRATEGIES[: max(1, min(n, len(STRATEGIES)))]
