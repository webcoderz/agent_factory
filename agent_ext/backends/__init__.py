"""File storage, execution, and permission backends for AI agents."""

from .base import ExecBackend, ExecResult, FilesystemBackend
from .local_fs import LocalFilesystemBackend
from .sandbox_exec import LocalSubprocessExecBackend
from .state import StateBackend, FileData, FileInfo, GrepMatch, EditResult, WriteResult
from .permissions import (
    DEFAULT_RULESET,
    PERMISSIVE_RULESET,
    READONLY_RULESET,
    STRICT_RULESET,
    OperationPermissions,
    PermissionAction,
    PermissionChecker,
    PermissionOperation,
    PermissionRule,
    PermissionRuleset,
    create_ruleset,
)
from .hashline import apply_hashline_edit, format_hashline_output, line_hash

__all__ = [
    # Base protocols
    "ExecBackend",
    "ExecResult",
    "FilesystemBackend",
    # Backends
    "LocalFilesystemBackend",
    "LocalSubprocessExecBackend",
    "StateBackend",
    # State backend types
    "FileData",
    "FileInfo",
    "GrepMatch",
    "EditResult",
    "WriteResult",
    # Permissions
    "DEFAULT_RULESET",
    "PERMISSIVE_RULESET",
    "READONLY_RULESET",
    "STRICT_RULESET",
    "OperationPermissions",
    "PermissionAction",
    "PermissionChecker",
    "PermissionOperation",
    "PermissionRule",
    "PermissionRuleset",
    "create_ruleset",
    # Hashline
    "apply_hashline_edit",
    "format_hashline_output",
    "line_hash",
]
