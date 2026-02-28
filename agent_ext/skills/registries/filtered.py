"""Filtered registry — expose only skills matching criteria."""

from __future__ import annotations

import builtins
from collections.abc import Callable

from ..exceptions import SkillNotFoundError
from ..models import SkillSpec


class FilteredRegistry:
    """Wraps a registry, only exposing skills that pass *predicate*.

    Example::

        # Only Python skills
        filtered = FilteredRegistry(
            base_registry,
            predicate=lambda spec: "python" in spec.tags,
        )
    """

    def __init__(self, inner, *, predicate: Callable[[SkillSpec], bool]) -> None:
        self._inner = inner
        self._predicate = predicate

    def list(self) -> builtins.list[SkillSpec]:
        return [s for s in self._inner.list() if self._predicate(s)]

    def get(self, skill_id: str) -> SkillSpec:
        spec = self._inner.get(skill_id)
        if not self._predicate(spec):
            raise SkillNotFoundError(skill_id)
        return spec

    def has(self, skill_id: str) -> bool:
        try:
            self.get(skill_id)
            return True
        except (KeyError, SkillNotFoundError):
            return False
