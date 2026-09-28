"""
Hybrid search layer.

Ranks results by merging multiple evidence signals through reciprocal rank
fusion (RRF): SQLite FTS5 (BM25), substring matching, graph proximity
(entities only), and recency. Retrieval functions return the same row shape
as the source tables, so callers need no changes.
"""

import re
from collections import defaultdict
from typing import Any

import aiosqlite

from .constants import (
    FTS_TABLES,
    RRF_K,
    SEARCH_CANDIDATE_LIMIT,
    prepare_fts_text,
)

# ── FTS query building ────────────────────────────────────────────────────────


def build_fts_query(query: str) -> str | None:
    """
    Convert a free-text query into an FTS5 match expression.

    Word tokens are extracted, camelCase boundaries split, single characters
    dropped, and the remainder joined as OR'd prefix queries, so a query like
    'volume controller' matches text containing either term. Returns None
    when no usable token remains (callers fall back to substring matching).
    """
    tokens: list[str] = []
    for raw in re.findall(r"\w+", query):
        for part in prepare_fts_text(raw).split():
            token = part.lower()
            if len(token) >= 2 and token not in tokens:
                tokens.append(token)
    if not tokens:
        return None
    return " OR ".join(f"{token}*" for token in tokens)


# ── FTS sync (write paths) ────────────────────────────────────────────────────


async def sync_decision_fts(
    db: aiosqlite.Connection, ref: str, title: str, rationale: str | None
) -> None:
    """Replace the FTS row for a decision."""
    await db.execute(
        f"DELETE FROM {FTS_TABLES['decisions']} WHERE ref = ?",
        (ref,),
    )
    await db.execute(
        f"INSERT INTO {FTS_TABLES['decisions']} (ref, title, rationale) VALUES (?, ?, ?)",
        (ref, prepare_fts_text(title), prepare_fts_text(rationale)),
    )


async def sync_task_fts(db: aiosqlite.Connection, ref: str, title: str, notes: str | None) -> None:
    """Replace the FTS row for a task."""
    await db.execute(
        f"DELETE FROM {FTS_TABLES['tasks']} WHERE ref = ?",
        (ref,),
    )
    await db.execute(
        f"INSERT INTO {FTS_TABLES['tasks']} (ref, title, notes) VALUES (?, ?, ?)",
        (ref, prepare_fts_text(title), prepare_fts_text(notes)),
    )


async def sync_session_fts(db: aiosqlite.Connection, ref: str, summary: str | None) -> None:
    """Replace the FTS row for a session log entry."""
    await db.execute(
        f"DELETE FROM {FTS_TABLES['sessions']} WHERE ref = ?",
        (ref,),
    )
    await db.execute(
        f"INSERT INTO {FTS_TABLES['sessions']} (ref, summary) VALUES (?, ?)",
        (ref, prepare_fts_text(summary)),
    )


async def sync_entity_name_fts(db: aiosqlite.Connection, ref: str, name: str) -> None:
    """Replace the FTS name row for an entity (observation rows keep their own)."""
    await db.execute(
        f"DELETE FROM {FTS_TABLES['entities']} WHERE ref = ? AND obs_ref IS NULL",
        (ref,),
    )
    await db.execute(
        f"INSERT INTO {FTS_TABLES['entities']} (ref, obs_ref, content) VALUES (?, NULL, ?)",
        (ref, prepare_fts_text(name)),
    )


async def sync_observation_fts(
    db: aiosqlite.Connection, observation_id: str, entity_id: str, content: str
) -> None:
    """Add the FTS row for a new observation under its entity's ref."""
    await db.execute(
        f"INSERT INTO {FTS_TABLES['entities']} (ref, obs_ref, content) VALUES (?, ?, ?)",
        (entity_id, observation_id, prepare_fts_text(content)),
    )


async def delete_entity_fts(db: aiosqlite.Connection, entity_id: str) -> None:
    """Remove every FTS row belonging to an entity, including its observations."""
    await db.execute(
        f"DELETE FROM {FTS_TABLES['entities']} WHERE ref = ?",
        (entity_id,),
    )


async def delete_observation_fts(db: aiosqlite.Connection, observation_id: str) -> None:
    """Remove the FTS row for a single observation."""
    await db.execute(
        f"DELETE FROM {FTS_TABLES['entities']} WHERE obs_ref = ?",
        (observation_id,),
    )


# ── Ranking helpers ───────────────────────────────────────────────────────────


async def _fts_rows(
    db: aiosqlite.Connection, table: str, fts_query: str
) -> list[tuple[str, float]]:
    """
    Run an FTS5 match and return (ref, score) pairs aggregated per ref.

    Score is the negated BM25 rank summed across matching rows, so higher is
    better. entities_fts shares one ref across an entity's name row and its
    observation rows, so their scores fold together.
    """
    async with db.execute(
        f"SELECT ref, rank FROM {table} WHERE {table} MATCH ? LIMIT ?",
        (fts_query, SEARCH_CANDIDATE_LIMIT),
    ) as cursor:
        rows = await cursor.fetchall()
    scores: dict[str, float] = defaultdict(float)
    for row in rows:
        rank = row["rank"]
        if rank is not None:
            scores[row["ref"]] += -float(rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def _rrf_scores(ordered_ids: list[str]) -> dict[str, float]:
    """Reciprocal rank fusion scores for one signal (1-based ranks)."""
    return {id_: 1.0 / (RRF_K + rank) for rank, id_ in enumerate(ordered_ids, start=1)}


def _merge(*signals: dict[str, float]) -> dict[str, float]:
    """Sum RRF contributions across signals."""
    merged: dict[str, float] = defaultdict(float)
    for signal in signals:
        for id_, value in signal.items():
            merged[id_] += value
    return dict(merged)


async def _rows_by_refs(
    db: aiosqlite.Connection,
    table: str,
    refs: list[str],
    where: str = "",
    params: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch full rows for refs, preserving ref order.

    Refs filtered out by the extra WHERE clause are dropped; refs missing
    from the table are also dropped.
    """
    if not refs:
        return []
    placeholders = ", ".join("?" * len(refs))
    async with db.execute(
        f"SELECT * FROM {table} WHERE id IN ({placeholders}) {where}",
        [*refs, *(params or [])],
    ) as cursor:
        by_id = {row["id"]: dict(row) for row in await cursor.fetchall()}
    return [by_id[ref] for ref in refs if ref in by_id]


def _recency_rows(rows: list[dict[str, Any]], field: str = "created_at") -> list[dict[str, Any]]:
    """Rank rows newest-first; timestamps are sortable ISO strings."""
    return sorted(rows, key=lambda row: row.get(field) or "", reverse=True)


async def _proximity_rows(
    db: aiosqlite.Connection,
    project_id: str,
    candidate_ids: list[str],
    rows_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Rank candidate entities by how many other candidates they relate to.

    Entities connected to more matching results surface higher, with
    importance breaking ties.
    """
    if len(candidate_ids) < 2:
        return []
    placeholders = ", ".join("?" * len(candidate_ids))
    async with db.execute(
        f"""
        SELECT from_id, to_id FROM relations
        WHERE project_id = ?
          AND from_id IN ({placeholders})
          AND to_id IN ({placeholders})
        """,
        (project_id, *candidate_ids, *candidate_ids),
    ) as cursor:
        edges = await cursor.fetchall()
    counts: dict[str, int] = defaultdict(int)
    for edge in edges:
        counts[edge["from_id"]] += 1
        counts[edge["to_id"]] += 1
    ranked = sorted(
        (id_ for id_ in counts if id_ in rows_by_id),
        key=lambda id_: (counts[id_], rows_by_id[id_]["importance"]),
        reverse=True,
    )
    return [rows_by_id[id_] for id_ in ranked]


def _item_size(category: str, item: dict[str, Any]) -> int:
    """Estimate the rendered size of one result item for token budgeting."""
    if category == "entities":
        return len(str(item.get("name", ""))) + len(str(item.get("entity_type", "")))
    if category == "decisions":
        return len(str(item.get("title", ""))) + len(str(item.get("rationale", "")))
    if category == "tasks":
        return len(str(item.get("title", ""))) + len(str(item.get("notes", "")))
    if category == "sessions":
        return len(str(item.get("summary", "")))
    return len(str(item))


def _apply_token_budget(
    results: dict[str, list[dict[str, Any]]],
    scores_by_category: dict[str, dict[str, float]],
    max_chars: int,
) -> dict[str, list[dict[str, Any]]]:
    """
    Drop lowest-scored items across categories until the estimated size fits.

    Items missing a score (e.g. below the ranking cut) are treated as -1.0
    and dropped first. Untouched categories keep their row shape.
    """
    total = sum(_item_size(c, item) for c, items in results.items() for item in items)
    if total <= max_chars:
        return results
    budgeted = {category: list(items) for category, items in results.items()}
    while total > max_chars and any(budgeted.values()):
        lowest: tuple[float, str, int] | None = None
        for category, items in budgeted.items():
            if not items:
                continue
            for index, item in enumerate(items):
                score = scores_by_category.get(category, {}).get(item.get("id", ""), -1.0)
                candidate = (score, category, index)
                if lowest is None or candidate < lowest:
                    lowest = candidate
        if lowest is None:
            break
        score, category, index = lowest
        removed = budgeted[category].pop(index)
        total -= _item_size(category, removed)
    return budgeted


# ── Retrieval ─────────────────────────────────────────────────────────────────


async def search_entities(
    db: aiosqlite.Connection,
    project_id: str,
    query: str,
    entity_type: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Search entities by name or observation content.

    Merges BM25 full-text and substring signals through reciprocal rank
    fusion, with importance breaking ties. Returns entity rows only; callers
    resolve matching observations when formatting.
    """
    fts_query = build_fts_query(query)
    fts_rows: list[dict[str, Any]] = []
    if fts_query:
        refs = [ref for ref, _score in await _fts_rows(db, FTS_TABLES["entities"], fts_query)]
        type_filter = "AND entity_type = ?" if entity_type else ""
        fts_rows = await _rows_by_refs(
            db, "entities", refs, type_filter, [entity_type] if entity_type else []
        )

    like = f"%{query}%"
    like_params: list[Any] = [project_id]
    type_filter = ""
    if entity_type:
        type_filter = "AND e.entity_type = ?"
        like_params.append(entity_type)
    like_params.extend([like, like, SEARCH_CANDIDATE_LIMIT])
    async with db.execute(
        f"""
        SELECT DISTINCT e.*
        FROM entities e
        LEFT JOIN observations o ON o.entity_id = e.id
        WHERE e.project_id = ?
          {type_filter}
          AND (e.name LIKE ? OR o.content LIKE ?)
        ORDER BY e.importance DESC
        LIMIT ?
        """,
        tuple(like_params),
    ) as cursor:
        like_rows = [dict(row) for row in await cursor.fetchall()]

    rows_by_id = {**{row["id"]: row for row in fts_rows}, **{row["id"]: row for row in like_rows}}
    scores = _merge(
        _rrf_scores([row["id"] for row in fts_rows]),
        _rrf_scores([row["id"] for row in like_rows]),
    )
    ordered = sorted(
        rows_by_id.values(),
        key=lambda row: (scores.get(row["id"], 0.0), row["importance"]),
        reverse=True,
    )
    return ordered[:limit]


async def search_memory(
    db: aiosqlite.Connection,
    project_id: str,
    query: str,
    branch: str | None = None,
    limit: int = 10,
    max_chars: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Hybrid cross-category search across decisions, sessions, tasks and entities.

    Merges BM25 full-text matches, substring matches, graph proximity
    (entities only) and recency through reciprocal rank fusion. Branch
    filtering keeps global rows always included, matching the documented
    behaviour. Returns per-category lists keyed by ``entities``,
    ``decisions``, ``sessions`` and ``tasks``, each capped at ``limit``.
    ``max_chars`` optionally drops lowest-scored items until the estimated
    rendered size fits the budget.
    """
    fts_query = build_fts_query(query)
    like = f"%{query}%"
    branch_filter = "AND (branch IS NULL OR ? IS NULL OR branch = ?)"

    async def fts_signal(
        table: str, source_table: str, where: str, params: list[Any]
    ) -> list[dict[str, Any]]:
        if not fts_query:
            return []
        refs = [ref for ref, _score in await _fts_rows(db, table, fts_query)]
        return await _rows_by_refs(db, source_table, refs, where, params)

    # ── Decisions ─────────────────────────────────────────────────────────────
    decisions_fts = await fts_signal(
        FTS_TABLES["decisions"],
        "decisions",
        f"AND project_id = ? {branch_filter}",
        [project_id, branch, branch],
    )
    async with db.execute(
        f"""
        SELECT * FROM decisions
        WHERE project_id = ?
          {branch_filter}
          AND (title LIKE ? OR rationale LIKE ?)
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (project_id, branch, branch, like, like, SEARCH_CANDIDATE_LIMIT),
    ) as cursor:
        decisions_like = [dict(row) for row in await cursor.fetchall()]

    # ── Sessions ──────────────────────────────────────────────────────────────
    sessions_fts = await fts_signal(
        FTS_TABLES["sessions"],
        "session_log",
        f"AND project_id = ? {branch_filter}",
        [project_id, branch, branch],
    )
    async with db.execute(
        f"""
        SELECT * FROM session_log
        WHERE project_id = ?
          {branch_filter}
          AND summary LIKE ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (project_id, branch, branch, like, SEARCH_CANDIDATE_LIMIT),
    ) as cursor:
        sessions_like = [dict(row) for row in await cursor.fetchall()]

    # ── Tasks ─────────────────────────────────────────────────────────────────
    tasks_fts = await fts_signal(
        FTS_TABLES["tasks"],
        "tasks",
        f"AND project_id = ? {branch_filter}",
        [project_id, branch, branch],
    )
    async with db.execute(
        f"""
        SELECT * FROM tasks
        WHERE project_id = ?
          {branch_filter}
          AND (title LIKE ? OR notes LIKE ?)
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (project_id, branch, branch, like, like, SEARCH_CANDIDATE_LIMIT),
    ) as cursor:
        tasks_like = [dict(row) for row in await cursor.fetchall()]

    # ── Entities ──────────────────────────────────────────────────────────────
    entities_fts = await fts_signal(
        FTS_TABLES["entities"],
        "entities",
        f"AND project_id = ? {branch_filter}",
        [project_id, branch, branch],
    )
    async with db.execute(
        """
        SELECT DISTINCT e.*
        FROM entities e
        LEFT JOIN observations o ON o.entity_id = e.id
        WHERE e.project_id = ?
          AND (e.branch IS NULL OR ? IS NULL OR e.branch = ?)
          AND (e.name LIKE ? OR o.content LIKE ?)
        ORDER BY e.importance DESC
        LIMIT ?
        """,
        (project_id, branch, branch, like, like, SEARCH_CANDIDATE_LIMIT),
    ) as cursor:
        entities_like = [dict(row) for row in await cursor.fetchall()]

    def rank_category(
        fts_rows: list[dict[str, Any]],
        like_rows: list[dict[str, Any]],
        recency_field: str,
    ) -> tuple[list[dict[str, Any]], dict[str, float]]:
        rows_by_id = {
            **{row["id"]: row for row in fts_rows},
            **{row["id"]: row for row in like_rows},
        }
        recency = _recency_rows(list(rows_by_id.values()), field=recency_field)
        scores = _merge(
            _rrf_scores([row["id"] for row in fts_rows]),
            _rrf_scores([row["id"] for row in like_rows]),
            _rrf_scores([row["id"] for row in recency]),
        )
        ordered = sorted(
            rows_by_id.values(),
            key=lambda row: (scores.get(row["id"], 0.0), row.get(recency_field) or ""),
            reverse=True,
        )
        return ordered[:limit], scores

    ordered_decisions, decision_scores = rank_category(decisions_fts, decisions_like, "created_at")
    ordered_sessions, session_scores = rank_category(sessions_fts, sessions_like, "created_at")
    ordered_tasks, task_scores = rank_category(tasks_fts, tasks_like, "updated_at")

    entity_rows_by_id = {
        **{row["id"]: row for row in entities_fts},
        **{row["id"]: row for row in entities_like},
    }
    candidate_ids = list(
        dict.fromkeys([row["id"] for row in entities_fts] + [row["id"] for row in entities_like])
    )
    proximity_rows = await _proximity_rows(db, project_id, candidate_ids, entity_rows_by_id)
    entity_recency = _recency_rows(list(entity_rows_by_id.values()), field="updated_at")
    entity_scores = _merge(
        _rrf_scores([row["id"] for row in entities_fts]),
        _rrf_scores([row["id"] for row in entities_like]),
        _rrf_scores([row["id"] for row in proximity_rows]),
        _rrf_scores([row["id"] for row in entity_recency]),
    )
    ordered_entities = sorted(
        entity_rows_by_id.values(),
        key=lambda row: (
            entity_scores.get(row["id"], 0.0),
            row["importance"],
            row["created_at"] or "",
        ),
        reverse=True,
    )[:limit]

    results = {
        "entities": ordered_entities,
        "decisions": ordered_decisions,
        "sessions": ordered_sessions,
        "tasks": ordered_tasks,
    }
    scores_by_category = {
        "entities": entity_scores,
        "decisions": decision_scores,
        "sessions": session_scores,
        "tasks": task_scores,
    }
    if max_chars is not None:
        results = _apply_token_budget(results, scores_by_category, max_chars)
    return results
