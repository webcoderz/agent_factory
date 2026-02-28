# Skills — Progressive-Disclosure Instruction Packs

Modular skill system for AI agents with discovery, loading, validation, and composable registries.

## Features

- **Directory Discovery**: `skills/<id>/SKILL.md` convention
- **Programmatic Creation**: Define skills in code (no filesystem)
- **Registry Composition**: Combine, filter, prefix registries
- **Validation**: Metadata and structure validation
- **Progressive Disclosure**: List → get → load (minimal tokens)

## Quick Start

```python
from agent_ext.skills import SkillRegistry, SkillLoader, create_skill

# Discover from directories
registry = SkillRegistry(roots=["skills", "vendor/skills"])
registry.discover()

# Load a skill
loader = SkillLoader(max_bytes=256_000)
loaded = loader.load(registry.get("my_skill"))
print(loaded.body_markdown)
```

## Programmatic Skills

```python
from agent_ext.skills import create_skill

skill = create_skill(
    id="code_review",
    name="Code Review",
    description="Review code for quality and bugs",
    body="# Code Review\n\nReview the code for...",
    tags=["code", "review"],
)
```

## Registry Composition

```python
from agent_ext.skills import (
    SkillRegistry, CombinedRegistry, FilteredRegistry, PrefixedRegistry,
)

# Combine multiple sources
local = SkillRegistry(roots=["skills"])
local.discover()

vendor = SkillRegistry(roots=["vendor/skills"])
vendor.discover()

# Merge, filter, or prefix
combined = CombinedRegistry([local, vendor])
python_only = FilteredRegistry(combined, predicate=lambda s: "python" in s.tags)
namespaced = PrefixedRegistry(vendor, prefix="vendor_")
```
