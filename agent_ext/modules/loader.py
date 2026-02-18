from __future__ import annotations

import importlib
from types import ModuleType


def import_module(import_path: str) -> ModuleType:
    return importlib.import_module(import_path)


def reload_module(mod: ModuleType) -> ModuleType:
    return importlib.reload(mod)
