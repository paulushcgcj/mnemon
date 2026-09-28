from typing import Any, cast

import aiosqlite

from .constants import (
    DEFAULT_SESSION_LOG_SOURCE,
    DEFAULT_TASK_STATUS,
    validate_task_status,
)
from .search import (
    search_memory as search_memory,  # re-exported: search lives in the search module
)
from .search import (
    sync_decision_fts,
    sync_session_fts,
    sync_task_fts,
)

# ── Project state ─────────────────────────────────────────────────────────────


async def get_project_state(db: aiosqlite.Connection, project_id: str) -> dict[str, Any] | None:
    async with db.execute("SELECT * FROM project_state WHERE project_id = ?", (project_id,)) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def upsert_project_state(db: aiosqlite.Connection, project_id: str, context: str) -> None:
    await db.execute(
        """
        INSERT INTO project_state (project_id, context, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(project_id) DO UPDATE SET
            context = excluded.context, updated_at = excluded.updated_at
        """,
        (project_id, context),
    )
    await db.commit()


# ── Branch state ──────────────────────────────────────────────────────────────


async def get_branch_state(
    db: aiosqlite.Connection, project_id: str, branch: str
) -> dict[str, Any] | None:
    async with db.execute(
        "SELECT * FROM branch_state WHERE project_id = ? AND branch = ?",
        (project_id, branch),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def upsert_branch_state(
    db: aiosqlite.Connection,
    project_id: str,
    branch: str,
    current_focus: str,
    next_steps: str,
) -> None:
    await db.execute(
        """
        INSERT INTO branch_state (project_id, branch, current_focus, next_steps, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        ON CONFLICT(project_id, branch) DO UPDATE SET
            current_focus = excluded.current_focus,
            next_steps    = excluded.next_steps,
            updated_at    = excluded.updated_at
        """,
        (project_id, branch, current_focus, next_steps),
    )
    await db.commit()


# ── Decisions ─────────────────────────────────────────────────────────────────


async def add_decision(
    db: aiosqlite.Connection,
    project_id: str,
    title: str,
    rationale: str,
    branch: str | None = None,
) -> str:
    async with db.execute(
        """
        INSERT INTO decisions (project_id, branch, title, rationale)
        VALUES (?, ?, ?, ?) RETURNING id
        """,
        (project_id, branch, title, rationale),
    ) as cur:
        row = await cur.fetchone()
        if row is not None:
            await sync_decision_fts(db, cast(str, row[0]), title, rationale)
        await db.commit()
        return cast(str, row[0]) if row is not None else ""


async def get_decisions(
    db: aiosqlite.Connection,
    project_id: str,
    branch: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    async with db.execute(
        """
        SELECT * FROM decisions
        WHERE project_id = ? AND (branch IS NULL OR branch = ?)
        ORDER BY created_at DESC LIMIT ?
        """,
        (project_id, branch, limit),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


# ── Tasks ─────────────────────────────────────────────────────────────────────


async def add_task(
    db: aiosqlite.Connection,
    project_id: str,
    title: str,
    branch: str | None = None,
    source: str = "ai",
    notes: str | None = None,
    status: str = DEFAULT_TASK_STATUS,
) -> str:
    async with db.execute(
        """
        INSERT INTO tasks (project_id, branch, title, status, source, notes)
        VALUES (?, ?, ?, ?, ?, ?) RETURNING id
        """,
        (project_id, branch, title, status, source, notes),
    ) as cur:
        row = await cur.fetchone()
        if row is not None:
            await sync_task_fts(db, cast(str, row[0]), title, notes)
        await db.commit()
        return cast(str, row[0]) if row is not None else ""


async def update_task(
    db: aiosqlite.Connection,
    task_id: str,
    status: str,
    notes: str | None = None,
) -> bool:
    # Validate status
    status = validate_task_status(status)

    async with db.execute(
        """
        UPDATE tasks
        SET status = ?, notes = COALESCE(?, notes), updated_at = datetime('now')
        WHERE id = ?
        RETURNING title, notes
        """,
        (status, notes, task_id),
    ) as cur:
        row = await cur.fetchone()
        if row is not None:
            await sync_task_fts(db, task_id, row["title"], row["notes"])
        await db.commit()
        return row is not None


async def get_tasks(
    db: aiosqlite.Connection,
    project_id: str,
    branch: str | None = None,
) -> list[dict[str, Any]]:
    async with db.execute(
        """
        SELECT * FROM tasks
        WHERE project_id = ? AND (branch IS NULL OR branch = ?)
        ORDER BY
            CASE status
                WHEN 'in-progress' THEN 1
                WHEN 'blocked'     THEN 2
                WHEN 'todo'        THEN 3
                WHEN 'done'        THEN 4
            END, updated_at DESC
        """,
        (project_id, branch),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


# ── Session log ───────────────────────────────────────────────────────────────


async def add_session_log(
    db: aiosqlite.Connection,
    project_id: str,
    summary: str,
    branch: str | None = None,
    source: str = DEFAULT_SESSION_LOG_SOURCE,
    sha: str | None = None,
) -> None:
    async with db.execute(
        "INSERT INTO session_log (project_id, branch, summary, source, sha) VALUES (?,?,?,?,?) RETURNING id",
        (project_id, branch, summary, source, sha),
    ) as cur:
        row = await cur.fetchone()
        if row is not None:
            await sync_session_fts(db, cast(str, row[0]), summary)
        await db.commit()


async def get_recent_sessions(
    db: aiosqlite.Connection,
    project_id: str,
    branch: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    async with db.execute(
        """
        SELECT * FROM session_log
        WHERE project_id = ? AND (branch IS NULL OR branch = ?)
        ORDER BY created_at DESC LIMIT ?
        """,
        (project_id, branch, limit),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]
