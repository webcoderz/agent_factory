from __future__ import annotations
import hashlib
import os
from typing import Dict, List

from .models import SkillSpec


def _hash_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class SkillRegistry:
    """
    Discovers skills from directories. Convention:
      skills/<skill_id>/SKILL.md
      skills/<skill_id>/spec.json (optional)
    """
    def __init__(self, roots: List[str]):
        self.roots = roots
        self._skills: Dict[str, SkillSpec] = {}

    def discover(self) -> None:
        for root in self.roots:
            if not os.path.isdir(root):
                continue
            for entry in os.listdir(root):
                skill_dir = os.path.join(root, entry)
                if not os.path.isdir(skill_dir):
                    continue
                md_path = os.path.join(skill_dir, "SKILL.md")
                if not os.path.exists(md_path):
                    continue
                # Minimal spec derived from folder + first heading line
                with open(md_path, "r", encoding="utf-8") as f:
                    body = f.read()
                first_line = next((ln.strip("# ").strip() for ln in body.splitlines() if ln.strip()), entry)
                spec = SkillSpec(
                    id=entry,
                    name=first_line or entry,
                    description=f"Skill {entry}",
                    path=md_path,
                    metadata={"body_hash": _hash_text(body)},
                )
                self._skills[spec.id] = spec

    def list(self) -> List[SkillSpec]:
        return list(self._skills.values())

    def get(self, skill_id: str) -> SkillSpec:
        return self._skills[skill_id]
