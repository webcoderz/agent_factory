"""Prefixed registry — namespace skills with a prefix."""
from __future__ import annotations

from typing import List

from ..models import SkillSpec
from ..exceptions import SkillNotFoundError


class PrefixedRegistry:
    """Wraps a registry, prefixing all skill IDs.

    Example::

        prefixed = PrefixedRegistry(base, prefix="vendor_")
        # Skill "search" becomes "vendor_search"
    """

    def __init__(self, inner, *, prefix: str) -> None:
        self._inner = inner
        self._prefix = prefix

    def _prefixed(self, spec: SkillSpec) -> SkillSpec:
        return SkillSpec(
            id=f"{self._prefix}{spec.id}",
            name=spec.name,
            description=spec.description,
            tags=spec.tags,
            version=spec.version,
            path=spec.path,
            required_perms=spec.required_perms,
            tool_bundle=spec.tool_bundle,
            metadata=spec.metadata,
        )

    def list(self) -> List[SkillSpec]:
        return [self._prefixed(s) for s in self._inner.list()]

    def get(self, skill_id: str) -> SkillSpec:
        if not skill_id.startswith(self._prefix):
            raise SkillNotFoundError(skill_id)
        inner_id = skill_id[len(self._prefix):]
        return self._prefixed(self._inner.get(inner_id))

    def has(self, skill_id: str) -> bool:
        if not skill_id.startswith(self._prefix):
            return False
        inner_id = skill_id[len(self._prefix):]
        try:
            self._inner.get(inner_id)
            return True
        except (KeyError, SkillNotFoundError):
            return False
