from __future__ import annotations

import hashlib

from .models import LoadedSkill, SkillSpec


class SkillLoader:
    def __init__(self, *, max_bytes: int = 256_000):
        self.max_bytes = max_bytes

    def load(self, spec: SkillSpec) -> LoadedSkill:
        if not spec.path:
            raise ValueError(f"Skill has no path: {spec.id}")
        with open(spec.path, "rb") as f:
            raw = f.read()
        if len(raw) > self.max_bytes:
            raise ValueError(f"Skill too large ({len(raw)} bytes): {spec.id}")
        body = raw.decode("utf-8", errors="replace")
        h = hashlib.sha256(raw).hexdigest()
        return LoadedSkill(spec=spec, body_markdown=body, body_hash=h)
