"""Composable skill registries — combine, filter, prefix, rename, wrap, git."""

from .combined import CombinedRegistry
from .filtered import FilteredRegistry
from .git import GitCloneOptions, GitSkillsRegistry
from .prefixed import PrefixedRegistry
from .renamed import RenamedRegistry
from .wrapper import WrapperRegistry

__all__ = [
    "CombinedRegistry",
    "FilteredRegistry",
    "GitCloneOptions",
    "GitSkillsRegistry",
    "PrefixedRegistry",
    "RenamedRegistry",
    "WrapperRegistry",
]
