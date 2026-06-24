import aiosqlite

from .constants import (
    DEFAULT_SESSION_LOG_SOURCE,
    DEFAULT_TASK_STATUS,
    validate_task_status,
)

# ── Project state ─────────────────────────────────────────────────────────────

async def get_project_state(db: aiosqlite.Connection, project_id: str) -> dict | None:
    async with db.execute(
        "SELECT * FROM project_state WHERE project_id = ?", (project_id,)
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def upsert_project_state(
    db: aiosqlite.Connection, project_id: str, context: str
) -> None:
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
) -> dict | None:
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
        await db.commit()
        return row[0]  # type: ignore[index,no-any-return]


async def get_decisions(
    db: aiosqlite.Connection,
    project_id: str,
    branch: str | None = None,
    limit: int = 10,
) -> list[dict]:
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
        await db.commit()
        return row[0]  # type: ignore[index,no-any-return]


async def update_task(
    db: aiosqlite.Connection,
    task_id: str,
    status: str,
    notes: str | None = None,
) -> bool:
    # Validate status
    status = validate_task_status(status)

    result = await db.execute(
        """
        UPDATE tasks
        SET status = ?, notes = COALESCE(?, notes), updated_at = datetime('now')
        WHERE id = ?
        """,
        (status, notes, task_id),
    )
    await db.commit()
    return result.rowcount > 0


async def get_tasks(
    db: aiosqlite.Connection,
    project_id: str,
    branch: str | None = None,
) -> list[dict]:
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
    await db.execute(
        "INSERT INTO session_log (project_id, branch, summary, source, sha) VALUES (?,?,?,?,?)",
        (project_id, branch, summary, source, sha),
    )
    await db.commit()


async def get_recent_sessions(
    db: aiosqlite.Connection,
    project_id: str,
    branch: str | None = None,
    limit: int = 5,
) -> list[dict]:
    async with db.execute(
        """
        SELECT * FROM session_log
        WHERE project_id = ? AND (branch IS NULL OR branch = ?)
        ORDER BY created_at DESC LIMIT ?
        """,
        (project_id, branch, limit),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]
