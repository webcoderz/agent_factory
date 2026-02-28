"""Tests for the new database system."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from agent_ext.database import DatabaseConfig, SQLiteDatabase


@pytest.fixture
def test_db_path():
    """Create a temp SQLite database with test data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    conn.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
    conn.execute("INSERT INTO users VALUES (2, 'Bob', 25)")
    conn.execute("INSERT INTO users VALUES (3, 'Charlie', 35)")
    conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, total REAL)")
    conn.execute("INSERT INTO orders VALUES (1, 1, 99.99)")
    conn.execute("INSERT INTO orders VALUES (2, 2, 49.50)")
    conn.commit()
    conn.close()
    yield path
    Path(path).unlink(missing_ok=True)


class TestSQLiteDatabase:
    @pytest.mark.asyncio
    async def test_connect_disconnect(self, test_db_path):
        db = SQLiteDatabase(test_db_path)
        await db.connect()
        await db.disconnect()

    @pytest.mark.asyncio
    async def test_list_tables(self, test_db_path):
        async with SQLiteDatabase(test_db_path) as db:
            tables = await db.list_tables()
            names = [t.name for t in tables]
            assert "users" in names
            assert "orders" in names

    @pytest.mark.asyncio
    async def test_describe_table(self, test_db_path):
        async with SQLiteDatabase(test_db_path) as db:
            info = await db.describe_table("users")
            assert info.name == "users"
            col_names = [c["name"] for c in info.columns]
            assert "id" in col_names
            assert "name" in col_names
            assert "age" in col_names
            assert info.row_count == 3

    @pytest.mark.asyncio
    async def test_get_schema(self, test_db_path):
        async with SQLiteDatabase(test_db_path) as db:
            schema = await db.get_schema()
            assert schema.database_type == "sqlite"
            assert len(schema.tables) == 2

    @pytest.mark.asyncio
    async def test_execute_query(self, test_db_path):
        async with SQLiteDatabase(test_db_path) as db:
            result = await db.execute_query("SELECT * FROM users WHERE age > 25")
            assert result.error is None
            assert result.row_count == 2
            assert result.columns == ["id", "name", "age"]

    @pytest.mark.asyncio
    async def test_read_only_blocks_writes(self, test_db_path):
        async with SQLiteDatabase(test_db_path, config=DatabaseConfig(read_only=True)) as db:
            result = await db.execute_query("DELETE FROM users WHERE id = 1")
            assert result.error is not None
            assert "not allowed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_read_only_blocks_insert(self, test_db_path):
        async with SQLiteDatabase(test_db_path, config=DatabaseConfig(read_only=True)) as db:
            result = await db.execute_query("INSERT INTO users VALUES (4, 'Dave', 40)")
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_row_limit(self, test_db_path):
        async with SQLiteDatabase(test_db_path, config=DatabaseConfig(max_rows=1)) as db:
            result = await db.execute_query("SELECT * FROM users")
            assert result.row_count == 1
            assert result.truncated is True

    @pytest.mark.asyncio
    async def test_sample_table(self, test_db_path):
        async with SQLiteDatabase(test_db_path) as db:
            result = await db.sample_table("users", limit=2)
            assert result.error is None
            assert result.row_count == 2

    @pytest.mark.asyncio
    async def test_query_length_limit(self, test_db_path):
        async with SQLiteDatabase(test_db_path, config=DatabaseConfig(max_query_length=5)) as db:
            result = await db.execute_query("SELECT * FROM users")
            assert result.error is not None
            assert "too long" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invalid_query(self, test_db_path):
        async with SQLiteDatabase(test_db_path) as db:
            result = await db.execute_query("SELECT * FROM nonexistent_table")
            assert result.error is not None
