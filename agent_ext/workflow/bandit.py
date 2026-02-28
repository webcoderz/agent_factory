from __future__ import annotations

import math
from collections import defaultdict


class UCB1Bandit:
    """
    Simple, deterministic-ish, works well.
    Chooses workflow with best upper confidence bound.
    """

    def __init__(self):
        self.counts: dict[str, int] = defaultdict(int)
        self.values: dict[str, float] = defaultdict(float)
        self.total: int = 0

    def observe(self, arm: str, reward: float) -> None:
        self.total += 1
        self.counts[arm] += 1
        n = self.counts[arm]
        # incremental mean
        self.values[arm] += (reward - self.values[arm]) / float(n)

    def choose(self, arms: list[str]) -> str:
        # cold-start: pick untried first
        for a in arms:
            if self.counts[a] == 0:
                return a
        # UCB1
        best_arm = arms[0]
        best_score = -1e9
        for a in arms:
            avg = self.values[a]
            bonus = math.sqrt(2.0 * math.log(max(1, self.total)) / float(self.counts[a]))
            score = avg + bonus
            if score > best_score:
                best_score = score
                best_arm = a
        return best_arm
