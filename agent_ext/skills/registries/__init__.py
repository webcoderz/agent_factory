"""Composable skill registries — combine, filter, prefix, rename, wrap."""

from .combined import CombinedRegistry
from .filtered import FilteredRegistry
from .prefixed import PrefixedRegistry
from .renamed import RenamedRegistry
from .wrapper import WrapperRegistry

__all__ = ["CombinedRegistry", "FilteredRegistry", "PrefixedRegistry", "RenamedRegistry", "WrapperRegistry"]
