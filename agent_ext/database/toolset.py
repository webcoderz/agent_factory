"""Database toolset — gives any pydantic-ai agent SQL query capabilities.

Example::

    from pydantic_ai import Agent
    from agent_ext.database import create_database_toolset, SQLDatabaseDeps, SQLiteDatabase

    db = SQLiteDatabase("my_data.db")
    await db.connect()

    toolset = create_database_toolset()
    agent = Agent("openai:gpt-4o", toolsets=[toolset])

    deps = SQLDatabaseDeps(database=db)
    result = await agent.run("What tables are in the database?", deps=deps)
"""
from __future__ import annotations

import asyncio
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, SkipValidation
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from .protocol import DatabaseBackend
from .types import QueryResult, SchemaInfo, TableInfo

DATABASE_SYSTEM_PROMPT = """
## Database Toolset

### IMPORTANT
* Database may be running in READ-ONLY mode
* When in read-only mode, only SELECT queries are allowed

You have access to database tools:
* `list_tables` - list all tables in the database
* `describe_table` - get column info for a table
* `sample_table` - preview rows from a table
* `query` - execute a SQL query

### Best Practices
* Always sample a table before writing complex queries
* Use LIMIT when querying large tables
* Validate queries against the schema before running
"""


class SQLDatabaseDeps(BaseModel):
    """Dependencies for the database toolset."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    database: Annotated[Any, SkipValidation]  # DatabaseBackend
    read_only: bool = True
    max_rows: int = 100
    query_timeout: float = 30.0


def create_database_toolset(*, toolset_id: str | None = None) -> FunctionToolset[SQLDatabaseDeps]:
    """Create a database toolset for AI agents.

    Returns:
        FunctionToolset with list_tables, describe_table, sample_table, query tools.
    """
    toolset: FunctionToolset[SQLDatabaseDeps] = FunctionToolset(id=toolset_id)

    @toolset.tool
    async def list_tables(ctx: RunContext[SQLDatabaseDeps]) -> list[str]:
        """List all tables in the database."""
        tables = await ctx.deps.database.list_tables()
        return [t.name for t in tables]

    @toolset.tool
    async def describe_table(ctx: RunContext[SQLDatabaseDeps], table_name: str) -> str:
        """Get column info for a specific table.

        Args:
            table_name: Name of the table to describe.
        """
        info = await ctx.deps.database.describe_table(table_name)
        lines = [f"Table: {info.name} ({info.row_count} rows)"]
        for col in info.columns:
            pk = " [PK]" if col.get("pk") else ""
            nullable = "" if col.get("notnull") else " NULL"
            lines.append(f"  {col['name']} {col.get('type', '?')}{pk}{nullable}")
        return "\n".join(lines)

    @toolset.tool
    async def sample_table(ctx: RunContext[SQLDatabaseDeps], table_name: str, limit: int = 5) -> str:
        """Preview rows from a table.

        Args:
            table_name: Table to sample.
            limit: Number of rows (default 5).
        """
        result = await ctx.deps.database.sample_table(table_name, limit=min(limit, ctx.deps.max_rows))
        if result.error:
            return f"Error: {result.error}"
        if not result.rows:
            return "No rows found."
        header = " | ".join(result.columns)
        rows = [" | ".join(str(v) for v in row) for row in result.rows]
        return f"{header}\n{'─' * len(header)}\n" + "\n".join(rows)

    @toolset.tool
    async def query(ctx: RunContext[SQLDatabaseDeps], sql_query: str) -> str:
        """Execute a SQL query and return results.

        Args:
            sql_query: SQL query to execute.
        """
        try:
            result = await asyncio.wait_for(
                ctx.deps.database.execute_query(sql_query),
                timeout=ctx.deps.query_timeout,
            )
        except asyncio.TimeoutError:
            return f"Error: Query timed out after {ctx.deps.query_timeout}s"

        if result.error:
            return f"Error: {result.error}"

        if not result.columns:
            return f"Query executed successfully ({result.execution_time_ms:.0f}ms)"

        # Format as table
        if len(result.rows) > ctx.deps.max_rows:
            rows = result.rows[:ctx.deps.max_rows]
            truncated = True
        else:
            rows = result.rows
            truncated = result.truncated

        header = " | ".join(result.columns)
        lines = [header, "─" * len(header)]
        for row in rows:
            lines.append(" | ".join(str(v) for v in row))

        footer = f"\n({result.row_count} rows, {result.execution_time_ms:.0f}ms)"
        if truncated:
            footer += f" [truncated to {len(rows)} rows]"
        lines.append(footer)
        return "\n".join(lines)

    return toolset
