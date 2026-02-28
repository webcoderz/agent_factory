"""Wrapper base class for registry composition.

All registry decorators (Filtered, Prefixed, Renamed) can inherit from this.
"""

from __future__ import annotations

import builtins

from ..models import SkillSpec


class WrapperRegistry:
    """A registry that wraps another and delegates all operations.

    Override only the methods you need to customize.
    """

    def __init__(self, inner) -> None:
        self._inner = inner

    @property
    def wrapped(self):
        return self._inner

    def list(self) -> builtins.list[SkillSpec]:
        return self._inner.list()

    def get(self, skill_id: str) -> SkillSpec:
        return self._inner.get(skill_id)

    def has(self, skill_id: str) -> bool:
        try:
            self._inner.get(skill_id)
            return True
        except (KeyError, Exception):
            return False
