from __future__ import annotations

from agent_ext.modules.spec import ModuleProvides, ModuleSpec


def init(ctx) -> None:
    # TUI already handles /workflows /assemble /exec; this is just a marker for module registry
    ctx.commands.setdefault("/workflows", lambda: "Use the TUI command /workflows")
    ctx.commands.setdefault("/assemble", lambda: "Use: /assemble <task_type> <text>")
    ctx.commands.setdefault("/exec", lambda: "Use: /exec <task_type> <text>")


module_spec = ModuleSpec(
    name="workflow",
    version="0.1.0",
    description="Workflow synthesis + execution + learning (bandit over assemblies).",
    provides=ModuleProvides(commands=["/workflows", "/assemble", "/exec"]),
    init=init,
)
