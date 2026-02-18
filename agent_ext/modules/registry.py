from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .loader import import_module
from .spec import ModuleSpec, ModuleState

STATE_FILE_DEFAULT = Path(".agent_state/registry.json")


class ModuleRegistry:
    """
    Discovers module.py files under agent_ext/modules/builtins/*/module.py,
    imports them, and enables their init(ctx) hooks.
    """

    def __init__(self, *, state_file: Path = STATE_FILE_DEFAULT):
        self.state_file = state_file
        self.modules: Dict[str, ModuleState] = {}

    def discover_builtin_import_paths(self) -> List[str]:
        root = Path(__file__).resolve().parent / "builtins"
        paths: List[str] = []
        if not root.exists():
            return paths
        for mod_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            candidate = mod_dir / "module.py"
            if candidate.exists():
                # agent_ext.modules.builtins.<name>.module
                paths.append(f"agent_ext.modules.builtins.{mod_dir.name}.module")
        return paths

    def load_from_import_path(self, import_path: str) -> ModuleSpec:
        mod = import_module(import_path)
        spec: Optional[ModuleSpec] = getattr(mod, "module_spec", None)
        if spec is None:
            raise RuntimeError(f"{import_path} must define `module_spec: ModuleSpec`")
        return spec

    def enable(self, spec: ModuleSpec, *, import_path: str, ctx) -> None:
        state = ModuleState(spec=spec, enabled=True, loaded_from=import_path)
        self.modules[spec.name] = state
        if spec.init is not None:
            spec.init(ctx)

    def disable(self, name: str) -> None:
        if name in self.modules:
            self.modules[name].enabled = False

    def enabled_specs(self) -> Iterable[ModuleSpec]:
        for st in self.modules.values():
            if st.enabled:
                yield st.spec

    def save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "modules": [
                {
                    "name": st.spec.name,
                    "version": st.spec.version,
                    "description": st.spec.description,
                    "enabled": st.enabled,
                    "loaded_from": st.loaded_from,
                }
                for st in self.modules.values()
            ]
        }
        self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_saved(self) -> Dict[str, bool]:
        if not self.state_file.exists():
            return {}
        try:
            raw = self.state_file.read_text(encoding="utf-8").strip()
            if not raw:
                return {}
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError):
            return {}
        out: Dict[str, bool] = {}
        for item in data.get("modules", []):
            out[item["name"]] = bool(item.get("enabled", True))
        return out

    def load_all_builtins(self, ctx) -> None:
        enabled_map = self.load_saved()
        for import_path in self.discover_builtin_import_paths():
            spec = self.load_from_import_path(import_path)
            is_enabled = enabled_map.get(spec.name, True)
            if is_enabled:
                self.enable(spec, import_path=import_path, ctx=ctx)
            else:
                self.modules[spec.name] = ModuleState(spec=spec, enabled=False, loaded_from=import_path)
