from __future__ import annotations

from agent_ext.modules.spec import ModuleProvides, ModuleSpec
from agent_ext.self_improve.controller import SelfImproveController


def init(ctx) -> None:
    ctx.self_improve = SelfImproveController()

    # optional commands for the TUI
    def cmd_improve_status() -> str:
        return "Self-improve enabled. Records in .agent_state/runs/"

    ctx.commands["/improve_status"] = cmd_improve_status


module_spec = ModuleSpec(
    name="self_improve",
    version="0.1.0",
    description="Trigger-driven self-improvement loop (gated).",
    provides=ModuleProvides(commands=["/improve_status"]),
    init=init,
)
