"""Composable skill registries — combine, filter, prefix, rename."""

from .combined import CombinedRegistry
from .filtered import FilteredRegistry
from .prefixed import PrefixedRegistry

__all__ = ["CombinedRegistry", "FilteredRegistry", "PrefixedRegistry"]
