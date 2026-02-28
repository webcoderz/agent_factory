"""Tests for the overhauled skills system."""
from __future__ import annotations

import pytest

from agent_ext.skills import (
    SkillSpec, LoadedSkill, create_skill,
    SkillRegistry, SkillLoader,
    CombinedRegistry, FilteredRegistry, PrefixedRegistry,
    SkillNotFoundError,
)


class TestCreateSkill:
    def test_basic_creation(self):
        skill = create_skill(
            id="test", name="Test", description="A test",
            body="# Test\n\nBody text",
        )
        assert skill.spec.id == "test"
        assert skill.spec.name == "Test"
        assert "# Test" in skill.body_markdown
        assert len(skill.body_hash) == 64  # sha256 hex

    def test_with_tags(self):
        skill = create_skill(
            id="t", name="T", description="d",
            body="body", tags=["python", "code"],
        )
        assert skill.spec.tags == ["python", "code"]


class TestCombinedRegistry:
    def _make_reg(self, skills: list[SkillSpec]) -> SkillRegistry:
        """Helper to make a registry with pre-loaded skills."""
        reg = SkillRegistry(roots=[])
        for s in skills:
            reg._skills[s.id] = s
        return reg

    def test_merge_two(self):
        r1 = self._make_reg([SkillSpec(id="a", name="A", description="d")])
        r2 = self._make_reg([SkillSpec(id="b", name="B", description="d")])
        combined = CombinedRegistry([r1, r2])
        ids = [s.id for s in combined.list()]
        assert "a" in ids
        assert "b" in ids

    def test_first_wins_on_conflict(self):
        r1 = self._make_reg([SkillSpec(id="x", name="First", description="d")])
        r2 = self._make_reg([SkillSpec(id="x", name="Second", description="d")])
        combined = CombinedRegistry([r1, r2])
        assert combined.get("x").name == "First"

    def test_get_missing_raises(self):
        combined = CombinedRegistry([])
        with pytest.raises(SkillNotFoundError):
            combined.get("nonexistent")


class TestFilteredRegistry:
    def test_filters_by_tag(self):
        reg = SkillRegistry(roots=[])
        reg._skills["a"] = SkillSpec(id="a", name="A", description="d", tags=["python"])
        reg._skills["b"] = SkillSpec(id="b", name="B", description="d", tags=["rust"])
        filtered = FilteredRegistry(reg, predicate=lambda s: "python" in s.tags)
        ids = [s.id for s in filtered.list()]
        assert ids == ["a"]

    def test_get_filtered_out_raises(self):
        reg = SkillRegistry(roots=[])
        reg._skills["a"] = SkillSpec(id="a", name="A", description="d", tags=["rust"])
        filtered = FilteredRegistry(reg, predicate=lambda s: "python" in s.tags)
        with pytest.raises(SkillNotFoundError):
            filtered.get("a")


class TestPrefixedRegistry:
    def test_prefix_applied(self):
        reg = SkillRegistry(roots=[])
        reg._skills["search"] = SkillSpec(id="search", name="Search", description="d")
        prefixed = PrefixedRegistry(reg, prefix="vendor_")
        ids = [s.id for s in prefixed.list()]
        assert ids == ["vendor_search"]

    def test_get_with_prefix(self):
        reg = SkillRegistry(roots=[])
        reg._skills["search"] = SkillSpec(id="search", name="Search", description="d")
        prefixed = PrefixedRegistry(reg, prefix="vendor_")
        spec = prefixed.get("vendor_search")
        assert spec.id == "vendor_search"
        assert spec.name == "Search"

    def test_get_without_prefix_raises(self):
        reg = SkillRegistry(roots=[])
        reg._skills["s"] = SkillSpec(id="s", name="S", description="d")
        prefixed = PrefixedRegistry(reg, prefix="v_")
        with pytest.raises(SkillNotFoundError):
            prefixed.get("s")
