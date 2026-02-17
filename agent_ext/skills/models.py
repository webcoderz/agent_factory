from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SkillSpec(BaseModel):
    id: str
    name: str
    description: str
    tags: List[str] = Field(default_factory=list)
    version: str = "0.1.0"
    path: Optional[str] = None              # where SKILL.md lives
    required_perms: List[str] = Field(default_factory=list)
    tool_bundle: Optional[str] = None       # optional name -> tools enabled when active
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LoadedSkill(BaseModel):
    spec: SkillSpec
    body_markdown: str
    body_hash: str
