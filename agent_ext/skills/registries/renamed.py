"""Renamed registry — rename skills using an explicit mapping.

``name_map`` maps **new names to original names**: ``{'new-name': 'original-name'}``.
Skills not in the map keep their original names.

Example::

    renamed = RenamedRegistry(base, name_map={"doc-tool": "pdf", "sheet-tool": "xlsx"})
    spec = renamed.get("doc-tool")  # fetches "pdf" from base
"""

from __future__ import annotations

from ..exceptions import SkillNotFoundError
from ..models import SkillSpec
from .wrapper import WrapperRegistry


class RenamedRegistry(WrapperRegistry):
    """A registry that renames skills using a name map."""

    def __init__(self, inner, *, name_map: dict[str, str]) -> None:
        super().__init__(inner)
        self.name_map = name_map  # new_name → original_name

    @property
    def _reverse_map(self) -> dict[str, str]:
        """original_name → new_name."""
        return {v: k for k, v in self.name_map.items()}

    def _to_new(self, spec: SkillSpec) -> SkillSpec:
        new_name = self._reverse_map.get(spec.id)
        if new_name:
            return SkillSpec(
                id=new_name,
                name=spec.name,
                description=spec.description,
                tags=spec.tags,
                version=spec.version,
                path=spec.path,
                required_perms=spec.required_perms,
                tool_bundle=spec.tool_bundle,
                metadata=spec.metadata,
            )
        return spec

    def list(self) -> list[SkillSpec]:
        return [self._to_new(s) for s in self._inner.list()]

    def get(self, skill_id: str) -> SkillSpec:
        original = self.name_map.get(skill_id, skill_id)
        try:
            spec = self._inner.get(original)
        except (KeyError, SkillNotFoundError):
            raise SkillNotFoundError(skill_id) from None
        return self._to_new(spec)

    def has(self, skill_id: str) -> bool:
        original = self.name_map.get(skill_id, skill_id)
        try:
            self._inner.get(original)
            return True
        except (KeyError, SkillNotFoundError):
            return False
