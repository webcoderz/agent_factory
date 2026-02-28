"""Database toolset — SQL capabilities for AI agents."""

from .types import QueryResult, SchemaInfo, TableInfo, DatabaseConfig
from .protocol import DatabaseBackend
from .sqlite import SQLiteDatabase
from .toolset import create_database_toolset, SQLDatabaseDeps, DATABASE_SYSTEM_PROMPT

__all__ = [
    "QueryResult",
    "SchemaInfo",
    "TableInfo",
    "DatabaseConfig",
    "DatabaseBackend",
    "SQLiteDatabase",
]
