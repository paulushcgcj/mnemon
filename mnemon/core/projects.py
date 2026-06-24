import aiosqlite
from typing import Optional


async def upsert_project(
    db: aiosqlite.Connection,
    project_id: str,
    name: Optional[str] = None,
    git_url: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> None:
    """
    Upsert a project.
    
    Args:
        db: Database connection
        project_id: The project ID (e.g., 'owner/repo')
        name: Optional human-readable name
        git_url: Optional Git URL
        parent_id: Optional parent project ID for hierarchical organization
    """
    # Prevent circular reference (parent can't be the same as project)
    if parent_id == project_id:
        raise ValueError(f"Project '{project_id}' cannot be its own parent.")
    
    # Check for circular reference in the tree (only if parent exists)
    if parent_id:
        # First check if parent exists
        async with db.execute(
            "SELECT 1 FROM projects WHERE id = ?", (parent_id,)
        ) as cur:
            parent_exists = await cur.fetchone() is not None
        
        if parent_exists:
            # Use a CTE to check if project_id would be an ancestor of parent_id
            async with db.execute(
                """
                WITH RECURSIVE ancestors AS (
                    SELECT id, parent_id FROM projects WHERE id = ?
                    UNION ALL
                    SELECT p.id, p.parent_id FROM projects p
                    JOIN ancestors a ON p.id = a.parent_id
                )
                SELECT 1 FROM ancestors WHERE id = ?
                """,
                (parent_id, project_id),
            ) as cur:
                result = await cur.fetchone()
                if result:
                    raise ValueError(
                        f"Circular reference detected: project '{project_id}' "
                        f"would be an ancestor of its parent '{parent_id}'."
                    )
    
    # Use provided name or derive from project_id
    if name is None:
        name = project_id.split("/")[-1] if "/" in project_id else project_id
    
    await db.execute(
        """
        INSERT INTO projects (id, name, git_url, parent_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = COALESCE(excluded.name, name),
            git_url = COALESCE(excluded.git_url, git_url),
            parent_id = COALESCE(excluded.parent_id, parent_id)
        """,
        (project_id, name, git_url, parent_id),
    )
    await db.commit()


async def list_projects(
    db: aiosqlite.Connection, 
    parent_id: Optional[str] = None,
    include_children: bool = False,
) -> list[dict]:
    """
    List projects, optionally filtered by parent.
    
    Args:
        db: Database connection
        parent_id: Filter by parent project ID. If None, returns all projects.
        include_children: If True and parent_id is set, also includes all descendants.
    
    Returns:
        List of project dicts
    """
    if parent_id and include_children:
        # Get all descendants (children, grandchildren, etc.)
        # This uses a recursive CTE to find all descendants
        async with db.execute(
            """
            WITH RECURSIVE project_tree AS (
                SELECT * FROM projects WHERE id = ?
                UNION ALL
                SELECT p.* FROM projects p
                JOIN project_tree pt ON p.parent_id = pt.id
            )
            SELECT * FROM project_tree
            ORDER BY id
            """,
            (parent_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
    elif parent_id:
        # Get direct children only
        async with db.execute(
            "SELECT * FROM projects WHERE parent_id = ? ORDER BY id",
            (parent_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
    else:
        # Get all projects
        async with db.execute("SELECT * FROM projects ORDER BY id") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_project_children(
    db: aiosqlite.Connection,
    project_id: str,
    recursive: bool = False,
) -> list[dict]:
    """
    Get direct children of a project.
    
    Args:
        db: Database connection
        project_id: The parent project ID
        recursive: If True, include all descendants (not just direct children)
    
    Returns:
        List of child project dicts
    """
    if recursive:
        # Get all descendants using CTE
        async with db.execute(
            """
            WITH RECURSIVE project_tree AS (
                SELECT * FROM projects WHERE parent_id = ?
                UNION ALL
                SELECT p.* FROM projects p
                JOIN project_tree pt ON p.parent_id = pt.id
            )
            SELECT * FROM project_tree
            ORDER BY id
            """,
            (project_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
    else:
        # Get direct children only
        async with db.execute(
            "SELECT * FROM projects WHERE parent_id = ? ORDER BY id",
            (project_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def set_project_parent(
    db: aiosqlite.Connection,
    project_id: str,
    parent_id: Optional[str],
) -> bool:
    """
    Set or update the parent of a project.
    
    Args:
        db: Database connection
        project_id: The project to update
        parent_id: The new parent, or None to remove parent
    
    Returns:
        True if a row was updated, False otherwise
    """
    # Prevent circular reference (parent can't be the same as project)
    if parent_id == project_id:
        raise ValueError(f"Project '{project_id}' cannot be its own parent.")
    
    # Check for circular reference in the tree (only if parent exists)
    if parent_id:
        # First check if parent exists
        async with db.execute(
            "SELECT 1 FROM projects WHERE id = ?", (parent_id,)
        ) as cur:
            parent_exists = await cur.fetchone() is not None
        
        if parent_exists:
            # Use a CTE to check if project_id would be an ancestor of parent_id
            async with db.execute(
                """
                WITH RECURSIVE ancestors AS (
                    SELECT id, parent_id FROM projects WHERE id = ?
                    UNION ALL
                    SELECT p.id, p.parent_id FROM projects p
                    JOIN ancestors a ON p.id = a.parent_id
                )
                SELECT 1 FROM ancestors WHERE id = ?
                """,
                (parent_id, project_id),
            ) as cur:
                result = await cur.fetchone()
                if result:
                    raise ValueError(
                        f"Circular reference detected: project '{project_id}' "
                        f"would be an ancestor of its parent '{parent_id}'."
                    )
    
    result = await db.execute(
        "UPDATE projects SET parent_id = ? WHERE id = ?",
        (parent_id, project_id),
    )
    await db.commit()
    return result.rowcount > 0


async def get_project_tree(
    db: aiosqlite.Connection,
    project_id: Optional[str] = None,
) -> list[dict]:
    """
    Get the full project tree as a nested structure.
    
    Args:
        db: Database connection
        project_id: Root project ID. If None, returns all top-level projects.
    
    Returns:
        List of project dicts with 'children' key containing nested children
    """
    if project_id:
        # Get subtree starting from project_id
        async with db.execute(
            """
            WITH RECURSIVE project_tree AS (
                SELECT * FROM projects WHERE id = ?
                UNION ALL
                SELECT p.* FROM projects p
                JOIN project_tree pt ON p.parent_id = pt.id
            )
            SELECT * FROM project_tree
            ORDER BY id
            """,
            (project_id,),
        ) as cur:
            all_projects = [dict(r) for r in await cur.fetchall()]
    else:
        # Get all root projects (no parent or parent is NULL)
        async with db.execute(
            """
            WITH RECURSIVE project_tree AS (
                SELECT * FROM projects WHERE parent_id IS NULL
                UNION ALL
                SELECT p.* FROM projects p
                JOIN project_tree pt ON p.parent_id = pt.id
            )
            SELECT * FROM project_tree
            ORDER BY id
            """,
        ) as cur:
            all_projects = [dict(r) for r in await cur.fetchall()]
    
    # Build nested structure
    def build_tree(projects, parent_id=None):
        children = [p for p in projects if p.get("parent_id") == parent_id]
        for child in children:
            child["children"] = build_tree(projects, child["id"])
        return children
    
    return build_tree(all_projects)
