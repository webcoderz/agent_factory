"""Skills — progressive-disclosure instruction packs for AI agents."""

from .models import LoadedSkill, SkillSpec, create_skill
from .registry import SkillRegistry
from .loader import SkillLoader
from .exceptions import SkillError, SkillNotFoundError, SkillValidationError, SkillLoadError
from .registries import CombinedRegistry, FilteredRegistry, PrefixedRegistry

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
