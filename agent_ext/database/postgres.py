"""PostgreSQL database backend with security controls.

Requires ``asyncpg`` (already in project dependencies).

Example::

    from agent_ext.database import PostgresDatabase, DatabaseConfig

    async with PostgresDatabase("postgresql://user:pass@localhost/mydb") as db:
        tables = await db.list_tables()
        result = await db.execute_query("SELECT * FROM users LIMIT 10")
"""

from __future__ import annotations

import time
from typing import Any

from .types import DatabaseConfig, QueryResult, SchemaInfo, TableInfo


class PostgresDatabase:
    """PostgreSQL database backend.

    Provides schema exploration, query execution, and security controls.
    Uses asyncpg for async Postgres access.
    """

    def __init__(
        self,
        dsn: str,
        config: DatabaseConfig | None = None,
    ) -> None:
        self.dsn = dsn
        self.config = config or DatabaseConfig()
        self._pool: Any = None

    async def connect(self) -> None:
        import asyncpg

        self._pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5)

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    def _require_pool(self):
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool

    async def list_tables(self) -> list[TableInfo]:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
            tables: list[TableInfo] = []
            for row in rows:
                name = row["tablename"]
                count_row = await conn.fetchrow(f'SELECT COUNT(*) as cnt FROM "{name}"')
                tables.append(TableInfo(name=name, row_count=count_row["cnt"] if count_row else None))
            return tables

    async def describe_table(self, table_name: str) -> TableInfo:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT column_name, data_type, is_nullable, column_default,
                       (SELECT COUNT(*) > 0 FROM information_schema.key_column_usage k
                        WHERE k.table_name = c.table_name AND k.column_name = c.column_name
                        AND k.constraint_name LIKE '%_pkey') as is_pk
                FROM information_schema.columns c
                WHERE table_schema = 'public' AND table_name = $1
                ORDER BY ordinal_position
                """,
                table_name,
            )
            columns = [
                {
                    "name": r["column_name"],
                    "type": r["data_type"],
                    "notnull": r["is_nullable"] == "NO",
                    "default": r["column_default"],
                    "pk": bool(r["is_pk"]),
                }
                for r in rows
            ]
            count_row = await conn.fetchrow(f'SELECT COUNT(*) as cnt FROM "{table_name}"')
            return TableInfo(
                name=table_name,
                columns=columns,
                row_count=count_row["cnt"] if count_row else None,
            )

    async def get_schema(self) -> SchemaInfo:
        tables = await self.list_tables()
        detailed = [await self.describe_table(t.name) for t in tables]
        return SchemaInfo(
            tables=detailed,
            database_type="postgresql",
            database_path=self.dsn.split("@")[-1] if "@" in self.dsn else self.dsn,
        )

    async def execute_query(self, sql: str) -> QueryResult:
        pool = self._require_pool()

        if len(sql) > self.config.max_query_length:
            return QueryResult(error=f"Query too long ({len(sql)} chars, max {self.config.max_query_length})")

        if self.config.read_only:
            sql_upper = sql.strip().upper()
            write_ops = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "TRUNCATE")
            if any(sql_upper.startswith(op) for op in write_ops):
                return QueryResult(error="Write operations not allowed in read-only mode")

        t0 = time.time()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(sql)
                dt = (time.time() - t0) * 1000

                if not rows:
                    return QueryResult(execution_time_ms=dt)

                columns = list(rows[0].keys())
                result_rows = [list(r.values()) for r in rows[: self.config.max_rows + 1]]
                truncated = len(result_rows) > self.config.max_rows
                result_rows = result_rows[: self.config.max_rows]

                return QueryResult(
                    columns=columns,
                    rows=result_rows,
                    row_count=len(result_rows),
                    truncated=truncated,
                    execution_time_ms=dt,
                )
        except Exception as e:
            return QueryResult(error=str(e), execution_time_ms=(time.time() - t0) * 1000)

    async def sample_table(self, table_name: str, limit: int = 5) -> QueryResult:
        return await self.execute_query(f'SELECT * FROM "{table_name}" LIMIT {min(limit, self.config.max_rows)}')

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()
