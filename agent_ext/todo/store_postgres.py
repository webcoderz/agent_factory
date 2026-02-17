from __future__ import annotations

import uuid
from typing import List, Optional

import asyncpg

from agent_ext.todo.models import Task, TaskCreate, TaskPatch, TaskQuery, now_utc


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS agent_tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NULL,
  status TEXT NOT NULL,
  priority INT NOT NULL,

  parent_id TEXT NULL,
  depends_on TEXT[] NOT NULL DEFAULT '{}',
  tags TEXT[] NOT NULL DEFAULT '{}',

  case_id TEXT NULL,
  session_id TEXT NULL,
  user_id TEXT NULL,

  artifact_ids TEXT[] NOT NULL DEFAULT '{}',
  evidence_ids TEXT[] NOT NULL DEFAULT '{}',

  meta JSONB NOT NULL DEFAULT '{}'::jsonb,

  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS agent_tasks_case_idx ON agent_tasks(case_id);
CREATE INDEX IF NOT EXISTS agent_tasks_session_idx ON agent_tasks(session_id);
CREATE INDEX IF NOT EXISTS agent_tasks_user_idx ON agent_tasks(user_id);
CREATE INDEX IF NOT EXISTS agent_tasks_parent_idx ON agent_tasks(parent_id);
CREATE INDEX IF NOT EXISTS agent_tasks_status_idx ON agent_tasks(status);
"""


def _row_to_task(r: asyncpg.Record) -> Task:
    return Task(
        id=r["id"],
        title=r["title"],
        description=r["description"],
        status=r["status"],
        priority=r["priority"],
        parent_id=r["parent_id"],
        depends_on=list(r["depends_on"] or []),
        tags=list(r["tags"] or []),
        case_id=r["case_id"],
        session_id=r["session_id"],
        user_id=r["user_id"],
        artifact_ids=list(r["artifact_ids"] or []),
        evidence_ids=list(r["evidence_ids"] or []),
        meta=dict(r["meta"] or {}),
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


class PostgresTaskStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> "PostgresTaskStore":
        pool = await asyncpg.create_pool(dsn)
        async with pool.acquire() as conn:
            await conn.execute(CREATE_SQL)
        return cls(pool)

    async def create_task(self, data: TaskCreate) -> Task:
        tid = uuid.uuid4().hex
        now = now_utc()

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_tasks (
                  id,title,description,status,priority,parent_id,depends_on,tags,
                  case_id,session_id,user_id,artifact_ids,evidence_ids,meta,created_at,updated_at
                ) VALUES (
                  $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16
                )
                """,
                tid,
                data.title,
                data.description,
                "pending",
                data.priority,
                data.parent_id,
                list(dict.fromkeys(data.depends_on)),
                list(dict.fromkeys(data.tags)),
                data.case_id,
                data.session_id,
                data.user_id,
                [],  # artifact_ids
                [],  # evidence_ids
                data.meta,
                now,
                now,
            )

            row = await conn.fetchrow("SELECT * FROM agent_tasks WHERE id=$1", tid)
            return _row_to_task(row)

    async def get_task(self, task_id: str) -> Optional[Task]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM agent_tasks WHERE id=$1", task_id)
            return _row_to_task(row) if row else None

    async def list_tasks(self, q: TaskQuery) -> List[Task]:
        clauses = []
        args = []
        i = 1

        def add(cond: str, val):
            nonlocal i
            clauses.append(cond.replace("$", f"${i}"))
            args.append(val)
            i += 1

        if q.case_id:
            add("case_id = $", q.case_id)
        if q.session_id:
            add("session_id = $", q.session_id)
        if q.user_id:
            add("user_id = $", q.user_id)
        if q.status:
            add("status = $", q.status)
        if q.parent_id is not None:
            add("parent_id = $", q.parent_id)
        if q.tag:
            add("$ = ANY(tags)", q.tag)
        if q.text:
            add("(LOWER(title) LIKE $ OR LOWER(COALESCE(description,'')) LIKE $)", f"%{q.text.lower()}%")
            # same arg used twice: just append again
            args.append(args[-1])
            i += 1

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
        SELECT * FROM agent_tasks
        {where}
        ORDER BY priority ASC, created_at ASC
        LIMIT {int(q.limit)} OFFSET {int(q.offset)}
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
            return [_row_to_task(r) for r in rows]

    async def update_task(self, task_id: str, patch: TaskPatch) -> Optional[Task]:
        existing = await self.get_task(task_id)
        if not existing:
            return None

        p = patch.model_dump(exclude_unset=True)
        # merge
        merged = existing.model_dump()
        for k, v in p.items():
            if k in {"depends_on", "tags", "artifact_ids", "evidence_ids"} and v is not None:
                merged[k] = list(dict.fromkeys(v))
            else:
                merged[k] = v
        merged["updated_at"] = now_utc()

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE agent_tasks SET
                  title=$2, description=$3, status=$4, priority=$5,
                  parent_id=$6, depends_on=$7, tags=$8,
                  case_id=$9, session_id=$10, user_id=$11,
                  artifact_ids=$12, evidence_ids=$13, meta=$14,
                  updated_at=$15
                WHERE id=$1
                """,
                task_id,
                merged["title"],
                merged.get("description"),
                merged["status"],
                merged["priority"],
                merged.get("parent_id"),
                merged.get("depends_on", []),
                merged.get("tags", []),
                merged.get("case_id"),
                merged.get("session_id"),
                merged.get("user_id"),
                merged.get("artifact_ids", []),
                merged.get("evidence_ids", []),
                merged.get("meta", {}),
                merged["updated_at"],
            )
            row = await conn.fetchrow("SELECT * FROM agent_tasks WHERE id=$1", task_id)
            return _row_to_task(row) if row else None

    async def delete_task(self, task_id: str) -> bool:
        async with self.pool.acquire() as conn:
            r = await conn.execute("DELETE FROM agent_tasks WHERE id=$1", task_id)
            # asyncpg returns "DELETE <n>"
            return r.split()[-1] != "0"

    async def add_dependency(self, task_id: str, depends_on_task_id: str) -> Optional[Task]:
        t = await self.get_task(task_id)
        if not t:
            return None
        deps = list(dict.fromkeys([*t.depends_on, depends_on_task_id]))
        return await self.update_task(task_id, TaskPatch(depends_on=deps))

    async def add_subtask(self, parent_id: str, data: TaskCreate) -> Task:
        parent = await self.get_task(parent_id)
        if not parent:
            raise ValueError(f"Parent task not found: {parent_id}")

        merged = TaskCreate(
            **data.model_dump(),
            parent_id=parent_id,
            case_id=data.case_id or parent.case_id,
            session_id=data.session_id or parent.session_id,
            user_id=data.user_id or parent.user_id,
        )
        return await self.create_task(merged)
