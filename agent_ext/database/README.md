# Database — SQL Capabilities for AI Agents

Empower AI agents to explore schemas, query data, and understand database structures with built-in security controls.

## Features

- **SQLite Backend**: Full schema exploration and query execution
- **Security**: Read-only mode, row limits, query length limits, timeouts
- **Schema Discovery**: List tables, describe columns, sample data
- **Write Protection**: Block INSERT/UPDATE/DELETE in read-only mode

## Quick Start

```python
from agent_ext.database import SQLiteDatabase, DatabaseConfig

# Read-only access (default)
db = SQLiteDatabase("my_data.db")
await db.connect()

# Explore schema
tables = await db.list_tables()
for t in tables:
    print(f"{t.name}: {t.row_count} rows")

# Describe a table
info = await db.describe_table("users")
for col in info.columns:
    print(f"  {col['name']} ({col['type']})")

# Query with security controls
result = await db.execute_query("SELECT * FROM users WHERE age > 25")
print(f"Got {result.row_count} rows")

# Sample data
sample = await db.sample_table("users", limit=5)

await db.disconnect()
```

## Context Manager

```python
async with SQLiteDatabase("data.db") as db:
    result = await db.execute_query("SELECT COUNT(*) FROM orders")
```

## Security Configuration

```python
config = DatabaseConfig(
    read_only=True,        # Block all writes
    max_rows=1000,         # Limit result size
    timeout_s=30.0,        # Query timeout
    max_query_length=10000 # Prevent huge queries
)
db = SQLiteDatabase("data.db", config=config)
```
