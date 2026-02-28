"""Type definitions for the database system."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DatabaseConfig:
    """Configuration for database access."""
    read_only: bool = True
    max_rows: int = 1000
    timeout_s: float = 30.0
    max_query_length: int = 10_000


@dataclass
class TableInfo:
    """Metadata about a database table."""
    name: str
    columns: list[dict[str, Any]] = field(default_factory=list)
    row_count: int | None = None


@dataclass
class SchemaInfo:
    """Full database schema."""
    tables: list[TableInfo] = field(default_factory=list)
    database_type: str = ""
    database_path: str = ""


@dataclass
class QueryResult:
    """Result of a SQL query."""
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    error: str | None = None
    execution_time_ms: float = 0.0
