# Backends — File Storage, Execution & Permissions

Everything an AI agent needs to work with files and execute code safely.

## Features

- **Local Filesystem**: Sandboxed read/write/list/glob within a root directory
- **State Backend**: In-memory filesystem for testing (no disk needed)
- **Subprocess Execution**: Run commands with timeout and capture
- **Permission System**: Fine-grained access control with presets
- **Hashline**: Content-hash line editing for precise, low-token edits

## Backends

| Backend | Use Case |
|---------|----------|
| `LocalFilesystemBackend` | Real filesystem, sandboxed to root dir |
| `LocalSubprocessExecBackend` | Run shell commands |
| `StateBackend` | In-memory, ephemeral — perfect for tests |

## Permission Presets

| Preset | Read | Write | Execute |
|--------|------|-------|---------|
| `READONLY_RULESET` | ✅ | ❌ | ❌ |
| `DEFAULT_RULESET` | ✅ | Ask | Ask |
| `PERMISSIVE_RULESET` | ✅ | ✅ | ✅ |
| `STRICT_RULESET` | Ask | Ask | Ask |

All presets deny access to `.env`, `.pem`, `.key`, credentials, etc.

## Hashline Editing

```python
from agent_ext.backends import format_hashline_output, apply_hashline_edit

# Format file with hashline tags
tagged = format_hashline_output("def hello():\n    return 42\n")
# 1:a3|def hello():
# 2:f1|    return 42

# Edit by line number + hash (no text matching needed)
new_content, error = apply_hashline_edit(
    "def hello():\n    return 42\n",
    start_line=2, start_hash="f1",
    new_content="    return 99",
)
```

## State Backend (Testing)

```python
from agent_ext.backends import StateBackend

backend = StateBackend()
backend.write_text("src/app.py", "print('hello')")
content = backend.read_text("src/app.py")

# Rich operations
matches = backend.grep_raw("print")
result = backend.edit("src/app.py", "hello", "world")
```
