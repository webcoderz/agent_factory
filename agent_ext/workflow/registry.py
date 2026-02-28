from __future__ import annotations

from dataclasses import dataclass

from .types import Component, WorkflowSpec


@dataclass
class Registry:
    components: dict[str, Component]
    workflows: dict[str, WorkflowSpec]

    def __init__(self):
        self.components = {}
        self.workflows = {}

    def register_component(self, name: str, component: Component) -> None:
        self.components[name] = component

    def register_workflow(self, wf: WorkflowSpec) -> None:
        self.workflows[wf.name] = wf

    def list_components(self) -> list[str]:
        return sorted(self.components.keys())

    def list_workflows(self) -> list[str]:
        return sorted(self.workflows.keys())

    def get_component(self, name: str) -> Component:
        return self.components[name]

    def find_components_by_tag(self, tag: str) -> list[str]:
        out = []
        for name, c in self.components.items():
            if tag in c.capability.tags:
                out.append(name)
        return sorted(out)

    def workflow_capability_signature(self, wf: WorkflowSpec) -> tuple[str, ...]:
        tags = []
        for step in wf.steps:
            comp = self.components.get(step.component_name)
            if comp:
                tags.extend(list(comp.capability.tags))
        return tuple(sorted(set(tags)))
