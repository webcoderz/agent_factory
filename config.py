from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List


class SkillsConfig(BaseModel):
    roots: List[str] = Field(default_factory=lambda: ["skills"])
    max_skill_bytes: int = 256_000
    allow_skill_tools: bool = True


class MemoryConfig(BaseModel):
    max_messages: int = 80
    preserve_tool_pairs: bool = True


class BackendsConfig(BaseModel):
    fs_root: str = "."
    exec_enabled: bool = False


class AgentsExtConfig(BaseModel):
    skills: SkillsConfig = SkillsConfig()
    memory: MemoryConfig = MemoryConfig()
    backends: BackendsConfig = BackendsConfig()
