"""Permission system for backend operations.

Fine-grained access control with presets (read-only, full-access, etc.)
and pattern-based rules.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

PermissionAction = Literal["allow", "deny", "ask"]
PermissionOperation = Literal["read", "write", "edit", "execute", "glob", "grep", "ls"]


@dataclass(frozen=True)
class PermissionRule:
    """A rule matching paths/commands to an action.  First match wins."""
    pattern: str
    action: PermissionAction
    description: str = ""


@dataclass
class OperationPermissions:
    """Permissions for a single operation type."""
    default: PermissionAction = "allow"
    rules: list[PermissionRule] = field(default_factory=list)

    def check(self, path: str) -> PermissionAction:
        for rule in self.rules:
            if fnmatch.fnmatch(path, rule.pattern):
                return rule.action
        return self.default


@dataclass
class PermissionRuleset:
    """Complete permissions configuration for all operations."""
    default: PermissionAction = "ask"
    read: OperationPermissions | None = None
    write: OperationPermissions | None = None
    edit: OperationPermissions | None = None
    execute: OperationPermissions | None = None
    glob: OperationPermissions | None = None
    grep: OperationPermissions | None = None
    ls: OperationPermissions | None = None

    def get_operation_permissions(self, operation: PermissionOperation) -> OperationPermissions:
        op_perms = getattr(self, operation, None)
        if op_perms is not None:
            return op_perms
        return OperationPermissions(default=self.default)

    def check(self, operation: PermissionOperation, path: str) -> PermissionAction:
        return self.get_operation_permissions(operation).check(path)


class PermissionChecker:
    """Checks operations against a ``PermissionRuleset``."""

    def __init__(self, ruleset: PermissionRuleset) -> None:
        self.ruleset = ruleset

    def check(self, operation: PermissionOperation, path: str) -> PermissionAction:
        return self.ruleset.check(operation, path)

    def is_allowed(self, operation: PermissionOperation, path: str) -> bool:
        return self.check(operation, path) == "allow"

    def require(self, operation: PermissionOperation, path: str) -> None:
        """Raise ``PermissionError`` if not allowed."""
        action = self.check(operation, path)
        if action == "deny":
            raise PermissionError(f"Operation '{operation}' denied for path: {path}")
        if action == "ask":
            raise PermissionError(f"Operation '{operation}' requires approval for path: {path}")


# ---------------------------------------------------------------------------
# Common sensitive file patterns
# ---------------------------------------------------------------------------

SECRETS_PATTERNS = [
    "**/.env", "**/.env.*", "**/*.pem", "**/*.key", "**/*.crt",
    "**/credentials*", "**/secrets*", "**/*secret*", "**/*password*",
    "**/.aws/**", "**/.ssh/**",
]


def _deny_rules(patterns: list[str], desc: str) -> list[PermissionRule]:
    return [PermissionRule(pattern=p, action="deny", description=desc) for p in patterns]


# ---------------------------------------------------------------------------
# Preset rulesets
# ---------------------------------------------------------------------------

READONLY_RULESET = PermissionRuleset(
    default="deny",
    read=OperationPermissions(default="allow", rules=_deny_rules(SECRETS_PATTERNS, "Protect secrets")),
    write=OperationPermissions(default="deny"),
    edit=OperationPermissions(default="deny"),
    execute=OperationPermissions(default="deny"),
    glob=OperationPermissions(default="allow"),
    grep=OperationPermissions(default="allow"),
    ls=OperationPermissions(default="allow"),
)

PERMISSIVE_RULESET = PermissionRuleset(
    default="allow",
    read=OperationPermissions(default="allow", rules=_deny_rules(SECRETS_PATTERNS, "Protect secrets")),
    write=OperationPermissions(default="allow", rules=_deny_rules(SECRETS_PATTERNS, "Protect secrets")),
    edit=OperationPermissions(default="allow", rules=_deny_rules(SECRETS_PATTERNS, "Protect secrets")),
    execute=OperationPermissions(default="allow"),
    glob=OperationPermissions(default="allow"),
    grep=OperationPermissions(default="allow"),
    ls=OperationPermissions(default="allow"),
)

DEFAULT_RULESET = PermissionRuleset(
    default="ask",
    read=OperationPermissions(default="allow", rules=_deny_rules(SECRETS_PATTERNS, "Protect secrets")),
    write=OperationPermissions(default="ask", rules=_deny_rules(SECRETS_PATTERNS, "Protect secrets")),
    edit=OperationPermissions(default="ask", rules=_deny_rules(SECRETS_PATTERNS, "Protect secrets")),
    execute=OperationPermissions(default="ask"),
    glob=OperationPermissions(default="allow"),
    grep=OperationPermissions(default="allow"),
    ls=OperationPermissions(default="allow"),
)

STRICT_RULESET = PermissionRuleset(
    default="ask",
    read=OperationPermissions(default="ask", rules=_deny_rules(SECRETS_PATTERNS, "Protect secrets")),
    write=OperationPermissions(default="ask", rules=_deny_rules(SECRETS_PATTERNS, "Protect secrets")),
    edit=OperationPermissions(default="ask", rules=_deny_rules(SECRETS_PATTERNS, "Protect secrets")),
    execute=OperationPermissions(default="ask"),
    glob=OperationPermissions(default="ask"),
    grep=OperationPermissions(default="ask"),
    ls=OperationPermissions(default="ask"),
)


def create_ruleset(
    *,
    default: PermissionAction = "ask",
    allow_read: bool = True,
    allow_write: bool = False,
    allow_edit: bool = False,
    allow_execute: bool = False,
    allow_glob: bool = True,
    allow_grep: bool = True,
    allow_ls: bool = True,
    deny_secrets: bool = True,
) -> PermissionRuleset:
    """Convenience factory for custom rulesets."""
    def _act(allowed: bool) -> PermissionAction:
        return "allow" if allowed else "ask"

    secret_rules = _deny_rules(SECRETS_PATTERNS, "Protect secrets") if deny_secrets else []
    return PermissionRuleset(
        default=default,
        read=OperationPermissions(default=_act(allow_read), rules=secret_rules),
        write=OperationPermissions(default=_act(allow_write), rules=secret_rules),
        edit=OperationPermissions(default=_act(allow_edit), rules=secret_rules),
        execute=OperationPermissions(default=_act(allow_execute)),
        glob=OperationPermissions(default=_act(allow_glob)),
        grep=OperationPermissions(default=_act(allow_grep)),
        ls=OperationPermissions(default=_act(allow_ls)),
    )
