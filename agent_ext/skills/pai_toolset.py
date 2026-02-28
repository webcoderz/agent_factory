"""Skills FunctionToolset — progressive-disclosure skill discovery for pydantic-ai agents.

Tools: list_skills, load_skill.

Example::

    from pydantic_ai import Agent
    from agent_ext.skills import create_skills_toolset, SkillsDeps, SkillRegistry

    registry = SkillRegistry(roots=["skills"])
    registry.discover()

    toolset = create_skills_toolset()
    agent = Agent("openai:gpt-4o", toolsets=[toolset])

    deps = SkillsDeps(registry=registry)
    result = await agent.run("What skills are available?", deps=deps)
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, SkipValidation
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from .loader import SkillLoader
from .models import SkillSpec


class SkillsDeps(BaseModel):
    """Dependencies for the skills toolset."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    registry: Annotated[Any, SkipValidation]  # SkillRegistry or any registry with list()/get()
    loader: Annotated[Any, SkipValidation] = None  # SkillLoader (created if None)
    max_body_chars: int = 10_000


def create_skills_toolset(*, toolset_id: str | None = None) -> FunctionToolset[SkillsDeps]:
    """Create a skills toolset for progressive-disclosure skill usage.

    Returns:
        FunctionToolset with list_skills and load_skill tools.
    """
    toolset: FunctionToolset[SkillsDeps] = FunctionToolset(id=toolset_id)

    @toolset.tool
    async def list_skills(ctx: RunContext[SkillsDeps]) -> str:
        """List all available skills with their IDs and descriptions.

        Use this to discover what skills are available before loading one.
        """
        skills = ctx.deps.registry.list()
        if not skills:
            return "No skills available."
        lines = []
        for s in skills:
            tags = f" [{', '.join(s.tags)}]" if s.tags else ""
            lines.append(f"- **{s.id}**: {s.description}{tags}")
        return "\n".join(lines)

    @toolset.tool
    async def load_skill(ctx: RunContext[SkillsDeps], skill_id: str) -> str:
        """Load the full instructions for a specific skill.

        Args:
            skill_id: The skill ID to load (from list_skills).

        Returns:
            The skill's markdown instructions.
        """
        try:
            spec = ctx.deps.registry.get(skill_id)
        except (KeyError, Exception):
            return f"Error: Skill '{skill_id}' not found. Use list_skills to see available skills."

        loader = ctx.deps.loader or SkillLoader()
        try:
            loaded = loader.load(spec)
            body = loaded.body_markdown
            if len(body) > ctx.deps.max_body_chars:
                body = body[: ctx.deps.max_body_chars] + "\n\n... (truncated)"
            return f"# Skill: {spec.name}\n\n{body}"
        except Exception as e:
            return f"Error loading skill '{skill_id}': {e}"

    return toolset
