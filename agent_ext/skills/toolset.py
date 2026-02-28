from __future__ import annotations

from .models import LoadedSkill, SkillSpec


class SkillContextPack:
    """
    What you inject into the model context.
    """

    def __init__(self, *, catalog_text: str, loaded_skills: list[LoadedSkill]):
        self.catalog_text = catalog_text
        self.loaded_skills = loaded_skills

    def as_instructions(self) -> str:
        out = [self.catalog_text]
        for sk in self.loaded_skills:
            out.append("\n\n---\n\n")
            out.append(f"# Skill: {sk.spec.id} ({sk.spec.version})\n")
            out.append(sk.body_markdown)
        return "".join(out)


def build_skill_catalog(catalog: list[SkillSpec]) -> str:
    lines = ["You have access to the following skills (load full instructions only when needed):\n"]
    for s in sorted(catalog, key=lambda x: x.id):
        tag_str = f" [{', '.join(s.tags)}]" if s.tags else ""
        lines.append(f"- {s.id}: {s.name} — {s.description}{tag_str}\n")
    return "".join(lines)
