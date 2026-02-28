from __future__ import annotations

from agent_ext.modules.spec import ModuleProvides, ModuleSpec


def init(ctx) -> None:
    # Keep core tiny: just ensure these dicts exist so modules can register into them.
    if getattr(ctx, "commands", None) is None:
        ctx.commands = {}
    if getattr(ctx, "events", None) is None:
        ctx.events = {}
    # A place to register interactive commands (like /status, /modules, etc.)


module_spec = ModuleSpec(
    name="core",
    version="0.1.0",
    description="Core runtime scaffolding for the workbench.",
    provides=ModuleProvides(commands=["/status", "/modules", "/help"]),
    init=init,
)
