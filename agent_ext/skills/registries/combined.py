"""Combined registry — merge multiple registries into one."""
from __future__ import annotations

from typing import List

from ..models import SkillSpec
from ..exceptions import SkillNotFoundError


class CombinedRegistry:
    """Merges multiple registries, first-match wins on conflicts."""

    def __init__(self, registries: list) -> None:
        self._registries = list(registries)

    def list(self) -> List[SkillSpec]:
        seen: set[str] = set()
        result: list[SkillSpec] = []
        for reg in self._registries:
            for spec in reg.list():
                if spec.id not in seen:
                    seen.add(spec.id)
                    result.append(spec)
        return result

    def get(self, skill_id: str) -> SkillSpec:
        for reg in self._registries:
            try:
                return reg.get(skill_id)
            except (KeyError, SkillNotFoundError):
                continue
        raise SkillNotFoundError(skill_id)

    def has(self, skill_id: str) -> bool:
        return any(
            (hasattr(r, "has") and r.has(skill_id)) or skill_id in {s.id for s in r.list()}
            for r in self._registries
        )
