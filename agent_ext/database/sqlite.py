"""SQLite database backend with security controls."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from .types import DatabaseConfig, QueryResult, SchemaInfo, TableInfo


class SQLiteDatabase:
    """SQLite database backend.

    Provides schema exploration, query execution, and security controls
    (read-only mode, row limits, query timeouts).

    Example::

        db = SQLiteDatabase("my_data.db")
        await db.connect()
        tables = await db.list_tables()
        result = await db.execute_query("SELECT * FROM users LIMIT 10")
        await db.disconnect()
    """

    def __init__(
        self,
        path: str | Path,
        config: DatabaseConfig | None = None,
    ) -> None:
        self.path = str(path)
        self.config = config or DatabaseConfig()
        self._conn: sqlite3.Connection | None = None

    async def connect(self) -> None:
        uri = f"file:{self.path}"
        if self.config.read_only:
            uri += "?mode=ro"
        self._conn = sqlite3.connect(uri, uri=True, timeout=self.config.timeout_s)
        self._conn.row_factory = sqlite3.Row

    async def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    async def list_tables(self) -> list[TableInfo]:
        conn = self._require_conn()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables: list[TableInfo] = []
        for row in cursor.fetchall():
            name = row[0]
            count_cursor = conn.execute(f"SELECT COUNT(*) FROM [{name}]")
            count = count_cursor.fetchone()[0]
            tables.append(TableInfo(name=name, row_count=count))
        return tables

    async def describe_table(self, table_name: str) -> TableInfo:
        conn = self._require_conn()
        cursor = conn.execute(f"PRAGMA table_info([{table_name}])")
        columns: list[dict[str, Any]] = []
        for row in cursor.fetchall():
            columns.append({
                "name": row[1],
                "type": row[2],
                "notnull": bool(row[3]),
                "default": row[4],
                "pk": bool(row[5]),
            })
        count_cursor = conn.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        count = count_cursor.fetchone()[0]
        return TableInfo(name=table_name, columns=columns, row_count=count)

    async def get_schema(self) -> SchemaInfo:
        tables = await self.list_tables()
        detailed: list[TableInfo] = []
        for t in tables:
            detailed.append(await self.describe_table(t.name))
        return SchemaInfo(
            tables=detailed,
            database_type="sqlite",
            database_path=self.path,
        )

    async def execute_query(self, sql: str) -> QueryResult:
        """Execute a SQL query with security controls."""
        conn = self._require_conn()

        if len(sql) > self.config.max_query_length:
            return QueryResult(error=f"Query too long ({len(sql)} chars, max {self.config.max_query_length})")

        # Block write operations in read-only mode
        if self.config.read_only:
            sql_upper = sql.strip().upper()
            write_ops = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "TRUNCATE")
            if any(sql_upper.startswith(op) for op in write_ops):
                return QueryResult(error="Write operations not allowed in read-only mode")

        t0 = time.time()
        try:
            cursor = conn.execute(sql)
            if cursor.description is None:
                return QueryResult(execution_time_ms=(time.time() - t0) * 1000)

            columns = [desc[0] for desc in cursor.description]
            rows_raw = cursor.fetchmany(self.config.max_rows + 1)
            truncated = len(rows_raw) > self.config.max_rows
            rows = [list(r) for r in rows_raw[:self.config.max_rows]]

            return QueryResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                truncated=truncated,
                execution_time_ms=(time.time() - t0) * 1000,
            )
        except Exception as e:
            return QueryResult(
                error=str(e),
                execution_time_ms=(time.time() - t0) * 1000,
            )

    async def sample_table(self, table_name: str, limit: int = 5) -> QueryResult:
        """Get sample rows from a table."""
        return await self.execute_query(f"SELECT * FROM [{table_name}] LIMIT {min(limit, self.config.max_rows)}")

    # -- context manager support --

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()
