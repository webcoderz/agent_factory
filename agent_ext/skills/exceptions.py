"""Exceptions for the skills system."""
from __future__ import annotations


class SkillError(Exception):
    """Base exception for skill operations."""


class SkillNotFoundError(SkillError):
    """Raised when a skill is not found in any registry."""

    def __init__(self, skill_id: str):
        self.skill_id = skill_id
        super().__init__(f"Skill not found: {skill_id}")


class SkillValidationError(SkillError):
    """Raised when skill metadata or structure is invalid."""

    def __init__(self, skill_id: str, reason: str):
        self.skill_id = skill_id
        self.reason = reason
        super().__init__(f"Skill '{skill_id}' validation failed: {reason}")


class SkillLoadError(SkillError):
    """Raised when a skill cannot be loaded."""

    def __init__(self, skill_id: str, reason: str):
        self.skill_id = skill_id
        self.reason = reason
        super().__init__(f"Skill '{skill_id}' load failed: {reason}")
