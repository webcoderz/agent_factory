"""Skill models — specs, loaded skills, and programmatic creation."""

from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel, Field


class SkillSpec(BaseModel):
    """Metadata for a discoverable skill."""

    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    version: str = "0.1.0"
    path: str | None = None  # where SKILL.md lives
    required_perms: list[str] = Field(default_factory=list)
    tool_bundle: str | None = None  # optional name → tools enabled when active
    metadata: dict[str, Any] = Field(default_factory=dict)


class LoadedSkill(BaseModel):
    """A skill with its body loaded into memory."""

    spec: SkillSpec
    body_markdown: str
    body_hash: str


def create_skill(
    *,
    id: str,
    name: str,
    description: str,
    body: str,
    tags: list[str] | None = None,
    version: str = "0.1.0",
    required_perms: list[str] | None = None,
    tool_bundle: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> LoadedSkill:
    """Programmatically create a skill (no filesystem needed).

    Example::

        skill = create_skill(
            id="code_review",
            name="Code Review",
            description="Review code for quality and bugs",
            body="# Code Review\\n\\nReview the code for...\\n",
            tags=["code", "review"],
        )
    """
    spec = SkillSpec(
        id=id,
        name=name,
        description=description,
        tags=tags or [],
        version=version,
        required_perms=required_perms or [],
        tool_bundle=tool_bundle,
        metadata=metadata or {},
    )
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return LoadedSkill(spec=spec, body_markdown=body, body_hash=body_hash)
