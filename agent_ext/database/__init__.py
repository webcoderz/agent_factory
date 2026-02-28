"""Database toolset — SQL capabilities for AI agents."""

from .postgres import PostgresDatabase
from .protocol import DatabaseBackend
from .sqlite import SQLiteDatabase
from .toolset import DATABASE_SYSTEM_PROMPT, SQLDatabaseDeps, create_database_toolset
from .types import DatabaseConfig, QueryResult, SchemaInfo, TableInfo

__all__ = [
    "QueryResult",
    "SchemaInfo",
    "TableInfo",
    "DatabaseConfig",
    "DatabaseBackend",
    "SQLiteDatabase",
]
