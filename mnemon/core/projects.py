import aiosqlite


async def upsert_project(
    db: aiosqlite.Connection,
    project_id: str,
    git_url: str | None = None,
    parent_id: str | None = None,
) -> None:
    name = project_id.split("/")[-1] if "/" in project_id else project_id
    await db.execute(
        """
        INSERT INTO projects (id, parent_id, name, git_url)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            git_url   = COALESCE(excluded.git_url,   git_url),
            parent_id = COALESCE(excluded.parent_id, parent_id)
        """,
        (project_id, parent_id, name, git_url),
    )
    await db.commit()


async def list_projects(
    db: aiosqlite.Connection,
    parent_id: str | None = None,
) -> list[dict]:
    if parent_id:
        async with db.execute(
            "SELECT * FROM projects WHERE parent_id = ? ORDER BY id", (parent_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
    async with db.execute("SELECT * FROM projects ORDER BY id") as cur:
        return [dict(r) for r in await cur.fetchall()]
