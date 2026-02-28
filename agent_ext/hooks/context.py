"""Middleware context for sharing data across the middleware execution chain.

Provides a context system with strict access controls:
- Each hook can only *write* to its own namespace
- Each hook can only *read* from earlier hooks in the execution chain
- ``on_error`` / ``on_tool_error`` can read everything
"""
from __future__ import annotations

from collections.abc import Mapping
from enum import IntEnum
from typing import Any


class HookType(IntEnum):
    """Execution order of middleware hooks.

    The integer value represents execution order.  A hook can only read
    data from hooks with *lower* values (earlier in the chain).
    """

    BEFORE_RUN = 1
    BEFORE_MODEL_REQUEST = 2
    BEFORE_TOOL_CALL = 3
    ON_TOOL_ERROR = 4
    AFTER_TOOL_CALL = 5
    AFTER_RUN = 6
    ON_ERROR = 7  # special: can read all


class ContextAccessError(Exception):
    """Raised when middleware attempts unauthorized context access."""


class ScopedContext:
    """A scoped view of ``MiddlewareContext`` for a specific hook.

    Enforces access control:
    - Can only *write* to the current hook's namespace
    - Can only *read* from the current and earlier hooks' namespaces
    """

    def __init__(self, parent: MiddlewareContext, current_hook: HookType) -> None:
        self._parent = parent
        self._current_hook = current_hook

    # -- read-only global state ---------------------------------------------

    @property
    def config(self) -> Mapping[str, Any]:
        """Read-only access to global configuration."""
        return self._parent.config

    @property
    def metadata(self) -> Mapping[str, Any]:
        """Read-only access to execution metadata."""
        return self._parent.metadata

    @property
    def current_hook(self) -> HookType:
        return self._current_hook

    # -- access control -----------------------------------------------------

    def _can_read(self, hook: HookType) -> bool:
        if self._current_hook in (HookType.ON_ERROR, HookType.ON_TOOL_ERROR):
            return True
        return hook <= self._current_hook

    # -- write (only to own namespace) --------------------------------------

    def set(self, key: str, value: Any) -> None:
        """Store *key* → *value* in the current hook's namespace."""
        self._parent._set_hook_data(self._current_hook, key, value)

    # -- read ---------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the current hook's namespace."""
        return self.get_from(self._current_hook, key, default)

    def get_from(self, hook: HookType, key: str, default: Any = None) -> Any:
        """Get a value from another hook's namespace (respecting access control)."""
        if not self._can_read(hook):
            raise ContextAccessError(
                f"Hook '{self._current_hook.name}' cannot read from "
                f"'{hook.name}' (later in execution chain)"
            )
        return self._parent._get_hook_data(hook, key, default)

    def get_all_from(self, hook: HookType) -> Mapping[str, Any]:
        """Get all data from a hook's namespace."""
        if not self._can_read(hook):
            raise ContextAccessError(
                f"Hook '{self._current_hook.name}' cannot read from "
                f"'{hook.name}' (later in execution chain)"
            )
        return self._parent._get_all_hook_data(hook)

    def has_key(self, key: str) -> bool:
        return self.has_key_in(self._current_hook, key)

    def has_key_in(self, hook: HookType, key: str) -> bool:
        if not self._can_read(hook):
            raise ContextAccessError(
                f"Hook '{self._current_hook.name}' cannot read from "
                f"'{hook.name}' (later in execution chain)"
            )
        return self._parent._has_hook_key(hook, key)


class MiddlewareContext:
    """Context object for sharing data across the middleware chain.

    Provides:
    - Immutable global ``config``
    - Mutable ``metadata`` (timestamps, usage, etc.)
    - Per-hook namespaced storage with access control via ``ScopedContext``

    Example::

        ctx = MiddlewareContext(config={"rate_limit": 100})
        scoped = ctx.for_hook(HookType.BEFORE_RUN)
        scoped.set("user_intent", "question")

        later = ctx.for_hook(HookType.AFTER_RUN)
        intent = later.get_from(HookType.BEFORE_RUN, "user_intent")  # OK
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._config: dict[str, Any] = dict(config) if config else {}
        self._metadata: dict[str, Any] = dict(metadata) if metadata else {}
        self._hook_data: dict[HookType, dict[str, Any]] = {h: {} for h in HookType}

    # -- public read-only ---------------------------------------------------

    @property
    def config(self) -> Mapping[str, Any]:
        return self._config

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self._metadata

    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata (internal use, e.g. by MiddlewareAgent)."""
        self._metadata[key] = value

    # -- scoped access ------------------------------------------------------

    def for_hook(self, hook: HookType) -> ScopedContext:
        """Get a ``ScopedContext`` for the given hook."""
        return ScopedContext(self, hook)

    # -- internals ----------------------------------------------------------

    def _set_hook_data(self, hook: HookType, key: str, value: Any) -> None:
        self._hook_data[hook][key] = value

    def _get_hook_data(self, hook: HookType, key: str, default: Any = None) -> Any:
        return self._hook_data[hook].get(key, default)

    def _get_all_hook_data(self, hook: HookType) -> Mapping[str, Any]:
        return self._hook_data[hook]

    def _has_hook_key(self, hook: HookType, key: str) -> bool:
        return key in self._hook_data[hook]

    # -- cloning for parallel execution -------------------------------------

    def clone(self) -> MiddlewareContext:
        """Shallow clone for parallel middleware (prevents race conditions)."""
        new = MiddlewareContext(config=dict(self._config), metadata=dict(self._metadata))
        for hook, data in self._hook_data.items():
            new._hook_data[hook] = dict(data)
        return new

    def merge_from(self, other: MiddlewareContext, hook: HookType) -> None:
        """Merge data from *other*'s hook namespace into ours."""
        self._hook_data[hook].update(other._hook_data[hook])

    def reset(self) -> None:
        """Clear per-run state (metadata + hook data), keep config."""
        self._metadata.clear()
        for hook in HookType:
            self._hook_data[hook].clear()
