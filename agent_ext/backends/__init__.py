"""File storage, execution, and permission backends for AI agents."""

from .base import ExecBackend, ExecResult, FilesystemBackend
from .console import CONSOLE_SYSTEM_PROMPT, ConsoleDeps, create_console_toolset
from .hashline import apply_hashline_edit, format_hashline_output, line_hash
from .local_fs import LocalFilesystemBackend
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
from .sandbox_exec import LocalSubprocessExecBackend
from .state import EditResult, FileData, FileInfo, GrepMatch, StateBackend, WriteResult

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
