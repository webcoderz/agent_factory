"""Skills — progressive-disclosure instruction packs for AI agents."""

from .exceptions import SkillError, SkillLoadError, SkillNotFoundError, SkillValidationError
from .loader import SkillLoader
from .models import LoadedSkill, SkillSpec, create_skill
from .registries import CombinedRegistry, FilteredRegistry, PrefixedRegistry
from .registry import SkillRegistry

__all__ = [
    "LoadedSkill",
    "SkillSpec",
    "create_skill",
    "SkillRegistry",
    "SkillLoader",
    "SkillError",
    "SkillNotFoundError",
    "SkillValidationError",
    "SkillLoadError",
    "CombinedRegistry",
    "FilteredRegistry",
    "PrefixedRegistry",
]
