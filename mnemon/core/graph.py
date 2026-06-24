"""
Knowledge graph layer — entities, observations, relations.

Better than Anthropic's memory server because:
- Entities are scoped to project (and optionally branch)
- Importance ranking controls context injection priority
- Entity types for structured categorisation
- Full search across entity names AND observations
- Pruning support for stale entities
- Relations surface in the context block automatically
"""

import aiosqlite

from .constants import DEFAULT_OBSERVATION_SOURCE


# ── Entities ──────────────────────────────────────────────────────────────────

async def upsert_entity(
    db: aiosqlite.Connection,
    project_id: str,
    name: str,
    entity_type: str,
    importance: float = 0.5,
    branch: str | None = None,
) -> str:
    """Create entity if it doesn't exist; update type/importance if it does."""
    # Validate inputs
    from .constants import validate_entity_type, validate_importance, DEFAULT_ENTITY_TYPE, DEFAULT_IMPORTANCE
    entity_type = validate_entity_type(entity_type)
    importance = validate_importance(importance)
    
    async with db.execute(
        """
        INSERT INTO entities (project_id, branch, name, entity_type, importance)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(project_id, name) DO UPDATE SET
            entity_type = excluded.entity_type,
            importance  = excluded.importance,
            updated_at  = datetime('now')
        RETURNING id
        """,
        (project_id, branch, name, entity_type, importance),
    ) as cur:
        row = await cur.fetchone()
        await db.commit()
        return row[0]


async def delete_entity(
    db: aiosqlite.Connection, project_id: str, name: str
) -> bool:
    result = await db.execute(
        "DELETE FROM entities WHERE project_id = ? AND name = ?",
        (project_id, name),
    )
    await db.commit()
    return result.rowcount > 0


async def get_entity_by_name(
    db: aiosqlite.Connection, project_id: str, name: str
) -> dict | None:
    async with db.execute(
        "SELECT * FROM entities WHERE project_id = ? AND name = ?",
        (project_id, name),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_entities(
    db: aiosqlite.Connection,
    project_id: str,
    entity_type: str | None = None,
    branch: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Return entities ordered by importance descending."""
    if entity_type:
        async with db.execute(
            """
            SELECT * FROM entities
            WHERE project_id = ? AND entity_type = ?
              AND (branch IS NULL OR branch = ?)
            ORDER BY importance DESC, updated_at DESC LIMIT ?
            """,
            (project_id, entity_type, branch, limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async with db.execute(
        """
        SELECT * FROM entities
        WHERE project_id = ? AND (branch IS NULL OR branch = ?)
        ORDER BY importance DESC, updated_at DESC LIMIT ?
        """,
        (project_id, branch, limit),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


# ── Observations ──────────────────────────────────────────────────────────────

async def add_observation(
    db: aiosqlite.Connection,
    entity_id: str,
    content: str,
    source: str = DEFAULT_OBSERVATION_SOURCE,
) -> str:
    async with db.execute(
        "INSERT INTO observations (entity_id, content, source) VALUES (?,?,?) RETURNING id",
        (entity_id, content, source),
    ) as cur:
        row = await cur.fetchone()
        await db.commit()
        return row[0]


async def delete_observation(db: aiosqlite.Connection, observation_id: str) -> bool:
    result = await db.execute(
        "DELETE FROM observations WHERE id = ?", (observation_id,)
    )
    await db.commit()
    return result.rowcount > 0


async def get_observations(
    db: aiosqlite.Connection, entity_id: str
) -> list[dict]:
    async with db.execute(
        "SELECT * FROM observations WHERE entity_id = ? ORDER BY created_at ASC",
        (entity_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


# ── Relations ─────────────────────────────────────────────────────────────────

async def add_relation(
    db: aiosqlite.Connection,
    project_id: str,
    from_id: str,
    to_id: str,
    relation: str,
) -> str:
    async with db.execute(
        """
        INSERT INTO relations (project_id, from_id, to_id, relation)
        VALUES (?,?,?,?)
        ON CONFLICT(from_id, to_id, relation) DO UPDATE SET relation = excluded.relation
        RETURNING id
        """,
        (project_id, from_id, to_id, relation),
    ) as cur:
        row = await cur.fetchone()
        await db.commit()
        return row[0]


async def delete_relation(db: aiosqlite.Connection, relation_id: str) -> bool:
    result = await db.execute("DELETE FROM relations WHERE id = ?", (relation_id,))
    await db.commit()
    return result.rowcount > 0


async def get_relations_for(
    db: aiosqlite.Connection, entity_id: str
) -> list[dict]:
    """Return outgoing and incoming relations with entity names resolved."""
    async with db.execute(
        """
        SELECT r.id, r.relation, r.created_at,
               'out'   AS direction,
               e2.name AS other_name,
               e2.entity_type AS other_type
        FROM relations r
        JOIN entities e2 ON e2.id = r.to_id
        WHERE r.from_id = ?

        UNION ALL

        SELECT r.id, r.relation, r.created_at,
               'in'    AS direction,
               e1.name AS other_name,
               e1.entity_type AS other_type
        FROM relations r
        JOIN entities e1 ON e1.id = r.from_id
        WHERE r.to_id = ?
        ORDER BY direction, r.relation
        """,
        (entity_id, entity_id),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


# ── Search ────────────────────────────────────────────────────────────────────

async def search_entities(
    db: aiosqlite.Connection,
    project_id: str,
    query: str,
    entity_type: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Search entities by name or observation content.
    Returns entities ranked by importance, with matching observations attached.
    """
    like = f"%{query}%"
    
    if entity_type:
        # With entity_type filter
        async with db.execute(
            """
            SELECT DISTINCT e.*
            FROM entities e
            LEFT JOIN observations o ON o.entity_id = e.id
            WHERE e.project_id = ?
              AND e.entity_type = ?
              AND (e.name LIKE ? OR o.content LIKE ?)
            ORDER BY e.importance DESC
            LIMIT ?
            """,
            (project_id, entity_type, like, like, limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
    else:
        # Without entity_type filter
        async with db.execute(
            """
            SELECT DISTINCT e.*
            FROM entities e
            LEFT JOIN observations o ON o.entity_id = e.id
            WHERE e.project_id = ?
              AND (e.name LIKE ? OR o.content LIKE ?)
            ORDER BY e.importance DESC
            LIMIT ?
            """,
            (project_id, like, like, limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ── Full graph read ───────────────────────────────────────────────────────────

async def get_full_graph(
    db: aiosqlite.Connection,
    project_id: str,
    branch: str | None = None,
    importance_min: float = 0.0,
    limit: int = 30,
) -> list[dict]:
    """
    Return entities with their observations and relations.
    Ordered by importance so the most useful entities surface first.
    """
    entities = await list_entities(db, project_id, branch=branch, limit=limit)
    entities = [e for e in entities if e["importance"] >= importance_min]

    result = []
    for entity in entities:
        obs      = await get_observations(db, entity["id"])
        rels     = await get_relations_for(db, entity["id"])
        result.append({**entity, "observations": obs, "relations": rels})

    return result


# ── Pruning ───────────────────────────────────────────────────────────────────

async def prune_entities(
    db: aiosqlite.Connection,
    project_id: str,
    importance_below: float = 0.2,
    older_than_days: int = 30,
) -> int:
    """
    Delete entities that are both low-importance AND haven't been updated recently.
    Returns the number of entities pruned.
    """
    result = await db.execute(
        """
        DELETE FROM entities
        WHERE project_id = ?
          AND importance < ?
          AND updated_at < datetime('now', ? || ' days')
        """,
        (project_id, importance_below, f"-{older_than_days}"),
    )
    await db.commit()
    return result.rowcount
